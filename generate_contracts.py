import os
import re
import json
import asyncio
import httpx
from datetime import datetime
from PIL import Image, ImageOps, ImageFilter
from dotenv import load_dotenv

# ReportLab modules
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm, inch
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

load_dotenv("/Users/phamtranthuyvy/Projects/chatbot-easytrip/.env")

# Register system fonts for Vietnamese Unicode
FONT_REGULAR = "Arial"
FONT_BOLD = "Arial-Bold"
FONT_ITALIC = "Arial-Italic"
FONT_BOLD_ITALIC = "Arial-BoldItalic"

def register_fonts():
    font_paths = {
        FONT_REGULAR: "/System/Library/Fonts/Supplemental/Arial.ttf",
        FONT_BOLD: "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        FONT_ITALIC: "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
        FONT_BOLD_ITALIC: "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
    }
    for name, path in font_paths.items():
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception as e:
                print(f"Font register error {name}: {e}")
        else:
            # Fallback to Times
            fallback = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
            if os.path.exists(fallback):
                pdfmetrics.registerFont(TTFont(name, fallback))

register_fonts()

class NumberedCanvas(canvas.Canvas):
    """Canvas that adds standard page layout and footer if needed"""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


def num_to_vietnamese_words(n: int) -> str:
    """Chuyển số tiền thành chữ Tiếng Việt chuẩn xác"""
    if n == 0: return "Không đồng"
    don_vi = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]
    chu_so = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
    
    def doc_3_so(num, day_du=False):
        t = num // 100
        c = (num % 100) // 10
        d = num % 10
        res = []
        if t > 0 or day_du:
            res.append(chu_so[t] + " trăm")
        if c > 1:
            res.append(chu_so[c] + " mươi")
            if d == 1: res.append("mốt")
            elif d == 4: res.append("tư")
            elif d == 5: res.append("lăm")
            elif d > 0: res.append(chu_so[d])
        elif c == 1:
            res.append("mười")
            if d == 5: res.append("lăm")
            elif d > 0: res.append(chu_so[d])
        elif c == 0 and (t > 0 or day_du) and d > 0:
            res.append("lẻ")
            res.append(chu_so[d])
        elif c == 0 and d > 0:
            res.append(chu_so[d])
        return " ".join(res)

    chunks = []
    temp = n
    while temp > 0:
        chunks.append(temp % 1000)
        temp //= 1000
        
    words = []
    for i in range(len(chunks)-1, -1, -1):
        c = chunks[i]
        if c > 0:
            day_du = (i < len(chunks)-1)
            w = doc_3_so(c, day_du)
            if w:
                words.append(w)
                if don_vi[i]:
                    words.append(don_vi[i])
                    
    res_str = " ".join(words).strip()
    return res_str.capitalize() + " đồng chẵn."


