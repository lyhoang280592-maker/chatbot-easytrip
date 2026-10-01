$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$workDir = "C:\Users\PC\Downloads\chatbot-easytrip-main\chatbot-easytrip"
$buildDir = Join-Path $workDir "temp_build_mau01"
$outputDocx = Join-Path $workDir "Mau_so_01_PLI_Giai_trinh_Lao_dong_nuoc_ngoai.docx"
$desktopDocx = "C:\Users\PC\Desktop\Mau_so_01_PLI_Giai_trinh_Lao_dong_nuoc_ngoai.docx"

if (Test-Path $buildDir) {
    Remove-Item $buildDir -Recurse -Force
}
New-Item -ItemType Directory -Path (Join-Path $buildDir "_rels") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $buildDir "word\_rels") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $buildDir "docProps") -Force | Out-Null

# 1. [Content_Types].xml
$contentTypes = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
'@
[System.IO.File]::WriteAllText((Join-Path $buildDir "[Content_Types].xml"), $contentTypes, [System.Text.Encoding]::UTF8)

# 2. _rels/.rels
$rootRels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
'@
[System.IO.File]::WriteAllText((Join-Path $buildDir "_rels\.rels"), $rootRels, [System.Text.Encoding]::UTF8)

# 3. word/_rels/document.xml.rels
$docRels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/>
</Relationships>
'@
[System.IO.File]::WriteAllText((Join-Path $buildDir "word\_rels\document.xml.rels"), $docRels, [System.Text.Encoding]::UTF8)

# 4. word/fontTable.xml
$fontTable = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:fonts xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:font w:name="Times New Roman">
    <w:panose1 w:val="02020603050405020304"/>
    <w:charset w:val="00"/>
    <w:family w:val="roman"/>
    <w:pitch w:val="variable"/>
  </w:font>
</w:fonts>
'@
[System.IO.File]::WriteAllText((Join-Path $buildDir "word\fontTable.xml"), $fontTable, [System.Text.Encoding]::UTF8)

# 5. word/settings.xml
$settings = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:defaultTabStop w:val="720"/>
  <w:characterSpacingControl w:val="doNotCompress"/>
</w:settings>
'@
[System.IO.File]::WriteAllText((Join-Path $buildDir "word\settings.xml"), $settings, [System.Text.Encoding]::UTF8)

# 6. word/styles.xml
$styles = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
        <w:sz w:val="26"/>
        <w:szCs w:val="26"/>
        <w:lang w:val="vi-VN"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:line="276" w:lineRule="auto" w:after="100"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
</w:styles>
'@
[System.IO.File]::WriteAllText((Join-Path $buildDir "word\styles.xml"), $styles, [System.Text.Encoding]::UTF8)

# 7. docProps/core.xml & app.xml
$core = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Mẫu số 01/PLI - Giải trình nhu cầu sử dụng lao động nước ngoài</dc:title>
  <dc:creator>EasyTrip Admin</dc:creator>
</cp:coreProperties>
'@
[System.IO.File]::WriteAllText((Join-Path $buildDir "docProps\core.xml"), $core, [System.Text.Encoding]::UTF8)

$app = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Word</Application>
</Properties>
'@
[System.IO.File]::WriteAllText((Join-Path $buildDir "docProps\app.xml"), $app, [System.Text.Encoding]::UTF8)

