/**
 * Lark Base ↔ MISA AMIS AI Sync Simulator
 * Core Application Logic & State Management
 */

// ==========================================
// 1. Initial State & Sample Data
// ==========================================
const INITIAL_LARK_ORDERS = [
    {
        id: "REC001",
        orderCode: "DH-2026-001",
        customerName: "Công ty Cổ phần Công nghệ Alpha Việt Nam",
        taxCode: "0108923456",
        phone: "0912345678",
        address: "Tầng 5, Tòa nhà Keangnam, Cầu Giấy, Hà Nội",
        items: [
            { sku: "SP-CLOUD-01", name: "Gói Phần Mềm Cloud ERP (1 Năm)", qty: 1, price: 32000000, vatRate: 10 }
        ],
        totalAmount: 35200000, // 32M + 3.2M VAT
        vatAmount: 3200000,
        paymentStatus: "Đã thanh toán (CK)",
        orderStatus: "Đã duyệt",
        misaSyncStatus: "Đã đồng bộ",
        misaVoucherNo: "BH00891",
        syncTime: "10/08/2026 14:10"
    },
    {
        id: "REC002",
        orderCode: "DH-2026-002",
        customerName: "Công ty TNHH Thương Mại Dịch Vụ Sao Biển",
        taxCode: "0316789123",
        phone: "0987654321",
        address: "128 Nguyễn Thị Minh Khai, Quận 3, TP.HCM",
        items: [
            { sku: "SP-POS-PRO", name: "Thiết bị POS Bán hàng thông minh", qty: 2, price: 8500000, vatRate: 8 },
            { sku: "SP-SCAN-01", name: "Máy quét mã vạch không dây", qty: 2, price: 2000000, vatRate: 8 }
        ],
        totalAmount: 22680000, // 21M + 1.68M VAT
        vatAmount: 1680000,
        paymentStatus: "Chưa thanh toán",
        orderStatus: "Đã duyệt",
        misaSyncStatus: "Đã đồng bộ",
        misaVoucherNo: "BH00892",
        syncTime: "10/08/2026 14:25"
    },
    {
        id: "REC003",
        orderCode: "DH-2026-003",
        customerName: "Công ty TNHH Tư Vấn Thiết Kế Kiến Trúc Xanh",
        taxCode: "0109988776",
        phone: "0903112233",
        address: "45 Trần Duy Hưng, Cầu Giấy, Hà Nội",
        items: [
            { sku: "SP-SRV-CONSULT", name: "Dịch vụ tư vấn giải pháp chuyển đổi số", qty: 1, price: 15000000, vatRate: 10 }
        ],
        totalAmount: 16500000,
        vatAmount: 1500000,
        paymentStatus: "Đã đặt cọc 50%",
        orderStatus: "Chờ duyệt",
        misaSyncStatus: "Chưa đồng bộ",
        misaVoucherNo: "-",
        syncTime: "-"
    },
    {
        id: "REC004",
        orderCode: "DH-2026-004",
        customerName: "Cửa hàng Thời trang & Phụ kiện Mộc Nhi",
        taxCode: "8492019283", // Mã hợp lệ 10 số
        phone: "0945678901",
        address: "78 Hàng Bông, Hoàn Kiếm, Hà Nội",
        items: [
            { sku: "SP-ACC-TAG", name: "Gói 1000 Tem nhãn RFID", qty: 5, price: 1800000, vatRate: 8 },
            { sku: "SP-PRINT-02", name: "Máy in nhiệt hóa đơn K80", qty: 1, price: 1200000, vatRate: 8 }
        ],
        totalAmount: 10908000,
        vatAmount: 708000,
        paymentStatus: "Đã thanh toán (Tiền mặt)",
        orderStatus: "Chờ duyệt",
        misaSyncStatus: "Chưa đồng bộ",
        misaVoucherNo: "-",
        syncTime: "-"
    }
];

let appState = {
    larkOrders: JSON.parse(JSON.stringify(INITIAL_LARK_ORDERS)),
    misaVouchers: [],
    misaReceipts: [],
    misaCustomers: [],
    safeMode: true, // Dry-run mode
    activeTab: "lark-base",
    selectedOrderForPipeline: null,
    nextVoucherIndex: 893,
    nextReceiptIndex: 301
};