def num_to_english_words(n: int) -> str:
    """Chuyển số tiền thành chữ Tiếng Anh"""
    to_19 = ['Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten',
             'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
    tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
    denom = ['', 'Thousand', 'Million', 'Billion']
    
    def _convert_nn(val):
        if val < 20: return to_19[val]
        for v, d in enumerate(tens):
            if v >= 2:
                if val < (v + 1) * 10:
                    return d + ('' if val % 10 == 0 else ' ' + to_19[val % 10])
        return ''

    def _convert_nnn(val):
        word = ''
        rem = val % 100
        hun = val // 100
        if hun > 0:
            word = to_19[hun] + ' Hundred'
            if rem > 0: word += ' ' + _convert_nn(rem)
        else:
            word = _convert_nn(rem)
        return word

    if n == 0: return "Zero Vietnamese Dong only."
    word = ''
    i = 0
    while n > 0:
        rem = n % 1000
        if rem > 0:
            w = _convert_nnn(rem)
            word = w + (' ' + denom[i] if denom[i] else '') + (' ' + word if word else '')
        n //= 1000
        i += 1
    return word.strip() + " Vietnamese Dong only."


def extract_and_clean_signature(image_path: str, output_sig_path: str, crop_box=None):
    """
    Trích xuất chữ ký từ ảnh hộ chiếu và tách nền trong suốt (Transparent PNG)
    Tự động nhận diện hướng ảnh (đứng hoặc ngang) để cắt đúng vùng chữ ký
    """
    try:
        img = Image.open(image_path).convert("RGBA")
        width, height = img.size
        
        # Nếu không có crop_box, tự động nhận diện theo tỷ lệ ảnh
        if not crop_box:
            aspect_ratio = height / width
            if aspect_ratio >= 1.15:
                # Ảnh mở 2 trang theo chiều dọc (chuẩn phổ biến nhất của hộ chiếu Nga / quốc tế)
                crop_box = (int(width * 0.05), int(height * 0.44), int(width * 0.52), int(height * 0.70))
            elif aspect_ratio <= 0.85:
                # Ảnh chụp ngang 1 trang dữ liệu
                crop_box = (int(width * 0.05), int(height * 0.58), int(width * 0.48), int(height * 0.94))
            else:
                # Ảnh vuông hoặc gần vuông
                crop_box = (int(width * 0.08), int(height * 0.46), int(width * 0.50), int(height * 0.72))
            
        cropped = img.crop(crop_box)
        
        # Chuyển sang Grayscale và tăng độ tương phản để lọc nét mực
        gray = ImageOps.grayscale(cropped)
        gray = ImageOps.autocontrast(gray, cutoff=2)
        
        # Tạo ảnh RGBA trong suốt
        datas = gray.getdata()
        new_data = []
        
        # Ngưỡng tách nét chữ (nét mực đậm < 140, nền giấy trắng > 140)
        for item in datas:
            if item < 135:  # Nét chữ ký
                alpha = int((135 - item) / 135 * 255)
                # Đổi nét chữ thành màu xanh đen / đen tự nhiên
                new_data.append((25, 30, 45, min(255, alpha * 2)))
            else:  # Nền trong suốt
                new_data.append((255, 255, 255, 0))
                
        sig_img = Image.new("RGBA", cropped.size)
        sig_img.putdata(new_data)
        
        # Trim khoảng trắng thừa quanh chữ ký
        bbox = sig_img.getbbox()
        if bbox:
            sig_img = sig_img.crop(bbox)
            
        os.makedirs(os.path.dirname(output_sig_path) or ".", exist_ok=True)
        sig_img.save(output_sig_path, "PNG")
        print(f"✅ Extracted clean signature saved to: {output_sig_path}")
        return True
    except Exception as e:
        print(f"⚠️ Error extracting signature from {image_path}: {e}")
        return False


def build_contract_pdf(output_pdf_path: str, data: dict):
    """
    Tạo tệp PDF Hợp đồng 7 trang chuẩn xác 100% theo mẫu
    """
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    style_header_country = ParagraphStyle(
        'HeaderCountry',
        fontName=FONT_BOLD,
        fontSize=11,
        leading=15,
        alignment=1, # Center
        textTransform='uppercase'
    )
    style_header_slogan = ParagraphStyle(
        'HeaderSlogan',
        fontName=FONT_BOLD,
        fontSize=10,
        leading=14,
        alignment=1
    )
    style_title_vi = ParagraphStyle(
        'TitleVI',
        fontName=FONT_BOLD,
        fontSize=12,
        leading=16,
        alignment=1,
        spaceAfter=2
    )
    style_title_en = ParagraphStyle(
        'TitleEN',
        fontName=FONT_BOLD,
        fontSize=11,
        leading=15,
        alignment=1,
        spaceAfter=4
    )
    style_contract_no = ParagraphStyle(
        'ContractNo',
        fontName=FONT_REGULAR,
        fontSize=9.5,
        leading=13,
        alignment=1,
        spaceAfter=12
    )
    style_basis_vi = ParagraphStyle(
        'BasisVI',
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=12,
        alignment=0, # Left
        leftIndent=10,
        firstLineIndent=-10
    )
    style_basis_en = ParagraphStyle(
        'BasisEN',
        fontName=FONT_ITALIC,
        fontSize=8.5,
        leading=11.5,
        alignment=0,
        leftIndent=10,
        firstLineIndent=-10,
        spaceAfter=5
    )
    style_normal_vi = ParagraphStyle(
        'NormalVI',
        fontName=FONT_REGULAR,
        fontSize=9.5,
        leading=13,
        alignment=4 # Justify
    )
    style_normal_en = ParagraphStyle(
        'NormalEN',
        fontName=FONT_ITALIC,
        fontSize=9,
        leading=12.5,
        alignment=4,
        spaceAfter=4
    )
    style_party_title = ParagraphStyle(
        'PartyTitle',
        fontName=FONT_BOLD,
        fontSize=9.5,
        leading=13,
        spaceBefore=4
    )
    style_article_title = ParagraphStyle(
        'ArticleTitle',
        fontName=FONT_BOLD,
        fontSize=10,
        leading=14,
        spaceBefore=8,
        spaceAfter=2
    )
    style_tbl_header = ParagraphStyle(
        'TblHeader',
        fontName=FONT_BOLD,
        fontSize=8.5,
        leading=11,
        alignment=1
    )
    style_tbl_cell = ParagraphStyle(
        'TblCell',
        fontName=FONT_REGULAR,
        fontSize=8.5,
        leading=11,
        alignment=1
    )
    style_tbl_cell_left = ParagraphStyle(
        'TblCellLeft',
        fontName=FONT_REGULAR,
        fontSize=8.5,
        leading=11,
        alignment=0
    )

    story = []

    # -------------------------------------------------------------
    # PAGE 1: TIÊU NGỮ & BÊN A
    # -------------------------------------------------------------
    story.append(Paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", style_header_country))
    story.append(Paragraph("Độc lập - Tự do - Hạnh phúc", style_header_slogan))
    story.append(Paragraph("---------------", style_header_slogan))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("HỢP ĐỒNG CUNG CẤP DỊCH VỤ TƯ VẤN VÀ LÀM HỒ SƠ VISA", style_title_vi))
    story.append(Paragraph("CONSULTING AND VISA APPLICATION SERVICE CONTRACT", style_title_en))
    story.append(Paragraph(f"Số / No: {data.get('contract_no', '......')}/2026/HĐDV-EASYTRIP", style_contract_no))

    legal_bases = [
        ("Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24/11/2015 và các văn bản hướng dẫn thi hành;",
         "Pursuant to the Civil Code No. 91/2015/QH13 dated November 24, 2015 and its guiding documents;"),
        ("Căn cứ Luật Thương mại số 36/2005/QH11 ngày 14/06/2005 và các văn bản hướng dẫn thi hành;",
         "Pursuant to the Commercial Law No. 36/2005/QH11 dated June 14, 2005 and its guiding documents;"),
        ("Căn cứ Luật Doanh nghiệp số 59/2020/QH14 ngày 17/06/2020 và các văn bản hướng dẫn thi hành;",
         "Pursuant to the Law on Enterprises No. 59/2020/QH14 dated June 17, 2020 and its guiding documents;"),
        ("Căn cứ Luật Nhập cảnh, xuất cảnh, quá cảnh, cư trú của người nước ngoài tại Việt Nam số 47/2014/QH13 ngày 16/06/2014 và các luật sửa đổi, bổ sung liên quan;",
         "Pursuant to the Law on Entry, Exit, Transit, and Residence of Foreigners in Vietnam No. 47/2014/QH13 dated June 16, 2014 and its related amendments;"),
        ("Căn cứ Luật Quản lý thuế số 38/2019/QH14 ngày 13/06/2019 và Luật Thuế giá trị gia tăng số 13/2008/QH12 cùng các văn bản hướng dẫn thi hành;",
         "Pursuant to the Law on Tax Administration No. 38/2019/QH14 dated June 13, 2019 and the Law on Value Added Tax No. 13/2008/QH12 and their guiding documents;"),
        ("Căn cứ Thông tư số 28/2026/TT-BTC ngày 27/03/2026 quy định về phí và lệ phí trong lĩnh vực xuất cảnh, nhập cảnh, quá cảnh, cư trú tại Việt Nam;",
         "Pursuant to Circular No. 28/2026/TT-BTC dated March 27, 2026 regulating fees and charges in the field of entry, exit, transit, and residence in Vietnam;"),
        ("Căn cứ vào nhu cầu và khả năng thực tế của hai Bên.",
         "Pursuant to the demands and actual capacities of both Parties.")
    ]

    for vi, en in legal_bases:
        story.append(Paragraph(f"- {vi}", style_basis_vi))
        story.append(Paragraph(en, style_basis_en))

    story.append(Spacer(1, 3*mm))
    contract_date_vi = data.get('date_vi', 'ngày 16 tháng 06 năm 2026')
    contract_date_en = data.get('date_en', 'June 16, 2026')
    story.append(Paragraph(f"Hôm nay, {contract_date_vi}, tại văn phòng CÔNG TY TNHH CHUYẾN ĐI VÀ THỊ THỰC DỄ DÀNG, chúng tôi gồm có:", style_normal_vi))
    story.append(Paragraph(f"Today, {contract_date_en}, at the office of EASY TRIP AND VISA COMPANY LIMITED, we consist of:", style_normal_en))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("BÊN A: BÊN SỬ DỤNG DỊCH VỤ (KHÁCH HÀNG)", style_party_title))
    story.append(Paragraph("PARTY A: SERVICE USER (CUSTOMER)", style_party_title))
    story.append(Paragraph(f"Tên tổ chức/cá nhân / Name: <b>{data.get('customer_name', 'IRNRNAZAROV ENVER')}</b>", style_normal_vi))
    story.append(Paragraph(f"Số Hộ chiếu / Passport No.: <b>{data.get('passport_no', '767587433')}</b>    Ngày cấp / Date of Issue: <b>{data.get('date_of_issue', '20/05/2022')}</b>", style_normal_vi))
    story.append(Paragraph(f"Quốc tịch / Nationality: <b>{data.get('nationality', 'Nga / Russian')}</b>", style_normal_vi))
    story.append(Paragraph(f"Email: {data.get('email', '.................................................................................')}", style_normal_vi))
    story.append(Paragraph("Đại diện bởi / Represented by: .......................................................", style_normal_vi))

    # -------------------------------------------------------------
    # PAGE 2: BÊN B & ĐIỀU 1
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("BÊN B: BÊN CUNG CẤP DỊCH VỤ", style_party_title))
    story.append(Paragraph("PARTY B: SERVICE PROVIDER", style_party_title))
    story.append(Paragraph("Tên đơn vị / Company Name: <b>CÔNG TY TNHH CHUYẾN ĐI VÀ THỊ THỰC DỄ DÀNG</b>", style_normal_vi))
    story.append(Paragraph("English Name: EASY TRIP AND VISA COMPANY LIMITED", style_normal_en))
    story.append(Paragraph("Mã số thuế / Tax Code: 4202051389", style_normal_vi))
    story.append(Paragraph("Địa chỉ / Address: 21 Phan Vinh, Phường Vĩnh Nguyên, TP. Nha Trang, tỉnh Khánh Hòa, Việt Nam", style_normal_vi))
    story.append(Paragraph("Đại diện / Represented by: Ông/Bà <b>LÝ VIỆT HOÀNG</b> (Mr./Ms. LY VIET HOANG)", style_normal_vi))
    story.append(Paragraph("Chức vụ / Position: Giám đốc / Director", style_normal_vi))
    story.append(Paragraph("Điện thoại / Telephone: 0896916361 - Hotline: 0896916361", style_normal_vi))
    story.append(Paragraph("Tài khoản ngân hàng / Bank Account: VCB Khánh Hòa Số Tài khoản / Account No.: <b>1068582577</b>", style_normal_vi))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Hai Bên cùng thống nhất ký kết Hợp đồng dịch vụ làm thủ tục xin Visa với các điều khoản sau:", style_normal_vi))
    story.append(Paragraph("Both Parties hereby agree to enter into this Visa Service Contract with the following terms and conditions:", style_normal_en))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("ĐIỀU 1: NỘI DUNG DỊCH VỤ", style_article_title))
    story.append(Paragraph("ARTICLE 1: SCOPE OF SERVICES", style_article_title))
    story.append(Paragraph("1.1 Bên A giao và Bên B đồng ý thực hiện dịch vụ tư vấn, chuẩn bị, hoàn thiện bộ hồ sơ để nộp hồ sơ và nộp lệ phí xin cấp Visa (Thị thực) cho Bên A với chi tiết sau:", style_normal_vi))
    story.append(Paragraph("1.1 Party A delegates and Party B agrees to perform the services of consulting preparing, completing, and payment of visa submitting visa applications for Party A as detailed below:", style_normal_en))

    # Table Scope of Services
    tbl_data = [
        [
            Paragraph("<b>STT</b><br/><i>No.</i>", style_tbl_header),
            Paragraph("<b>Họ và tên người xin Visa</b><br/><i>Full name of applicant</i>", style_tbl_header),
            Paragraph("<b>Số Hộ chiếu</b><br/><i>Passport No.</i>", style_tbl_header),
            Paragraph("<b>Cơ quan cấp thị thực</b><br/><i>Issuing Authority</i>", style_tbl_header),
            Paragraph("<b>Mục đích</b><br/><i>Purpose</i>", style_tbl_header),
            Paragraph("<b>Loại Visa</b><br/><i>Visa Type</i>", style_tbl_header)
        ],
        [
            Paragraph("1", style_tbl_cell),
            Paragraph(f"<b>{data.get('customer_name', 'IRNRNAZAROV ENVER')}</b>", style_tbl_cell),
            Paragraph(data.get('passport_no', '767587433'), style_tbl_cell),
            Paragraph("Cục QL XNK - Bộ Công an<br/><i>Immigration Dept - MPS (Vietnam)</i>", style_tbl_cell),
            Paragraph("Du lịch<br/><i>Tourism</i>", style_tbl_cell),
            Paragraph("Thị thực điện tử /<br/><i>EVisa</i>", style_tbl_cell)
        ]
    ]
    t1 = Table(tbl_data, colWidths=[1.0*cm, 3.8*cm, 2.5*cm, 4.2*cm, 2.2*cm, 2.8*cm])
    t1.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(Spacer(1, 2*mm))
    story.append(t1)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("1.2 Nội dung công việc chi tiết của Bên B:", style_normal_vi))
    story.append(Paragraph("1.2 Detailed scope of work of Party B:", style_normal_en))
    story.append(Paragraph("- Tư vấn các quy định pháp lý, điều kiện và thủ tục xin cấp thị thực điện tử của Cục Quản lý Xuất nhập cảnh - Bộ Công an.", style_normal_vi))
    story.append(Paragraph("Consult on legal regulations, conditions, and procedures for e-visa issuance of the Immigration Department - Ministry of Public Security.", style_normal_en))
    story.append(Paragraph("- Hướng dẫn Bên A chuẩn bị giấy tờ, thông tin cá nhân đúng tiêu chuẩn theo yêu cầu.", style_normal_vi))

    # -------------------------------------------------------------
    # PAGE 3: ĐIỀU 2 (CHI PHÍ & THANH TOÁN)
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Guide Party A to prepare documents and personal information up to standard as required.", style_normal_en))
    story.append(Paragraph("- Thực hiện khai trực tuyến thông tin, điền tờ khai và nộp hồ sơ đăng ký.", style_normal_vi))
    story.append(Paragraph("Perform online declaration, fill out application forms, and submit registration documents.", style_normal_en))
    story.append(Paragraph("- Theo dõi tiến trình xử lý của Bộ Công an và bàn giao kết quả thị thực điện tử cho Bên A ngay sau khi có kết quả.", style_normal_vi))
    story.append(Paragraph("Track the processing status by the Ministry of Public Security and hand over the electronic visa results to Party A immediately upon availability.", style_normal_en))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("ĐIỀU 2: GIÁ TRỊ HỢP ĐỒNG VÀ PHƯƠNG THỨC THANH TOÁN", style_article_title))
    story.append(Paragraph("ARTICLE 2: CONTRACT VALUE AND PAYMENT METHOD", style_article_title))
    story.append(Paragraph("2.1 Bảng chi tiết chi phí / Detailed Cost Breakdown:", style_normal_vi))

    service_fee = data.get('service_fee', 757500)
    state_fee = data.get('state_fee', 662500)
    total_amount = service_fee + state_fee

    cost_table_data = [
        [
            Paragraph("<b>STT</b><br/><i>No.</i>", style_tbl_header),
            Paragraph("<b>Nội dung chi phí</b><br/><i>Description of Fees</i>", style_tbl_header),
            Paragraph("<b>Số lượng</b><br/><i>Qty</i>", style_tbl_header),
            Paragraph("<b>Đơn giá (VNĐ)</b><br/><i>Unit Price (VND)</i>", style_tbl_header),
            Paragraph("<b>Thành tiền (VNĐ)</b><br/><i>Total Amount (VND)</i>", style_tbl_header),
        ],
        [
            Paragraph("1", style_tbl_cell),
            Paragraph("Phí dịch vụ tư vấn & làm hồ sơ Visa<br/><i>Service fee for consulting & visa processing</i>", style_tbl_cell_left),
            Paragraph("1", style_tbl_cell),
            Paragraph(f"{service_fee:,}".replace(",", "."), style_tbl_cell),
            Paragraph(f"{service_fee:,}".replace(",", "."), style_tbl_cell),
        ],
        [
            Paragraph("2", style_tbl_cell),
            Paragraph("Lệ phí nộp Nhà nước đăng ký cấp thị thực điện tử (Thu hộ - Chi hộ)<br/>($25 – tỷ giá 26.500VND)<br/><i>State fee for electronic visa registration (Collected & Paid on behalf)<br/>($25 – exchange rate 26,500 VND)</i>", style_tbl_cell_left),
            Paragraph("1", style_tbl_cell),
            Paragraph(f"{state_fee:,}".replace(",", "."), style_tbl_cell),
            Paragraph(f"{state_fee:,}".replace(",", "."), style_tbl_cell),
        ],
        [
            Paragraph("<b>Tổng cộng / Total Amount</b>", style_tbl_header),
            "", "", "",
            Paragraph(f"<b>{total_amount:,}</b>".replace(",", "."), style_tbl_header)
        ]
    ]

    t2 = Table(cost_table_data, colWidths=[1.0*cm, 7.5*cm, 1.6*cm, 3.2*cm, 3.2*cm])
    t2.setStyle(TableStyle([
        ('SPAN', (0, 3), (3, 3)),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(Spacer(1, 2*mm))
    story.append(t2)
    story.append(Spacer(1, 3*mm))

    words_vi = num_to_vietnamese_words(total_amount)
    words_en = num_to_english_words(total_amount)
    story.append(Paragraph(f"Bằng chữ: <b>{words_vi}</b>", style_normal_vi))
    story.append(Paragraph(f"In words: <i>{words_en}</i>", style_normal_en))

    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("2.2 Thuế Giá trị gia tăng (VAT) / Value Added Tax (VAT):", style_normal_vi))
    story.append(Paragraph("- Đơn giá phí dịch vụ nêu trên đã bao gồm thuế GTGT theo quy định của pháp luật Việt Nam. Bên B có trách nhiệm lập và xuất hóa đơn điện tử giá trị gia tăng (GTGT) hợp pháp cho Bên A đối với phần Phí dịch vụ tư vấn & làm hồ sơ trong vòng 03 ngày làm việc kể từ ngày hoàn thành dịch vụ hoặc khi Bên A thanh toán đầy đủ, tùy điều kiện nào đến trước. Bên A có trách nhiệm cung cấp đầy đủ và chính xác thông tin xuất hóa đơn.", style_normal_vi))
    story.append(Paragraph("- The service fee specified above is inclusive of VAT in accordance with Vietnamese tax laws. Party B is responsible for issuing a valid electronic Value Added Tax (VAT) invoice to Party A for the service fee component within 03 working days from the completion of the service or upon full payment by Party A, whichever comes first. Party A is responsible for providing complete and accurate billing information.", style_normal_en))

    # -------------------------------------------------------------
    # PAGE 4: ĐIỀU 3 & ĐIỀU 4
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("- Đối với phần Lệ phí nộp Nhà nước đăng ký cấp thị thực điện tử (Thu hộ - Chi hộ), Bên B sẽ cung cấp chứng từ, biên lai lệ phí của Bộ Công an/Cổng dịch vụ công cho Bên A và phần này không chịu thuế GTGT của Bên B.", style_normal_vi))
    story.append(Paragraph("- For the State fee for electronic visa registration (Collected & Paid on behalf), Party B shall provide the official receipt from the Ministry of Public Security / Public Service Portal to Party A, and this component is not subject to VAT by Party B.", style_normal_en))

    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("2.3 Tiến độ thanh toán / Payment Schedule:", style_normal_vi))
    story.append(Paragraph("- Bên A thanh toán 100% tổng giá trị hợp đồng ngay sau khi ký kết Hợp đồng này.", style_normal_vi))
    story.append(Paragraph("- Party A shall pay 100% of the total contract value immediately upon signing this Contract.", style_normal_en))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("ĐIỀU 3: QUYỀN VÀ NGHĨA VỤ CỦA BÊN A", style_article_title))
    story.append(Paragraph("ARTICLE 3: RIGHTS AND OBLIGATIONS OF PARTY A", style_article_title))
    story.append(Paragraph("3.1 Cung cấp đầy đủ, trung thực, chính xác và kịp thời các hồ sơ, thông tin, giấy tờ theo hướng dẫn của Bên B. Bên A tự chịu hoàn toàn trách nhiệm pháp lý trước pháp luật về tính chân thật, hợp pháp của các tài liệu đã cung cấp.", style_normal_vi))
    story.append(Paragraph("3.1 Provide fully, honestly, accurately, and timely all dossiers, information, and documents as guided by Party B. Party A shall be solely and fully liable under the law for the authenticity and legality of the provided documents.", style_normal_en))
    story.append(Paragraph("3.2 Thanh toán đầy đủ và đúng hạn các khoản phí theo quy định tại Điều 2 của Hợp đồng này.", style_normal_vi))
    story.append(Paragraph("3.2 Pay fully and on time all fees specified in Article 2 of this Contract.", style_normal_en))
    story.append(Paragraph("3.3 Có mặt đúng giờ hoặc phối hợp cung cấp sinh trắc học, thông tin bổ sung khi có yêu cầu từ Cục Quản lý Xuất nhập cảnh - Bộ Công an hoặc cơ quan có thẩm quyền của Nhà nước.", style_normal_vi))
    story.append(Paragraph("3.3 Be present on time or coordinate to provide biometrics and additional information upon request from the Immigration Department - Ministry of Public Security or competent State authorities.", style_normal_en))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("ĐIỀU 4: QUYỀN VÀ NGHĨA VỤ CỦA BÊN B", style_article_title))
    story.append(Paragraph("ARTICLE 4: RIGHTS AND OBLIGATIONS OF PARTY B", style_article_title))
    story.append(Paragraph("4.1 Được quyền sử dụng thông tin trên hộ chiếu, thông tin khác của bên A để thực hiện công việc tư vấn và chuẩn bị hồ sơ đăng ký các dịch vụ công của Nhà Nước Việt Nam.", style_normal_vi))
    story.append(Paragraph("4.1 To be authorized to use Party A's passport information and other information to perform consultancy services and prepare application dossiers for public services of the State of Vietnam.", style_normal_en))
    story.append(Paragraph("4.2 Bảo quản cẩn thận, an toàn các giấy tờ gốc, thông tin cá nhân do Bên A bàn giao trong quá trình thực hiện hợp đồng.", style_normal_vi))
    story.append(Paragraph("4.2 Carefully and safely preserve the original documents and personal information handed over by Party A during the contract execution.", style_normal_en))
    story.append(Paragraph("4.3 Bảo mật tuyệt đối mọi thông tin cá nhân, thông tin hồ sơ của Bên A và không tiết lộ cho bất kỳ bên thứ ba nào khi chưa có sự đồng ý bằng văn bản của Bên A, trừ trường hợp cung cấp cho Cục Quản lý Xuất nhập cảnh - Bộ Công an để đăng ký cấp thị thực điện tử hoặc theo yêu cầu của pháp luật.", style_normal_vi))
    story.append(Paragraph("4.3 Keep strictly confidential all personal and dossier information of Party A and not disclose it to any third party without Party A's prior written consent, except for submission to the Immigration Department - Ministry of Public Security for e-visa registration or as required by law.", style_normal_en))

    # -------------------------------------------------------------
    # PAGE 5: ĐIỀU 5 & ĐIỀU 6
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("4.4 Thông báo kịp thời cho Bên A về tiến độ và kết quả hồ sơ. Bàn giao đầy đủ kết quả dịch vụ công ngay sau khi được Nhà Nước Việt Nam ban hành.", style_normal_vi))
    story.append(Paragraph("4.4 Promptly notify Party A of the progress and results of the application. Fully hand over the results of the public service immediately upon issuance by the State of Vietnam.", style_normal_en))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("ĐIỀU 5: ĐIỀU KHOẢN VỀ KẾT QUẢ DỊCH VỤ VÀ HOÀN PHÍ", style_article_title))
    story.append(Paragraph("ARTICLE 5: SERVICE RESULTS AND REFUND POLICY", style_article_title))
    story.append(Paragraph("5.1 Hai Bên hiểu rõ rằng quyền quyết định cấp hoặc từ chối cấp thị thực điện tử hoàn toàn thuộc thẩm quyền của Cục Quản lý Xuất nhập cảnh - Bộ Công an nước Cộng hòa Xã hội Chủ nghĩa Việt Nam. Bên B không quyết định và không bảo đảm tuyệt đối kết quả cấp thị thực.", style_normal_vi))
    story.append(Paragraph("5.1 Both Parties clearly understand that the decision to grant or refuse the electronic visa belongs solely to the authority of the Immigration Department - Ministry of Public Security of the Socialist Republic of Vietnam. Party B does not decide and does not guarantee absolute visa issuance results.", style_normal_en))
    story.append(Paragraph("5.2 Xử lý khi rớt thị thực do lỗi khách quan (từ phía Cục Quản lý Xuất nhập cảnh - Bộ Công an từ chối mà không do lỗi của Bên nào):", style_normal_vi))
    story.append(Paragraph("5.2 Handling visa rejection due to objective reasons (rejection by the Immigration Department - Ministry of Public Security without fault of either Party):", style_normal_en))
    story.append(Paragraph("- Lệ phí nộp Nhà nước đăng ký cấp thị thực điện tử sẽ không được hoàn lại (theo quy định của Bộ Công an và Thông tư số 28/2026/TT-BTC).", style_normal_vi))
    story.append(Paragraph("The State fee for electronic visa registration will not be refunded (in accordance with the Ministry of Public Security regulations and Circular No. 28/2026/TT-BTC).", style_normal_en))
    story.append(Paragraph(f"- Bên B sẽ hoàn trả lại 100% Phí dịch vụ tư vấn & làm hồ sơ ({service_fee:,} VNĐ) cho Bên A trong vòng 05 ngày làm việc kể từ ngày nhận được thông báo từ chối cấp thị thực.".replace(",", "."), style_normal_vi))
    story.append(Paragraph(f"Party B shall refund 100% of the Service Fee (VND {service_fee:,}) to Party A within 05 working days from the date of receiving the visa rejection notice.".replace(",", "."), style_normal_en))
    story.append(Paragraph("5.3 Trường hợp Bên A đơn phương hủy hợp đồng sau khi Bên B đã tiến hành xử lý hồ sơ hoặc nộp lệ phí, phí dịch vụ và Lệ phí nộp Nhà nước đăng ký cấp thị thực điện tử sẽ không được hoàn lại.", style_normal_vi))
    story.append(Paragraph("5.3 In case Party A unilaterally terminates the contract after Party B has commenced processing the dossier or paid the fees, the service fee and the State fee for electronic visa registration shall not be refunded.", style_normal_en))
    story.append(Paragraph("5.4 Trường hợp Bên A cung cấp thông tin, tài liệu giả mạo hoặc sai sự thật dẫn đến việc hồ sơ bị từ chối hoặc bị xử lý theo pháp luật:", style_normal_vi))
    story.append(Paragraph("5.4 In case Party A provides forged or untruthful information or documents, leading to visa rejection or legal actions:", style_normal_en))
    story.append(Paragraph("- Bên B có quyền đơn phương chấm dứt hợp đồng ngay lập tức.", style_normal_vi))
    story.append(Paragraph("Party B has the right to unilaterally terminate the contract immediately.", style_normal_en))
    story.append(Paragraph("- Bên A không được hoàn lại bất kỳ khoản phí nào và phải tự chịu hoàn toàn trách nhiệm trước pháp luật.", style_normal_vi))
    story.append(Paragraph("Party A shall not be refunded any fees and must bear full legal responsibility.", style_normal_en))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("ĐIỀU 6: BẤT KHẢ KHÁNG VÀ GIỚI HẠN TRÁCH NHIỆM", style_article_title))
    story.append(Paragraph("ARTICLE 6: FORCE MAJEURE AND LIMITATION OF LIABILITY", style_article_title))

    # -------------------------------------------------------------
    # PAGE 6: ĐIỀU 7 & ĐIỀU 8
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("6.1 Sự kiện bất khả kháng là sự kiện xảy ra một cách khách quan, không thể lường trước được và không thể khắc phục được mặc dù đã áp dụng mọi biện pháp cần thiết và khả năng cho phép, bao gồm nhưng không giới hạn ở: thiên tai, dịch bệnh, chiến tranh, sự thay đổi đột ngột về chính sách xuất nhập cảnh của Chính phủ Việt Nam hoặc quốc gia liên quan, việc Cục Quản lý Xuất nhập cảnh - Bộ Công an tạm ngừng hoạt động hoặc đóng cửa biên giới.", style_normal_vi))
    story.append(Paragraph("6.1 A Force Majeure event is an event that occurs objectively, unpredictably, and irremediably despite all necessary and permissible measures being taken, including but not limited to: natural disasters, epidemics, wars, sudden changes in immigration policies of the Vietnamese Government or related countries, temporary suspension of operations of the Immigration Department - Ministry of Public Security, or border closures.", style_normal_en))
    story.append(Paragraph("6.2 Trong trường hợp xảy ra Sự kiện bất khả kháng dẫn đến việc chậm trễ hoặc không thể thực hiện nghĩa vụ hợp đồng, bên bị ảnh hưởng sẽ được miễn trừ trách nhiệm và không phải bồi thường thiệt hại, với điều kiện phải thông báo cho bên kia bằng văn bản trong vòng 03 ngày kể từ ngày xảy ra sự kiện. Hai bên sẽ cùng thương lượng để tìm giải pháp khắc phục.", style_normal_vi))
    story.append(Paragraph("6.2 In the event of a Force Majeure event leading to delay or inability to perform contractual obligations, the affected party shall be exempted from liability and shall not compensate for damages, provided that the other party is notified in writing within 03 days from the occurrence of the event. Both parties shall negotiate to find a remedy.", style_normal_en))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("ĐIỀU 7: GIẢI QUYẾT TRANH CHẤP", style_article_title))
    story.append(Paragraph("ARTICLE 7: DISPUTE RESOLUTION", style_article_title))
    story.append(Paragraph("7.1 Mọi tranh chấp phát sinh từ hoặc liên quan đến Hợp đồng này trước hết sẽ được hai Bên giải quyết thông qua thương lượng, hòa giải trên tinh thần hợp tác và cùng có lợi.", style_normal_vi))
    story.append(Paragraph("7.1 Any dispute arising from or related to this Contract shall first be resolved by both Parties through negotiation and conciliation in a cooperative and mutually beneficial spirit.", style_normal_en))
    story.append(Paragraph("7.2 Trường hợp tranh chấp không thể giải quyết bằng thương lượng trong vòng 30 ngày kể từ ngày phát sinh, một trong hai Bên có quyền đưa vụ việc ra giải quyết tại Tòa án nhân dân có thẩm quyền tại Thành phố Nha Trang, tỉnh Khánh Hòa, Việt Nam để giải quyết theo quy định của pháp luật Việt Nam.", style_normal_vi))
    story.append(Paragraph("7.2 In case the dispute cannot be resolved through negotiation within 30 days from its occurrence, either Party has the right to refer the dispute to the competent People's Court in Nha Trang City, Khanh Hoa Province, Vietnam for resolution in accordance with Vietnamese law.", style_normal_en))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("ĐIỀU 8: ĐIỀU KHOẢN CHUNG", style_article_title))
    story.append(Paragraph("ARTICLE 8: GENERAL PROVISIONS", style_article_title))
    story.append(Paragraph("8.1 Hợp đồng này được điều chỉnh và giải thích theo quy định của pháp luật nước Cộng hòa Xã hội Chủ nghĩa Việt Nam.", style_normal_vi))
    story.append(Paragraph("8.1 This Contract shall be governed by and construed in accordance with the laws of the Socialist Republic of Vietnam.", style_normal_en))
    story.append(Paragraph("8.2 Hợp đồng này có hiệu lực kể từ ngày ký và tự động thanh lý sau khi Bên B bàn giao kết quả thị thực điện tử cho Bên A và Bên A hoàn tất nghĩa vụ thanh toán.", style_normal_vi))
    story.append(Paragraph("8.2 This Contract shall take effect from the date of signing and shall be automatically liquidated after Party B hands over the electronic visa results to Party A and Party A completes the payment obligations.", style_normal_en))

    # -------------------------------------------------------------
    # PAGE 7: KÝ TÊN & ĐÓNG DẤU
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("8.3 Hợp đồng được lập thành 02 (hai) bản bằng tiếng Việt và tiếng Anh. Mỗi bên giữ 01 (một) bản có giá trị pháp lý như nhau. Bản tiếng Việt sẽ được ưu tiên áp dụng nếu có bất kỳ sự khác biệt nào về cách giải thích giữa hai ngôn ngữ.", style_normal_vi))
    story.append(Paragraph("8.3 The Contract is prepared in 02 (two) copies in both Vietnamese and English. Each party shall keep 01 (one) copy with equal legal validity. The Vietnamese version shall prevail in case of any discrepancy in interpretation between the two languages.", style_normal_en))

    story.append(Spacer(1, 10*mm))

    sig_img_path = data.get('signature_image_path')
    sig_element = Spacer(1, 2.0*cm)
    if sig_img_path and os.path.exists(sig_img_path):
        # Giữ tỉ lệ nét chữ ký tự nhiên, nhỏ gọn 3.8cm x 1.6cm
        sig_element = RLImage(sig_img_path, width=3.8*cm, height=1.6*cm)

    # Bảng chữ ký 2 bên
    sig_tbl_data = [
        [
            Paragraph("<b>ĐẠI DIỆN BÊN A</b><br/><i>REPRESENTATIVE OF PARTY A</i>", style_tbl_header),
            Paragraph("<b>ĐẠI DIỆN BÊN B</b><br/><b>CÔNG TY TNHH CHUYẾN ĐI VÀ THỊ THỰC DỄ DÀNG</b><br/><i>REPRESENTATIVE OF PARTY B<br/>EASY TRIP AND VISA CO., LTD</i>", style_tbl_header)
        ],
        [
            sig_element,
            Spacer(1, 2.0*cm)
        ],
        [
            Paragraph(f"<b>{data.get('customer_name', 'IRNRNAZAROV ENVER')}</b>", style_tbl_header),
            Paragraph("<b>LÝ VIỆT HOÀNG</b>", style_tbl_header)
        ]
    ]

    t_sig = Table(sig_tbl_data, colWidths=[8.5*cm, 8.5*cm])
    t_sig.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]))

    story.append(t_sig)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"🎉 Generated 7-Page Contract PDF successfully: {output_pdf_path}")
    return output_pdf_path

if __name__ == "__main__":
    # Quick Test with IRNRNAZAROV ENVER
    os.makedirs("output_contracts", exist_ok=True)
    sample_data = {
        "contract_no": "089",
        "date_vi": "ngày 16 tháng 06 năm 2026",
        "date_en": "June 16, 2026",
        "customer_name": "IRNRNAZAROV ENVER",
        "passport_no": "767587433",
        "date_of_issue": "20/05/2022",
        "nationality": "Nga / Russian",
        "service_fee": 757500,
        "state_fee": 662500,
        "signature_image_path": None
    }
    build_contract_pdf("output_contracts/Sample_Contract_IRNRNAZAROV_ENVER.pdf", sample_data)