# 8. word/document.xml - Fully structured according to Decree 152/2020/ND-CP & Decree 70/2023/ND-CP
$docXml = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <!-- Top Right Note: Mẫu số 01/PLI -->
    <w:p>
      <w:pPr>
        <w:jc w:val="right"/>
        <w:spacing w:after="120"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:i/>
          <w:sz w:val="22"/>
        </w:rPr>
        <w:t>Mẫu số 01/PLI</w:t>
      </w:r>
    </w:p>

    <!-- Header Table: 2 Columns -->
    <w:tbl>
      <w:tblPr>
        <w:tblW w:w="0" w:type="auto"/>
        <w:tblBorders>
          <w:top w:val="none"/>
          <w:left w:val="none"/>
          <w:bottom w:val="none"/>
          <w:right w:val="none"/>
          <w:insideH w:val="none"/>
          <w:insideV w:val="none"/>
        </w:tblBorders>
      </w:tblPr>
      <w:tblGrid>
        <w:gridCol w:w="4600"/>
        <w:gridCol w:w="5000"/>
      </w:tblGrid>
      <w:tr>
        <w:tc>
          <w:tcPr>
            <w:tcW w:w="4600" w:type="dxa"/>
          </w:tcPr>
          <w:p>
            <w:pPr>
              <w:jc w:val="center"/>
              <w:spacing w:after="40"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:b/>
                <w:sz w:val="23"/>
              </w:rPr>
              <w:t>CÔNG TY TNHH ĐẦU TƯ</w:t>
            </w:r>
          </w:p>
          <w:p>
            <w:pPr>
              <w:jc w:val="center"/>
              <w:spacing w:after="40"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:b/>
                <w:sz w:val="23"/>
              </w:rPr>
              <w:t>DỊCH VỤ S&amp;J</w:t>
            </w:r>
          </w:p>
          <w:p>
            <w:pPr>
              <w:jc w:val="center"/>
              <w:spacing w:after="40"/>
            </w:pPr>
            <w:r>
              <w:t>Số: 01/BC-GTNS</w:t>
            </w:r>
          </w:p>
        </w:tc>
        <w:tc>
          <w:tcPr>
            <w:tcW w:w="5000" w:type="dxa"/>
          </w:tcPr>
          <w:p>
            <w:pPr>
              <w:jc w:val="center"/>
              <w:spacing w:after="40"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:b/>
                <w:sz w:val="23"/>
              </w:rPr>
              <w:t>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</w:t>
            </w:r>
          </w:p>
          <w:p>
            <w:pPr>
              <w:jc w:val="center"/>
              <w:spacing w:after="40"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:b/>
                <w:sz w:val="24"/>
                <w:u w:val="single"/>
              </w:rPr>
              <w:t>Độc lập - Tự do - Hạnh phúc</w:t>
            </w:r>
          </w:p>
          <w:p>
            <w:pPr>
              <w:jc w:val="center"/>
              <w:spacing w:after="40"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:i/>
                <w:sz w:val="23"/>
              </w:rPr>
              <w:t>Khánh Hòa, ngày 05 tháng 09 năm 2026</w:t>
            </w:r>
          </w:p>
        </w:tc>
      </w:tr>
    </w:tbl>

    <!-- Main Title -->
    <w:p>
      <w:pPr>
        <w:jc w:val="center"/>
        <w:spacing w:before="240" w:after="60"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
          <w:sz w:val="28"/>
        </w:rPr>
        <w:t>BÁO CÁO GIẢI TRÌNH</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:jc w:val="center"/>
        <w:spacing w:before="0" w:after="200"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
          <w:sz w:val="26"/>
        </w:rPr>
        <w:t>NHU CẦU SỬ DỤNG NGƯỜI LAO ĐỘNG NƯỚC NGOÀI</w:t>
      </w:r>
    </w:p>

    <!-- Recipient -->
    <w:p>
      <w:pPr>
        <w:jc w:val="center"/>
        <w:spacing w:after="200"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>Kính gửi: </w:t>
      </w:r>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>Ủy ban nhân dân tỉnh Khánh Hòa</w:t>
      </w:r>
      <w:pPr>
        <w:jc w:val="center"/>
      </w:pPr>
    </w:p>
    <w:p>
      <w:pPr>
        <w:jc w:val="center"/>
        <w:spacing w:after="240"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:i/>
        </w:rPr>
        <w:t>(Đồng kính gửi: Sở Lao động - Thương binh và Xã hội tỉnh Khánh Hòa)</w:t>
      </w:r>
    </w:p>

    <!-- Section 1 -->
    <w:p>
      <w:pPr>
        <w:spacing w:after="80"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>1. Thông tin về doanh nghiệp/tổ chức:</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>a) Tên doanh nghiệp/tổ chức: </w:t>
      </w:r>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>CÔNG TY TNHH ĐẦU TƯ DỊCH VỤ S&amp;J</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>b) Loại hình doanh nghiệp: Công ty trách nhiệm hữu hạn</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>c) Mã số doanh nghiệp/Mã số thuế: </w:t>
      </w:r>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>4202008263</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>d) Địa chỉ trụ sở chính: 61 Võ Trứ, phường Tân Lập, thành phố Nha Trang, tỉnh Khánh Hòa</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>đ) Số điện thoại: 0334900785         Email: shopmegau.co@gmail.com</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>e) Lĩnh vực hoạt động/Ngành nghề kinh doanh chính: Dịch vụ nhà hàng, ăn uống, ẩm thực và dịch vụ du lịch giải trí.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="120"/>
      </w:pPr>
      <w:r>
        <w:t>g) Người đại diện theo pháp luật: </w:t>
      </w:r>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>Bà Lý Kim Anh</w:t>
      </w:r>
      <w:r>
        <w:t>               Chức danh: </w:t>
      </w:r>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>Giám đốc</w:t>
      </w:r>
    </w:p>

    <!-- Section 2 -->
    <w:p>
      <w:pPr>
        <w:spacing w:after="80"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>2. Tình hình sử dụng lao động hiện nay của doanh nghiệp:</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>- Tổng số lao động đang làm việc tại doanh nghiệp: 15 người.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>  + Số lao động Việt Nam: 14 người.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="120"/>
      </w:pPr>
      <w:r>
        <w:t>  + Số lao động nước ngoài: 01 người.</w:t>
      </w:r>
    </w:p>

    <!-- Section 3 -->
    <w:p>
      <w:pPr>
        <w:spacing w:after="80"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>3. Giải trình nhu cầu sử dụng người lao động nước ngoài:</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>3.1. Vị trí công việc: </w:t>
      </w:r>
      <w:r>
        <w:t>Giám đốc điều hành</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>- Chức danh công việc: </w:t>
      </w:r>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>Giám đốc điều hành - CEO</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>- Số lượng: 01 người.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>- Thời hạn làm việc: Từ ngày </w:t>
      </w:r>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>07/09/2026</w:t>
      </w:r>
      <w:r>
        <w:t> đến ngày </w:t>
      </w:r>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>11/09/2028</w:t>
      </w:r>
      <w:r>
        <w:t> (02 năm).</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:t>- Hình thức làm việc: Thực hiện hợp đồng lao động.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="80"/>
      </w:pPr>
      <w:r>
        <w:t>- Địa điểm làm việc: 61 Võ Trứ, phường Tân Lập, thành phố Nha Trang, tỉnh Khánh Hòa.</w:t>
      </w:r>
    </w:p>

    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>3.2. Mô tả công việc cụ thể:</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="720"/>
        <w:spacing w:after="40"/>
      </w:pPr>
      <w:r>
        <w:t>• Điều hành chiến lược: Xây dựng và thực thi các chiến lược kinh doanh toàn diện, đảm bảo toàn bộ hệ thống nhà hàng tuân thủ nghiêm ngặt các tiêu chuẩn vận hành F&amp;B quốc tế.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="720"/>
        <w:spacing w:after="40"/>
      </w:pPr>
      <w:r>
        <w:t>• Quản lý đối ngoại: Đóng vai trò là cầu nối trực tiếp để đàm phán, làm việc và duy trì mối quan hệ chiến lược với các đối tác cung ứng, khách hàng cao cấp và các đoàn khách du lịch quốc tế.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="720"/>
        <w:spacing w:after="40"/>
      </w:pPr>
      <w:r>
        <w:t>• Kiểm soát chất lượng: Trực tiếp giám sát chất lượng dịch vụ của chuỗi nhà hàng, đảm bảo trải nghiệm ẩm thực và không gian văn hóa đáp ứng kỳ vọng khắt khe của tệp khách hàng quốc tế.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="720"/>
        <w:spacing w:after="40"/>
      </w:pPr>
      <w:r>
        <w:t>• Tối ưu hóa tài chính: Quản trị ngân sách, phân tích chỉ số kinh doanh chuyên sâu (Food cost, Labor cost) và lập báo cáo tài chính định kỳ bằng ngoại ngữ (tiếng Hàn và tiếng Anh).</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="720"/>
        <w:spacing w:after="80"/>
      </w:pPr>
      <w:r>
        <w:t>• Phát triển nhân sự: Xây dựng môi trường làm việc đa văn hóa, trực tiếp tuyển dụng và đào tạo đội ngũ quản lý cấp trung nhằm thích ứng với các chuẩn mực dịch vụ toàn cầu.</w:t>
      </w:r>
    </w:p>

    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>3.3. Yêu cầu về trình độ và kinh nghiệm:</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="720"/>
        <w:spacing w:after="40"/>
      </w:pPr>
      <w:r>
        <w:t>• Kinh nghiệm chuyên môn: Có tối thiểu từ 03 - 05 năm kinh nghiệm thực tế ở vị trí Quản lý cấp cao, Giám đốc điều hành trong lĩnh vực F&amp;B, Nhà hàng - Khách sạn hoặc Dịch vụ quốc tế.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="720"/>
        <w:spacing w:after="40"/>
      </w:pPr>
      <w:r>
        <w:t>• Kỹ năng ngoại ngữ: Sử dụng thành thạo tiếng Hàn (nghe, nói, đọc, viết chuyên sâu) để làm việc trực tiếp với đối tác Hàn Quốc; đồng thời giao tiếp thành thạo bằng tiếng Anh.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="720"/>
        <w:spacing w:after="40"/>
      </w:pPr>
      <w:r>
        <w:t>• Am hiểu văn hóa thị trường: Am hiểu sâu sắc về văn hóa, phong cách sống, tiêu chuẩn và thị hiếu tiêu dùng của khách hàng quốc tế và thị trường Hàn Quốc.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="720"/>
        <w:spacing w:after="80"/>
      </w:pPr>
      <w:r>
        <w:t>• Năng lực quản trị: Năng lực đọc hiểu báo cáo tài chính P&amp;L, hoạch định kế hoạch kinh doanh và quản trị hệ thống nhân sự đa văn hóa.</w:t>
      </w:r>
    </w:p>

    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="60"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>3.4. Lý do không tuyển dụng được người lao động Việt Nam vào vị trí này:</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="720"/>
        <w:spacing w:after="60"/>
        <w:jc w:val="both"/>
      </w:pPr>
      <w:r>
        <w:t>Công ty đã thực hiện thông báo đăng tuyển dụng lao động Việt Nam vào vị trí Giám đốc điều hành trên Trang thông tin điện tử của Trung tâm Dịch vụ việc làm tỉnh Khánh Hòa theo đúng quy định tại Nghị định số 70/2023/NĐ-CP. Tuy nhiên, sau thời gian đăng tuyển, Công ty không nhận được hồ sơ ứng viên người Việt Nam đáp ứng đầy đủ đồng thời các tiêu chí đặc thù: kinh nghiệm điều hành chuỗi ẩm thực quốc tế, am hiểu sâu sắc văn hóa thị hiếu Hàn Quốc và sử dụng thành thạo song ngữ Hàn - Anh ở cấp độ quản trị chiến lược.</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="720"/>
        <w:spacing w:after="120"/>
        <w:jc w:val="both"/>
      </w:pPr>
      <w:r>
        <w:t>Do đó, để đảm bảo duy trì hoạt động kinh doanh, nâng cao chất lượng dịch vụ theo tiêu chuẩn quốc tế và phục vụ tốt du khách nước ngoài tại Nha Trang - Khánh Hòa, Công ty kính đề nghị Quý cơ quan xem xét, chấp thuận nhu cầu sử dụng 01 người lao động nước ngoài cho vị trí công việc nêu trên.</w:t>
      </w:r>
    </w:p>

    <!-- Section 4 -->
    <w:p>
      <w:pPr>
        <w:spacing w:after="80"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
        </w:rPr>
        <w:t>4. Cam kết của doanh nghiệp:</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:ind w:left="360"/>
        <w:spacing w:after="160"/>
        <w:jc w:val="both"/>
      </w:pPr>
      <w:r>
        <w:t>Doanh nghiệp cam kết toàn bộ thông tin giải trình nêu trên là đúng sự thật và hoàn toàn chịu trách nhiệm trước pháp luật Việt Nam về tính chính xác, trung thực của các nội dung đã báo cáo./.</w:t>
      </w:r>
    </w:p>

    <!-- Footer Signature Table: 2 Columns -->
    <w:tbl>
      <w:tblPr>
        <w:tblW w:w="0" w:type="auto"/>
        <w:tblBorders>
          <w:top w:val="none"/>
          <w:left w:val="none"/>
          <w:bottom w:val="none"/>
          <w:right w:val="none"/>
          <w:insideH w:val="none"/>
          <w:insideV w:val="none"/>
        </w:tblBorders>
      </w:tblPr>
      <w:tblGrid>
        <w:gridCol w:w="4600"/>
        <w:gridCol w:w="5000"/>
      </w:tblGrid>
      <w:tr>
        <w:tc>
          <w:tcPr>
            <w:tcW w:w="4600" w:type="dxa"/>
          </w:tcPr>
          <w:p>
            <w:pPr>
              <w:spacing w:after="40"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:b/>
                <w:i/>
                <w:sz w:val="23"/>
              </w:rPr>
              <w:t>Nơi nhận:</w:t>
            </w:r>
          </w:p>
          <w:p>
            <w:pPr>
              <w:spacing w:after="30"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:sz w:val="22"/>
              </w:rPr>
              <w:t>- Như Kính gửi;</w:t>
            </w:r>
          </w:p>
          <w:p>
            <w:pPr>
              <w:spacing w:after="30"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:sz w:val="22"/>
              </w:rPr>
              <w:t>- Sở LĐ-TB&amp;XH tỉnh Khánh Hòa;</w:t>
            </w:r>
          </w:p>
          <w:p>
            <w:pPr>
              <w:spacing w:after="30"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:sz w:val="22"/>
              </w:rPr>
              <w:t>- Lưu: VT, HS.</w:t>
            </w:r>
          </w:p>
        </w:tc>
        <w:tc>
          <w:tcPr>
            <w:tcW w:w="5000" w:type="dxa"/>
          </w:tcPr>
          <w:p>
            <w:pPr>
              <w:jc w:val="center"/>
              <w:spacing w:after="40"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:b/>
                <w:sz w:val="24"/>
              </w:rPr>
              <w:t>ĐẠI DIỆN DOANH NGHIỆP</w:t>
            </w:r>
          </w:p>
          <w:p>
            <w:pPr>
              <w:jc w:val="center"/>
              <w:spacing w:after="40"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:i/>
                <w:sz w:val="22"/>
              </w:rPr>
              <w:t>(Ký, ghi rõ họ tên và đóng dấu)</w:t>
            </w:r>
          </w:p>
          <w:p>
            <w:pPr>
              <w:jc w:val="center"/>
              <w:spacing w:before="1200" w:after="40"/>
            </w:pPr>
            <w:r>
              <w:rPr>
                <w:b/>
                <w:sz w:val="24"/>
              </w:rPr>
              <w:t>LÝ KIM ANH</w:t>
            </w:r>
          </w:p>
        </w:tc>
      </w:tr>
    </w:tbl>

    <!-- Page Setup: Standard A4 -->
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1701" w:header="720" w:footer="720" w:gutter="0"/>
      <w:cols w:space="720"/>
      <w:docGrid w:linePitch="360"/>
    </w:sectPr>
  </w:body>
</w:document>
'@
[System.IO.File]::WriteAllText((Join-Path $buildDir "word\document.xml"), $docXml, [System.Text.Encoding]::UTF8)

# 9. Compress build folder to docx
if (Test-Path $outputDocx) {
    Remove-Item $outputDocx -Force
}
[System.IO.Compression.ZipFile]::CreateFromDirectory($buildDir, $outputDocx)

# Copy to Desktop for immediate access
Copy-Item $outputDocx -Destination $desktopDocx -Force

# Clean up build dir
Remove-Item $buildDir -Recurse -Force

Write-Host "SUCCESS: Created $outputDocx"
Write-Host "SUCCESS: Copied to $desktopDocx"