// ==========================================
// 2. DOM Elements
// ==========================================
const elements = {
    safeModeToggle: document.getElementById('safeModeToggle'),
    safeModeStatus: document.getElementById('safeModeStatus'),
    btnResetData: document.getElementById('btnResetData'),
    btnSyncAllApproved: document.getElementById('btnSyncAllApproved'),
    larkTableBody: document.getElementById('larkTableBody'),
    btnAddNewOrder: document.getElementById('btnAddNewOrder'),
    webhookLogFeed: document.getElementById('webhookLogFeed'),
    
    // Stats
    statPending: document.getElementById('statPending'),
    statSynced: document.getElementById('statSynced'),
    statRevenue: document.getElementById('statRevenue'),
    statWarning: document.getElementById('statWarning'),
    badgeLarkCount: document.getElementById('badgeLarkCount'),
    badgeMisaCount: document.getElementById('badgeMisaCount'),

    // Pipeline
    jsonLarkPreview: document.getElementById('jsonLarkPreview'),
    jsonMisaPayload: document.getElementById('jsonMisaPayload'),
    aiDecisionBox: document.getElementById('aiDecisionBox'),
    btnRunAIEvaluation: document.getElementById('btnRunAIEvaluation'),

    // MISA Subpanes
    misaVoucherBody: document.getElementById('misaVoucherBody'),
    misaReceiptBody: document.getElementById('misaReceiptBody'),
    misaCustomerBody: document.getElementById('misaCustomerBody'),

    // Chatbot
    chatMessages: document.getElementById('chatMessages'),
    chatInput: document.getElementById('chatInput'),
    btnSendChat: document.getElementById('btnSendChat'),
    btnClearChat: document.getElementById('btnClearChat'),

    // Modal
    voucherModal: document.getElementById('voucherModal'),
    modalVoucherContent: document.getElementById('modalVoucherContent'),
    btnCloseModal: document.getElementById('btnCloseModal'),
    btnModalClose: document.getElementById('btnModalClose'),
    btnModalPost: document.getElementById('btnModalPost'),

    // Toasts
    toastContainer: document.getElementById('toastContainer')
};

// ==========================================
// 3. Helper Functions
// ==========================================
function formatVND(amount) {
    return new Intl.NumberFormat('vi-VN').format(amount) + ' đ';
}

function getFormattedTime() {
    const now = new Date();
    return now.toTimeString().split(' ')[0];
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icon = type === 'success' ? 'fa-circle-check' : 'fa-circle-info';
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function addWebhookLog(message, type = 'normal') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `<span class="log-time">${getFormattedTime()}</span> ${message}`;
    elements.webhookLogFeed.prepend(entry);
}

// ==========================================
// 4. Rendering Functions
// ==========================================
function renderLarkTable() {
    elements.larkTableBody.innerHTML = '';
    
    appState.larkOrders.forEach((order) => {
        const tr = document.createElement('tr');
        
        let statusSelectClass = 'draft';
        if (order.orderStatus === 'Đã duyệt') statusSelectClass = 'approved';
        if (order.orderStatus === 'Chờ duyệt') statusSelectClass = 'review';

        let syncPillClass = 'pending';
        let syncPillIcon = 'fa-clock';
        if (order.misaSyncStatus === 'Đã đồng bộ') {
            syncPillClass = 'synced';
            syncPillIcon = 'fa-check';
        } else if (order.misaSyncStatus === 'Lỗi MST') {
            syncPillClass = 'error';
            syncPillIcon = 'fa-triangle-exclamation';
        }

        const itemsSummary = order.items.map(i => `${i.name} (x${i.qty})`).join('<br>');

        tr.innerHTML = `
            <td><strong class="font-mono text-primary">${order.orderCode}</strong></td>
            <td>
                <strong>${order.customerName}</strong>
                <div style="font-size: 11px; color: var(--text-dim);">${order.address}</div>
            </td>
            <td><span class="font-mono">${order.taxCode}</span></td>
            <td><div style="font-size: 12px; line-height: 1.3;">${itemsSummary}</div></td>
            <td><strong class="font-mono">${formatVND(order.totalAmount)}</strong></td>
            <td><span class="badge ${order.paymentStatus.includes('Đã thanh toán') ? 'success' : 'warning'}">${order.paymentStatus}</span></td>
            <td>
                <select class="status-select ${statusSelectClass}" data-id="${order.id}" onchange="handleOrderStatusChange('${order.id}', this.value)">
                    <option value="Nháp" ${order.orderStatus === 'Nháp' ? 'selected' : ''}>Nháp</option>
                    <option value="Chờ duyệt" ${order.orderStatus === 'Chờ duyệt' ? 'selected' : ''}>Chờ duyệt</option>
                    <option value="Đã duyệt" ${order.orderStatus === 'Đã duyệt' ? 'selected' : ''}>Đã duyệt</option>
                </select>
            </td>
            <td>
                <span class="sync-status-pill ${syncPillClass}">
                    <i class="fa-solid ${syncPillIcon}"></i> ${order.misaSyncStatus}
                </span>
            </td>
            <td>
                ${order.misaVoucherNo !== '-' ? `<span class="voucher-link" onclick="openVoucherModal('${order.misaVoucherNo}')"><i class="fa-solid fa-file-invoice"></i> ${order.misaVoucherNo}</span>` : '<span style="color: var(--text-dim);">-</span>'}
            </td>
            <td>
                <button class="btn btn-sm btn-outline" onclick="inspectOrderInPipeline('${order.id}')" title="Xem phân tích AI">
                    <i class="fa-solid fa-brain text-accent"></i> Xem AI
                </button>
            </td>
        `;
        elements.larkTableBody.appendChild(tr);
    });

    updateStats();
}

function renderMisaViews() {
    // 1. Render Sales Vouchers
    elements.misaVoucherBody.innerHTML = '';
    appState.misaVouchers.forEach(v => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong class="font-mono text-primary">${v.voucherNo}</strong></td>
            <td>${v.voucherDate}</td>
            <td><span class="font-mono">${v.customerCode}</span></td>
            <td><strong>${v.customerName}</strong></td>
            <td>${v.description}</td>
            <td><strong class="font-mono">${formatVND(v.totalAmount)}</strong></td>
            <td><span class="font-mono">${formatVND(v.vatAmount)}</span></td>
            <td><span class="draft-pill">${v.postStatus}</span></td>
            <td><span class="badge"><i class="fa-solid fa-feather"></i> ${v.sourceRef}</span></td>
            <td>
                <button class="btn btn-sm btn-outline" onclick="openVoucherModal('${v.voucherNo}')">
                    <i class="fa-solid fa-eye"></i> Xem
                </button>
            </td>
        `;
        elements.misaVoucherBody.appendChild(tr);
    });

    // 2. Render Cash Receipts
    elements.misaReceiptBody.innerHTML = '';
    appState.misaReceipts.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong class="font-mono text-success">${r.receiptNo}</strong></td>
            <td>${r.date}</td>
            <td>${r.payer}</td>
            <td>${r.reason}</td>
            <td><strong class="font-mono">${formatVND(r.amount)}</strong></td>
            <td><span class="font-mono badge">${r.accounts}</span></td>
            <td><span class="voucher-link" onclick="openVoucherModal('${r.refVoucher}')">${r.refVoucher}</span></td>
            <td><span class="draft-pill">${r.status}</span></td>
        `;
        elements.misaReceiptBody.appendChild(tr);
    });

    // 3. Render Customers
    elements.misaCustomerBody.innerHTML = '';
    appState.misaCustomers.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong class="font-mono text-primary">${c.customerCode}</strong></td>
            <td><strong>${c.name}</strong></td>
            <td><span class="font-mono">${c.taxCode}</span></td>
            <td>${c.address}</td>
            <td>${c.phone}</td>
            <td><span class="badge">${c.group}</span></td>
            <td><span class="badge success">Đang hoạt động</span></td>
        `;
        elements.misaCustomerBody.appendChild(tr);
    });

    elements.badgeMisaCount.innerText = appState.misaVouchers.length;
}

function updateStats() {
    const total = appState.larkOrders.length;
    const synced = appState.larkOrders.filter(o => o.misaSyncStatus === 'Đã đồng bộ').length;
    const pending = appState.larkOrders.filter(o => o.misaSyncStatus !== 'Đã đồng bộ').length;
    const totalRevenue = appState.larkOrders.reduce((sum, o) => sum + o.totalAmount, 0);

    elements.badgeLarkCount.innerText = total;
    elements.statPending.innerText = pending;
    elements.statSynced.innerText = synced;
    elements.statRevenue.innerText = (totalRevenue / 1000000).toFixed(1) + 'M';
}

// ==========================================
// 5. AI Synchronization Engine
// ==========================================
function syncOrderToMisa(order, triggeredBy = 'Webhook') {
    // 1. AI Customer Mapping & Creation
    let customerCode = `KH_${order.taxCode.slice(0, 6)}`;
    let existingCustomer = appState.misaCustomers.find(c => c.taxCode === order.taxCode);
    
    if (!existingCustomer) {
        existingCustomer = {
            customerCode: customerCode,
            name: order.customerName,
            taxCode: order.taxCode,
            address: order.address,
            phone: order.phone,
            group: "Khách hàng Doanh nghiệp"
        };
        appState.misaCustomers.push(existingCustomer);
        addWebhookLog(`[AI Engine] Đã tự động tạo mới Khách hàng <strong>${customerCode}</strong> (${order.customerName})`, 'sync');
    }

    // 2. Generate MISA Sales Voucher
    const voucherNo = order.misaVoucherNo !== '-' ? order.misaVoucherNo : `BH00${appState.nextVoucherIndex++}`;
    const newVoucher = {
        voucherNo: voucherNo,
        voucherDate: "10/08/2026",
        customerCode: existingCustomer.customerCode,
        customerName: existingCustomer.name,
        taxCode: existingCustomer.taxCode,
        description: `Bán hàng theo đơn Lark Base: ${order.orderCode}`,
        sourceRef: order.orderCode,
        totalAmount: order.totalAmount,
        vatAmount: order.vatAmount,
        postStatus: "Chưa ghi sổ (Tạm lưu)",
        details: order.items.map(item => ({
            sku: item.sku,
            name: item.name,
            qty: item.qty,
            price: item.price,
            amount: item.qty * item.price,
            vatRate: item.vatRate,
            debitAccount: "131 (Phải thu khách hàng)",
            creditAccount: "5111 (Doanh thu bán hàng)",
            vatAccount: "33311 (Thuế GTGT đầu ra)"
        }))
    };

    // Remove old if exists
    appState.misaVouchers = appState.misaVouchers.filter(v => v.sourceRef !== order.orderCode);
    appState.misaVouchers.unshift(newVoucher);

    // 3. Generate Receipt if Paid
    if (order.paymentStatus.includes('Đã thanh toán')) {
        const isBank = order.paymentStatus.includes('CK');
        const receiptNo = isBank ? `UNC00${appState.nextReceiptIndex++}` : `PT00${appState.nextReceiptIndex++}`;
        const debitAcc = isBank ? "1121 (Tiền gửi ngân hàng)" : "1111 (Tiền mặt)";
        
        const newReceipt = {
            receiptNo: receiptNo,
            date: "10/08/2026",
            payer: order.customerName,
            reason: `Thu tiền bán hàng đơn ${order.orderCode} (${voucherNo})`,
            amount: order.totalAmount,
            accounts: `Nợ ${debitAcc.slice(0, 4)} / Có 131`,
            refVoucher: voucherNo,
            status: "Chưa ghi sổ (Tạm lưu)"
        };
        appState.misaReceipts = appState.misaReceipts.filter(r => r.refVoucher !== voucherNo);
        appState.misaReceipts.unshift(newReceipt);
        addWebhookLog(`[AI Engine] Tự động sinh Phiếu thu <strong>${receiptNo}</strong> (${formatVND(order.totalAmount)})`, 'sync');
    }

    // 4. Update Lark Order Record
    order.misaSyncStatus = "Đã đồng bộ";
    order.misaVoucherNo = voucherNo;
    order.syncTime = "10/08/2026 14:40";

    addWebhookLog(`[Thành công] Đơn <strong>${order.orderCode}</strong> đã đồng bộ sang MISA thành chứng từ <strong>${voucherNo}</strong> (${triggeredBy})`, 'success');
    showToast(`Đã đồng bộ đơn ${order.orderCode} sang MISA (${voucherNo})`, 'success');

    // 5. Send Notification to Lark Bot
    sendBotSyncCardNotification(order, voucherNo);

    renderLarkTable();
    renderMisaViews();
    inspectOrderInPipeline(order.id);
}

function handleOrderStatusChange(orderId, newStatus) {
    const order = appState.larkOrders.find(o => o.id === orderId);
    if (!order) return;

    order.orderStatus = newStatus;
    addWebhookLog(`[Lark Event] Đơn <strong>${order.orderCode}</strong> chuyển trạng thái sang: <em>"${newStatus}"</em>`);

    if (newStatus === "Đã duyệt") {
        addWebhookLog(`⚡ [Webhook Trigger] Phát hiện đơn "${order.orderCode}" đã duyệt. Đang kích hoạt AI Engine...`, 'sync');
        setTimeout(() => {
            syncOrderToMisa(order, "Webhook Tự Động");
        }, 600);
    } else {
        renderLarkTable();
    }
}

// ==========================================
// 6. Pipeline Inspector
// ==========================================
function inspectOrderInPipeline(orderId) {
    const order = appState.larkOrders.find(o => o.id === orderId);
    if (!order) return;

    appState.selectedOrderForPipeline = order;

    // Lark JSON
    elements.jsonLarkPreview.innerText = JSON.stringify({
        record_id: order.id,
        fields: {
            "Mã Đơn": order.orderCode,
            "Khách Hàng": order.customerName,
            "Mã Số Thuế": order.taxCode,
            "Địa Chỉ": order.address,
            "Chi Tiết Mặt Hàng": order.items,
            "Tổng Tiền": order.totalAmount,
            "Trạng Thái Đơn": order.orderStatus,
            "Trạng Thái Thanh Toán": order.paymentStatus
        }
    }, null, 2);

    // AI Analysis Decision
    elements.aiDecisionBox.innerHTML = `
        <div class="decision-title"><i class="fa-solid fa-lightbulb"></i> Phân tích AI cho đơn [${order.orderCode}]:</div>
        <div class="decision-text">
            • <strong>Khách hàng:</strong> Khớp MST ${order.taxCode} $\\rightarrow$ Gán mã đối tượng <code>KH_${order.taxCode.slice(0, 6)}</code>.<br>
            • <strong>Định khoản:</strong> Doanh thu thuần = ${formatVND(order.totalAmount - order.vatAmount)} (Có TK 5111) | Thuế GTGT = ${formatVND(order.vatAmount)} (Có TK 33311) | Công nợ = ${formatVND(order.totalAmount)} (Nợ TK 131).<br>
            • <strong>Thanh toán:</strong> Phát hiện "${order.paymentStatus}" $\\rightarrow$ Đề xuất tự sinh Phiếu thu kèm theo.<br>
            • <strong>An toàn dữ liệu:</strong> Chế độ <strong>Chưa ghi sổ (Unposted)</strong> được áp dụng.
        </div>
    `;

    // MISA Open API Payload
    const misaPayload = {
        app_id: "misa_app_amis_prod_89921",
        org_company_code: "CTY_CONG_NGHE_VIET_NAM_CN1",
        data_type: "sa_voucher",
        voucher: {
            ref_no: order.misaVoucherNo !== '-' ? order.misaVoucherNo : "TỰ_ĐỘNG_SINH_KHI_POST",
            ref_date: "2026-08-10",
            account_object_code: `KH_${order.taxCode.slice(0, 6)}`,
            account_object_name: order.customerName,
            account_object_tax_code: order.taxCode,
            account_object_address: order.address,
            journal_memo: `Bán hàng theo đơn Lark Base: ${order.orderCode}`,
            total_amount: order.totalAmount,
            total_vat_amount: order.vatAmount,
            is_posted: !appState.safeMode, // false if dry-run / unposted
            voucher_details: order.items.map(item => ({
                inventory_item_code: item.sku,
                description: item.name,
                unit_name: "Gói / Chiếc",
                quantity: item.qty,
                unit_price: item.price,
                amount: item.qty * item.price,
                vat_rate: item.vatRate,
                vat_amount: (item.qty * item.price * item.vatRate) / 100,
                debit_account: "131",
                credit_account: "5111",
                vat_account: "33311"
            }))
        }
    };

    elements.jsonMisaPayload.innerText = JSON.stringify(misaPayload, null, 2);
}

// ==========================================
// 7. Lark Chatbot Engine
// ==========================================
function sendBotSyncCardNotification(order, voucherNo) {
    const cardHtml = `
        <div class="chat-bubble bot">
            <div class="bot-avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="bubble-content" style="width: 100%;">
                <div class="bot-name">MISA AI Sync Bot <span class="time-stamp">${getFormattedTime()}</span></div>
                <div class="lark-mock-card success">
                    <div class="card-header"><i class="fa-solid fa-circle-check"></i> ĐÃ ĐỒNG BỘ THÀNH CÔNG SANG MISA</div>
                    <div class="card-body">
                        <p><strong>Mã Đơn Lark:</strong> ${order.orderCode}</p>
                        <p><strong>Khách Hàng:</strong> ${order.customerName}</p>
                        <p><strong>Số Chứng Từ MISA:</strong> <span class="badge">${voucherNo}</span> (Chưa ghi sổ)</p>
                        <p><strong>Tổng Tiền:</strong> ${formatVND(order.totalAmount)}</p>
                        <p><strong>Thanh Toán:</strong> ${order.paymentStatus}</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    elements.chatMessages.insertAdjacentHTML('beforeend', cardHtml);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function processUserChatMessage(message) {
    // Append User Bubble
    const userBubble = `
        <div class="chat-bubble user">
            <div class="bubble-content">
                ${message}
            </div>
        </div>
    `;
    elements.chatMessages.insertAdjacentHTML('beforeend', userBubble);
    elements.chatInput.value = '';
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

    // Simulate AI thinking and response
    setTimeout(() => {
        let botResponse = "";
        const lowerMsg = message.toLowerCase();

        if (lowerMsg.includes("đồng bộ các đơn") || lowerMsg.includes("đồng bộ hôm nay") || lowerMsg.includes("đồng bộ tất cả")) {
            const approvedUnsynced = appState.larkOrders.filter(o => o.orderStatus === 'Đã duyệt' && o.misaSyncStatus !== 'Đã đồng bộ');
            if (approvedUnsynced.length > 0) {
                botResponse = `
                    <p>Tôi đã nhận lệnh! Bắt đầu đồng bộ <strong>${approvedUnsynced.length} đơn hàng đã duyệt</strong> sang MISA AMIS:</p>
                `;
                approvedUnsynced.forEach(o => syncOrderToMisa(o, "Lark Bot Lệnh"));
            } else {
                botResponse = `
                    <p>Hiện tại tất cả các đơn hàng đã duyệt đều <strong>đã được đồng bộ đầy đủ</strong> sang MISA AMIS rồi nhé! Bạn có thể chuyển trạng thái đơn mới sang "Đã duyệt" để thử lại.</p>
                `;
            }
        } else if (lowerMsg.includes("dry-run") || lowerMsg.includes("thử nghiệm") || lowerMsg.includes("kiểm tra")) {
            botResponse = `
                <p>🔍 <strong>Kết quả kiểm tra thử nghiệm (Dry-run Analysis):</strong></p>
                <div class="lark-mock-card success">
                    <div class="card-header"><i class="fa-solid fa-shield-halved"></i> KIỂM SOÁT HỢP LỆ DỮ LIỆU</div>
                    <div class="card-body">
                        <p>• Tổng số đơn trên Lark Base: <strong>${appState.larkOrders.length} đơn</strong></p>
                        <p>• Mã số thuế: 100% đúng định dạng (10-13 chữ số)</p>
                        <p>• Danh mục hàng hóa (SKU): Khớp với danh mục MISA</p>
                        <p>• Chế độ an toàn: <strong>Tạm lưu / Chưa ghi sổ</strong> (Sẵn sàng đồng bộ)</p>
                    </div>
                </div>
            `;
        } else if (lowerMsg.includes("dh-2026-004") || lowerMsg.includes("004")) {
            const order4 = appState.larkOrders.find(o => o.orderCode === 'DH-2026-004');
            if (order4) {
                order4.orderStatus = "Đã duyệt";
                syncOrderToMisa(order4, "Lark Bot Lệnh");
                botResponse = `<p>Đã duyệt và đồng bộ thành công đơn hàng <strong>DH-2026-004</strong> cho bạn!</p>`;
            }
        } else {
            botResponse = `
                <p>Tôi đã ghi nhận yêu cầu của bạn: <em>"${message}"</em>.</p>
                <p>Hệ thống đang chạy ở chế độ <strong>Tự động hóa 100%</strong>. Khi nhân viên chốt đơn trên Lark Base, chứng từ sẽ tự động xuất hiện trên MISA AMIS ở trạng thái "Chưa ghi sổ" để nhân viên kế toán xuất hóa đơn điện tử.</p>
            `;
        }

        const botBubble = `
            <div class="chat-bubble bot">
                <div class="bot-avatar"><i class="fa-solid fa-robot"></i></div>
                <div class="bubble-content">
                    <div class="bot-name">MISA AI Sync Bot <span class="time-stamp">${getFormattedTime()}</span></div>
                    ${botResponse}
                </div>
            </div>
        `;
        elements.chatMessages.insertAdjacentHTML('beforeend', botBubble);
        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    }, 500);
}

// ==========================================
// 8. Modal & Voucher Inspector
// ==========================================
function openVoucherModal(voucherNo) {
    const voucher = appState.misaVouchers.find(v => v.voucherNo === voucherNo);
    if (!voucher) return;

    elements.modalVoucherContent.innerHTML = `
        <div style="background: rgba(0,0,0,0.2); padding: 14px; border-radius: var(--radius-md); margin-bottom: 16px;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 13px;">
                <div><strong>Số chứng từ:</strong> <span class="font-mono text-primary">${voucher.voucherNo}</span></div>
                <div><strong>Ngày hạch toán:</strong> ${voucher.voucherDate}</div>
                <div><strong>Khách hàng:</strong> ${voucher.customerName}</div>
                <div><strong>Mã số thuế:</strong> <span class="font-mono">${voucher.taxCode}</span></div>
                <div><strong>Diễn giải:</strong> ${voucher.description}</div>
                <div><strong>Trạng thái:</strong> <span class="draft-pill">${voucher.postStatus}</span></div>
            </div>
        </div>

        <h4 style="font-size: 13px; font-weight: 700; margin-bottom: 10px; color: var(--text-muted);">CHI TIẾT HẠCH TOÁN ĐỊNH KHOẢN</h4>
        <table class="misa-table" style="font-size: 12px;">
            <thead>
                <tr>
                    <th>Mã Hàng</th>
                    <th>Tên Hàng Hóa / Dịch Vụ</th>
                    <th>SL</th>
                    <th>Đơn Giá</th>
                    <th>Thành Tiền</th>
                    <th>TK Nợ</th>
                    <th>TK Có</th>
                    <th>Thuế GTGT</th>
                </tr>
            </thead>
            <tbody>
                ${voucher.details.map(d => `
                    <tr>
                        <td><code>${d.sku}</code></td>
                        <td>${d.name}</td>
                        <td>${d.qty}</td>
                        <td>${formatVND(d.price)}</td>
                        <td><strong>${formatVND(d.amount)}</strong></td>
                        <td><span class="badge">${d.debitAccount}</span></td>
                        <td><span class="badge">${d.creditAccount}</span></td>
                        <td>${d.vatRate}% (${formatVND((d.amount * d.vatRate) / 100)})</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>

        <div style="margin-top: 16px; text-align: right; font-size: 14px;">
            <div>Tổng tiền hàng: <strong>${formatVND(voucher.totalAmount - voucher.vatAmount)}</strong></div>
            <div>Tiền thuế GTGT: <strong>${formatVND(voucher.vatAmount)}</strong></div>
            <div style="font-size: 16px; color: #34d399; margin-top: 6px;">Tổng thanh toán: <strong>${formatVND(voucher.totalAmount)}</strong></div>
        </div>
    `;

    elements.voucherModal.classList.add('active');
}

function closeModal() {
    elements.voucherModal.classList.remove('active');
}

// ==========================================
// 9. Event Listeners Initialization
// ==========================================
function initEvents() {
    // Tab Switching
    document.querySelectorAll('.side-nav .nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.side-nav .nav-item').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const tabId = `tab-${btn.getAttribute('data-tab')}`;
            const targetPane = document.getElementById(tabId);
            if (targetPane) targetPane.classList.add('active');
        });
    });

    // MISA Subpanes
    document.querySelectorAll('.misa-view-toggle .btn-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.misa-view-toggle .btn-tab').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.misa-sub-pane').forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const subId = `misa-${btn.getAttribute('data-misa-tab')}`;
            const targetSub = document.getElementById(subId);
            if (targetSub) targetSub.classList.add('active');
        });
    });

    // Safe mode toggle
    elements.safeModeToggle.addEventListener('change', (e) => {
        appState.safeMode = e.target.checked;
        if (appState.safeMode) {
            elements.safeModeStatus.className = "safe-badge dry-run";
            elements.safeModeStatus.innerText = "Dry-Run (Nháp an toàn)";
            showToast("Đã bật chế độ Dry-Run (Lưu nháp an toàn)");
        } else {
            elements.safeModeStatus.className = "safe-badge live-run";
            elements.safeModeStatus.innerText = "Live Ghi Sổ";
            showToast("Đã chuyển sang chế độ Ghi sổ trực tiếp", "info");
        }
    });

    // Sync all approved
    elements.btnSyncAllApproved.addEventListener('click', () => {
        const approvedOrders = appState.larkOrders.filter(o => o.orderStatus === 'Đã duyệt');
        if (approvedOrders.length === 0) {
            showToast("Chưa có đơn nào ở trạng thái 'Đã duyệt'!");
            return;
        }
        approvedOrders.forEach(o => syncOrderToMisa(o, "Admin Nút Bấm"));
        showToast(`Đã xử lý đồng bộ xong ${approvedOrders.length} đơn hàng!`, 'success');
    });

    // Reset Data
    elements.btnResetData.addEventListener('click', () => {
        appState.larkOrders = JSON.parse(JSON.stringify(INITIAL_LARK_ORDERS));
        initPreloadedMisaData();
        renderLarkTable();
        renderMisaViews();
        showToast("Đã khôi phục dữ liệu mẫu ban đầu");
    });

    // Add new sample order
    elements.btnAddNewOrder.addEventListener('click', () => {
        const newIndex = appState.larkOrders.length + 1;
        const newOrder = {
            id: `REC00${newIndex}`,
            orderCode: `DH-2026-00${newIndex}`,
            customerName: `Công ty CP Công Nghệ & Thương Mại Mới ${newIndex}`,
            taxCode: `01089200${newIndex}`,
            phone: `09112233${newIndex}`,
            address: `Số ${newIndex * 10} Lê Văn Lương, Thanh Xuân, Hà Nội`,
            items: [
                { sku: "SP-CLOUD-01", name: "Gói Phần Mềm Cloud ERP (1 Năm)", qty: 1, price: 32000000, vatRate: 10 }
            ],
            totalAmount: 35200000,
            vatAmount: 3200000,
            paymentStatus: "Đã thanh toán (CK)",
            orderStatus: "Chờ duyệt",
            misaSyncStatus: "Chưa đồng bộ",
            misaVoucherNo: "-",
            syncTime: "-"
        };
        appState.larkOrders.push(newOrder);
        renderLarkTable();
        addWebhookLog(`[Lark Event] Đã thêm đơn hàng mới: <strong>${newOrder.orderCode}</strong>`);
        showToast(`Đã thêm đơn ${newOrder.orderCode} vào bảng Lark Base!`);
    });

    // Run AI Evaluation
    elements.btnRunAIEvaluation.addEventListener('click', () => {
        if (appState.larkOrders.length > 0) {
            inspectOrderInPipeline(appState.larkOrders[0].id);
            showToast("Đã phân tích toàn bộ quy tắc AI và sinh Payload chuẩn MISA");
        }
    });

    // Chat
    elements.btnSendChat.addEventListener('click', () => {
        const val = elements.chatInput.value.trim();
        if (val) processUserChatMessage(val);
    });

    elements.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const val = elements.chatInput.value.trim();
            if (val) processUserChatMessage(val);
        }
    });

    document.querySelectorAll('.chip-btn').forEach(chip => {
        chip.addEventListener('click', () => {
            const prompt = chip.getAttribute('data-prompt');
            processUserChatMessage(prompt);
        });
    });

    elements.btnClearChat.addEventListener('click', () => {
        elements.chatMessages.innerHTML = `
            <div class="chat-bubble bot">
                <div class="bot-avatar"><i class="fa-solid fa-robot"></i></div>
                <div class="bubble-content">
                    <div class="bot-name">MISA AI Sync Bot <span class="time-stamp">${getFormattedTime()}</span></div>
                    <p>Lịch sử chat đã được xóa. Tôi sẵn sàng nhận lệnh mới từ bạn!</p>
                </div>
            </div>
        `;
    });

    // Modal
    elements.btnCloseModal.addEventListener('click', closeModal);
    elements.btnModalClose.addEventListener('click', closeModal);
    elements.btnModalPost.addEventListener('click', () => {
        showToast("Đã thử nghiệm 'Ghi sổ' thành công trên chứng từ!", 'success');
        closeModal();
    });
    elements.voucherModal.addEventListener('click', (e) => {
        if (e.target === elements.voucherModal) closeModal();
    });

    // Save Mapping
    document.getElementById('btnSaveMapping').addEventListener('click', () => {
        showToast("Đã lưu cấu hình mapping trường và tham số API thành công!", 'success');
    });
}

// ==========================================
// 10. Initial Preload
// ==========================================
function initPreloadedMisaData() {
    appState.misaVouchers = [];
    appState.misaReceipts = [];
    appState.misaCustomers = [];

    // Preload the first two synced orders
    const syncedOrders = appState.larkOrders.filter(o => o.misaSyncStatus === 'Đã đồng bộ');
    syncedOrders.forEach(order => {
        syncOrderToMisa(order, "Khởi tạo hệ thống");
    });
}

// App Entry Point
document.addEventListener('DOMContentLoaded', () => {
    initPreloadedMisaData();
    renderLarkTable();
    renderMisaViews();
    initEvents();
    if (appState.larkOrders.length > 0) {
        inspectOrderInPipeline(appState.larkOrders[0].id);
    }
});
