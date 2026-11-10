// ===================================================================
// EASY TRIP & VISA - CO-PILOT CHAT ENGINE & DYNAMIC LEARNING
// ===================================================================

const isArabicUI = window.location.pathname.includes('index_ar.html') || window.location.pathname.includes('arabic.html');
const isFrenchUI = window.location.pathname.includes('index_fr.html') || window.location.pathname.includes('french.html');

// Các phần tử giao diện
const customerChatHistory = document.getElementById('customer-chat-history');
const customerInput = document.getElementById('customer-input');
const customerSendBtn = document.getElementById('customer-send-btn');
const queryChips = document.querySelectorAll('.query-chip');

const agentChatHistory = document.getElementById('agent-chat-history');
const agentMonitorArea = document.getElementById('agent-monitor-area');
const copilotConfidenceBadge = document.getElementById('copilot-confidence-badge');
const customerQuestionText = document.getElementById('customer-question-text');
const draftTextarea = document.getElementById('draft-textarea');

const btnApprove = document.getElementById('btn-approve');
const btnEditSend = document.getElementById('btn-edit-send');
const btnTakeover = document.getElementById('btn-takeover');

const statApproved = document.getElementById('stat-approved');
const statLearned = document.getElementById('stat-learned');
const statConfidence = document.getElementById('stat-confidence');

const brainLessonsList = document.getElementById('brain-lessons-list');
const btnClearBrain = document.getElementById('btn-clear-brain');

// Trạng thái ứng dụng
let approvedCount = 0;
let confidenceSum = 0;
let queryCount = 0;
let lastCustomerMessage = '';

// Tri thức gốc của Easy Trip & Visa (Dựa trên knowledge.txt)
const defaultLessons = [
    {
        id: 'def-1',
        keywords: ['nga', 'hàn', 'lao', 'lào', 'visarun', 'russia', 'korea'],
        promptText: "Tôi là người Nga/Hàn, muốn đi visarun Lào từ Nha Trang",
        response: "🚌 Chào bạn! Với quốc tịch Nga/Hàn Quốc/ASEAN, bạn sẽ đi tuyến **Nha Trang <=> LÀO (Cửa khẩu Bờ Y)** vì được **MIỄN VISA LÀO** giúp tiết kiệm chi phí! \n\n* **Gói xe Trọn gói 45 ngày:** 1.400.000đ (Khách cũ: 1.300.000đ). Xe chạy hàng ngày lúc 21:00.\n* **Gói E-visa 90 ngày (Nga):** Khách mới 3.400.000đ (Single) / 4.400.000đ (Multi) | Khách cũ 3.000.000đ (Single) / 4.000.000đ (Multi). Xe chạy thứ 3, 5, CN lúc 21:30.\n👉 Đón khách tại River Station hoặc Oceanus Nha Trang. Bạn muốn đi vào ngày nào?"
    },
    {
        id: 'def-2',
        keywords: ['campuchia', 'mộc bài', 'cambodia', 'quốc tịch khác', 'mỹ', 'anh'],
        promptText: "Giá đi visarun Campuchia (Mộc Bài) thế nào?",
        response: "🇰🇭 Chào bạn! Tuyến **Nha Trang <=> CAMPUCHIA (Cửa khẩu Mộc Bài)** khởi hành lúc **21:30 tối Thứ 3, Thứ 5, Chủ Nhật** hàng tuần:\n\n* **Gói xe 45 ngày (miễn thị thực):** 1.400.000đ.\n* **Quốc tế / Hàn Quốc (`/english`, `/korean`):** 4.000.000đ (Bus + E-visa 90D, +1.000.000đ Visa Cam) | 5.000.000đ (Single + Visa Cam) | 6.000.000đ (Multi + Visa Cam).\n* **Nga & CIS (`/russian`):** 3.400.000đ (Single 90D) | 4.400.000đ (Single + Cam) | 5.400.000đ (Multi + Cam).\n* **Ả Rập (`/arabic`):** 5.500.000đ / 6.500.000đ / 7.500.000đ.\n👉 Bạn vui lòng gửi mình quốc tịch và hình ảnh passport/visa hiện tại để kiểm tra lịch xe phù hợp nhất nhé!"
    },
    {
        id: 'def-3',
        keywords: ['e-visa', '3-5 ngày', 'giá e-visa', 'chi phí', 'làm visa'],
        promptText: "Giá làm E-visa Việt Nam chuẩn 3-5 ngày là bao nhiêu?",
        response: "💳 Dạ, chi phí làm **E-visa Việt Nam tiêu chuẩn (3-5 ngày làm việc, Single Entry)** theo từng thị trường Website là:\n* **Quốc tế / Hàn Quốc (`/english`, `/korean`):** **1.810.000đ**\n* **Nga & CIS (`/russian`):** **1.610.000đ**\n* **Ả Rập (`/arabic`):** **3.310.000đ**\n🔥 Nếu là **Khách Hàng Cũ (Loyalty)** giá ưu đãi còn **1.110.000đ** (Multiple Entry +1.000.000đ). Bạn có cần làm gấp hơn (1h / 2h / 4h / 1-2 ngày) không?"
    },
    {
        id: 'def-4',
        keywords: ['thuê xe máy', 'xe máy', 'nha trang', 'thuê xe'],
        promptText: "Thủ tục thuê xe máy ở Nha Trang như thế nào?",
        response: "🛵 Easy Trip có dịch vụ **thuê xe máy 24/7 giao tận nơi** tại Nha Trang! \n* Đầy đủ mũ bảo hiểm, giấy tờ xe.\n* Thuê theo ngày, theo tuần hoặc tháng với giá ưu đãi cực tốt.\n👉 Bạn muốn thuê dòng xe ga hay xe số và nhận xe tại khách sạn nào ạ?"
    }
];

// Khởi tạo bộ não học tập (Tải từ localStorage hoặc rỗng)
let learnedLessons = [];
const BACKEND_URL = window.location.origin;
let isBackendOnline = false;

// --- BẢO MẬT & XÁC THỰC ADMIN ---
const originalFetch = window.fetch;
window.fetch = async function (url, options = {}) {
    if (url.toString().startsWith(BACKEND_URL)) {
        options.headers = options.headers || {};
        if (!(options.body instanceof FormData)) {
            if (!options.headers['Content-Type']) {
                options.headers['Content-Type'] = 'application/json';
            }
        }
        const token = localStorage.getItem('admin_access_code') || '';
        if (token) {
            options.headers['Authorization'] = `Bearer ${token}`;
        }
    }
    
    try {
        const response = await originalFetch(url, options);
        if (url.toString().startsWith(BACKEND_URL) && !url.toString().includes('/api/verify_code')) {
            if (response.status === 401 || response.status === 403) {
                localStorage.removeItem('admin_access_code');
                showAuthGate(true);
            }
        }
        return response;
    } catch (err) {
        throw err;
    }
};

function showAuthGate(visible) {
    const overlay = document.getElementById('auth-gate-overlay');
    if (!overlay) return;
    overlay.style.display = visible ? 'flex' : 'none';
    if (visible) {
        document.getElementById('auth-password-input').focus();
    }
}

function handleAuthKeyPress(event) {
    if (event.key === 'Enter') {
        submitAuthCode();
    }
}

async function submitAuthCode() {
    const input = document.getElementById('auth-password-input');
    const password = input.value.trim();
    if (!password) {
        showNotification("Vui lòng nhập mã bảo mật!", "warning");
        return;
    }
    
    try {
        const response = await originalFetch(`${BACKEND_URL}/api/verify_code`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: password })
        });
        const data = await response.json();
        if (data.success) {
            localStorage.setItem('admin_access_code', password);
            showNotification("Đăng nhập quản trị thành công!");
            showAuthGate(false);
            if (document.getElementById('tab-btn-live') && document.getElementById('tab-btn-live').classList.contains('active')) {
                startLivePolling();
                loadLiveBrainLessons();
            }
        } else {
            showNotification(data.message || "Mã truy cập không chính xác!", "warning");
            input.value = '';
            input.focus();
        }
    } catch (e) {
        showNotification("Lỗi kết nối server xác thực.", "warning");
    }
}

function checkAuthOnStartup() {
    const token = localStorage.getItem('admin_access_code');
    if (!token) {
        showAuthGate(true);
    } else {
        showAuthGate(false);
    }
}

// Hàm thông báo Toast đẹp mắt
function showNotification(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast-notif ${type}`;
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.right = '20px';
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = '12px';
    toast.style.color = '#fff';
    toast.style.fontSize = '0.85rem';
    toast.style.fontWeight = '600';
    toast.style.zIndex = '9999';
    toast.style.boxShadow = '0 10px 25px rgba(0,0,0,0.5)';
    toast.style.display = 'flex';
    toast.style.alignItems = 'center';
    toast.style.gap = '8px';
    toast.style.animation = 'toastIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards';
    
    let bg = 'linear-gradient(135deg, #10B981, #059669)'; // success
    let icon = '✅';
    if (type === 'warning') {
        bg = 'linear-gradient(135deg, #F59E0B, #D97706)';
        icon = '⚠️';
    } else if (type === 'info') {
        bg = 'linear-gradient(135deg, #3B82F6, #1D4ED8)';
        icon = 'ℹ️';
    }
    toast.style.background = bg;
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    
    document.body.appendChild(toast);
    
    if (!document.getElementById('toast-styles')) {
        const style = document.createElement('style');
        style.id = 'toast-styles';
        style.innerHTML = `
            @keyframes toastIn {
                from { opacity: 0; transform: translateY(20px) scale(0.9); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }
            @keyframes toastOut {
                from { opacity: 1; transform: translateY(0) scale(1); }
                to { opacity: 0; transform: translateY(20px) scale(0.9); }
            }
        `;
        document.head.appendChild(style);
    }
    
    setTimeout(() => {
        toast.style.animation = 'toastOut 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3500);
}

// Kiểm tra kết nối với Backend FastAPI thực tế
async function checkBackendConnection() {
    try {
        const response = await fetch(`${BACKEND_URL}/admin/orders?status=PENDING`, {
            method: 'GET',
            mode: 'cors'
        });
        if (response.ok) {
            setBackendOnline(true);
        } else {
            setBackendOnline(false);
        }
    } catch (e) {
        setBackendOnline(false);
    }
}

function setBackendOnline(online) {
    isBackendOnline = online;
    const indicator = document.getElementById('backend-sync-indicator');
    const text = document.getElementById('backend-sync-text');
    if (!indicator || !text) return;
    
    if (online) {
        indicator.classList.remove('offline');
        indicator.classList.add('online');
        text.textContent = 'Backend Online';
        indicator.title = 'Đang đồng bộ thời gian thực với server!';
    } else {
        indicator.classList.remove('online');
        indicator.classList.add('offline');
        text.textContent = 'Backend Offline';
        indicator.title = 'Nhấp để kiểm tra lại kết nối';
    }
}

function initBrain() {
    const saved = localStorage.getItem('hitl_bot_lessons');
    if (saved) {
        try {
            learnedLessons = JSON.parse(saved);
        } catch (e) {
            learnedLessons = [];
        }
    }
    updateBrainUI();
    updateStats();
    
    // Kiểm tra kết nối lần đầu
    checkBackendConnection();
    // Đăng ký sự kiện click nút kết nối để kiểm tra lại
    const indicator = document.getElementById('backend-sync-indicator');
    if (indicator) {
        indicator.addEventListener('click', () => {
            showNotification('Đang kiểm tra kết nối với server...', 'info');
            checkBackendConnection();
        });
    }
}

// Lưu bài học mới và đồng bộ vào Backend thực tế
function learnLesson(keywords, promptText, response) {
    const id = 'learned-' + Date.now();
    const newLesson = {
        id: id,
        keywords: keywords,
        promptText: promptText,
        response: response
    };
    learnedLessons.unshift(newLesson);
    localStorage.setItem('hitl_bot_lessons', JSON.stringify(learnedLessons));
    
    updateBrainUI();
    
    // Đồng bộ trực tiếp vào Backend thật nếu Server đang chạy
    if (isBackendOnline) {
        fetch(`${BACKEND_URL}/api/teach`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: promptText,
                answer: response
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showNotification('Đã đồng bộ trực tiếp vào Tri thức thực tế của AI Agent!');
            } else {
                showNotification('Lỗi đồng bộ: ' + data.message, 'warning');
            }
        })
        .catch(err => {
            showNotification('Lỗi kết nối đồng bộ backend.', 'warning');
        });
    } else {
        showNotification('Đã học trên máy (Chế độ giả lập).');
    }
    
    setTimeout(() => {
        const firstCard = document.getElementById(`card-${id}`);
        if (firstCard) {
            firstCard.classList.add('new-learned');
        }
    }, 100);

    updateStats();
}

// Xóa bài học
btnClearBrain.addEventListener('click', () => {
    if (confirm('Bạn có chắc chắn muốn xoá toàn bộ bài học đã dạy cho Bot không?')) {
        learnedLessons = [];
        localStorage.removeItem('hitl_bot_lessons');
        updateBrainUI();
        updateStats();
    }
});

// Cập nhật giao diện Bộ Não Hub
function updateBrainUI() {
    // Giữ lại các bài học mặc định
    let html = '';
    
    // Render bài học đã học trước
    learnedLessons.forEach(l => {
        html += `
        <div class="lesson-card" id="card-${l.id}">
            <div class="lesson-meta">
                <span class="badge learned">Được Dạy Trực Tiếp</span>
                <span>Khớp: <code>${l.keywords.join(', ')}</code></span>
            </div>
            <div class="lesson-qa">
                <div><strong>Nếu khách hỏi:</strong> "${l.promptText}"</div>
                <div><strong>Bot sẽ trả lời:</strong> "${formatResponseForPreview(l.response)}"</div>
            </div>
        </div>
        `;
    });

    // Render bài học mặc định ban đầu
    defaultLessons.forEach(l => {
        html += `
        <div class="lesson-card default">
            <div class="lesson-meta">
                <span class="badge default">Tri Thức Gốc</span>
                <span>Khớp: <code>${l.keywords.slice(0, 3).join(', ')}</code></span>
            </div>
            <div class="lesson-qa">
                <div><strong>Nếu khách hỏi:</strong> "${l.promptText}"</div>
                <div><strong>Bot sẽ trả lời:</strong> "${formatResponseForPreview(l.response)}"</div>
            </div>
        </div>
        `;
    });

    brainLessonsList.innerHTML = html;
}

// Format câu trả lời để hiển thị rút gọn trong danh sách
function formatResponseForPreview(text) {
    if (text.length > 120) {
        return text.substring(0, 117) + '...';
    }
    return text;
}

// Cập nhật thống kê trên header
function updateStats() {
    statApproved.textContent = approvedCount;
    statLearned.textContent = learnedLessons.length;
    
    if (queryCount > 0) {
        const avg = Math.round(confidenceSum / queryCount);
        statConfidence.textContent = `${avg}%`;
    } else {
        statConfidence.textContent = '--%';
    }
}

// ==========================================================
// CƠ CHẾ KHỚP TỪ KHOÁ VÀ TÍNH ĐỘ TIN CẬY (NLP ENGINE ĐƠN GIẢN)
// ==========================================================
function cleanText(text) {
    return text.toLowerCase()
        .replace(/[.,\/#!$%\^&\*;:{}=\-_`~()?]/g,"")
        .replace(/\s{2,}/g," ");
}

function calculateConfidence(inputText) {
    const cleanedInput = cleanText(inputText);
    
    let bestMatch = null;
    let maxScore = 0;
    let matchedFromLearned = false;

    // 1. Kiểm tra trong các bài học đã được học trực tiếp từ người dùng trước
    learnedLessons.forEach(lesson => {
        let matchCount = 0;
        lesson.keywords.forEach(kw => {
            if (cleanedInput.includes(kw)) {
                matchCount++;
            }
        });
        
        let score = (matchCount / Math.max(lesson.keywords.length, 1)) * 100;
        
        if (cleanText(lesson.promptText).includes(cleanedInput) || cleanedInput.includes(cleanText(lesson.promptText))) {
            score = 100;
        }

        if (score > maxScore) {
            maxScore = score;
            bestMatch = lesson;
            matchedFromLearned = true;
        }
    });

    // 2. Kiểm tra trong các bài học gốc
    defaultLessons.forEach(lesson => {
        let matchCount = 0;
        lesson.keywords.forEach(kw => {
            if (cleanedInput.includes(kw)) {
                matchCount++;
            }
        });
        
        let score = (matchCount / Math.max(lesson.keywords.length, 1)) * 100;

        if (cleanText(lesson.promptText).includes(cleanedInput) || cleanedInput.includes(cleanText(lesson.promptText))) {
            score = 98;
        }

        if (score > maxScore) {
            maxScore = score;
            bestMatch = lesson;
            matchedFromLearned = false;
        }
    });

    if (maxScore < 20) {
        return {
            confidence: Math.max(5, Math.round(maxScore)),
            draftText: "Dạ, Easy Trip xin ghi nhận thông tin của bạn. Bạn vui lòng đợi trong giây lát, nhân viên tư vấn sẽ liên hệ và giải đáp trực tiếp cho bạn ngay ạ! 📞",
            keywords: ['nhân viên', 'đợi']
        };
    }

    const finalScore = Math.min(100, Math.round(maxScore));
    return {
        confidence: finalScore,
        draftText: bestMatch.response,
        keywords: bestMatch.keywords,
        matchedFromLearned: matchedFromLearned
    };
}

// Trích xuất từ khóa
function extractKeywords(text) {
    const skipWords = ['tôi', 'là', 'muốn', 'đi', 'cho', 'hỏi', 'giá', 'bao', 'nhiêu', 'thế', 'nào', 'ạ', 'và', 'có', 'ở', 'từ', 'cho', 'em', 'admin', 'bot', 'với'];
    const words = cleanText(text).split(' ');
    const uniqueKeywords = [...new Set(words)].filter(w => w.length > 2 && !skipWords.includes(w));
    
    if (uniqueKeywords.length === 0) {
        return words.filter(w => w.length > 1).slice(0, 4);
    }
    return uniqueKeywords;
}

// Gửi tin nhắn mô phỏng từ KHÁCH HÀNG
function handleCustomerSend(text) {
    if (!text.trim()) return;

    lastCustomerMessage = text;
    appendMessageToPhone('user', text);
    appendMessageToAgent('user', 'Khách hàng', text);
    processCopilotDraft(text);
}

// Hiển thị tin nhắn bên điện thoại khách hàng
function appendMessageToPhone(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `phone-message ${role}`;
    
    const bubble = document.createElement('div');
    bubble.className = 'phone-message-bubble';
    bubble.innerHTML = formatMarkdown(text);
    
    msgDiv.appendChild(bubble);
    customerChatHistory.appendChild(msgDiv);
    customerChatHistory.scrollTop = customerChatHistory.scrollHeight;
}

// Hiển thị tin nhắn bên màn hình giám sát của Agent
function appendMessageToAgent(role, senderName, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `agent-message ${role === 'user' ? 'user' : (role === 'agent' ? 'agent-manual' : 'bot')}`;
    
    const sender = document.createElement('div');
    sender.className = 'sender-info';
    sender.textContent = `${senderName}:`;
    
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = formatMarkdown(text);
    
    msgDiv.appendChild(sender);
    msgDiv.appendChild(bubble);
    agentChatHistory.appendChild(msgDiv);
    
    agentMonitorArea.scrollTop = agentMonitorArea.scrollHeight;
}

// Xử lý Markdown nhẹ (Bold **, Linebreak \n, Images, Links)
function formatMarkdown(text) {
    if (!text) return "";
    let formatted = text;
    
    // Hỗ trợ hiển thị ảnh nếu là markdown ảnh hoặc link ảnh trực tiếp
    const imgRegex = /!\[.*?\]\((.*?)\)/g;
    formatted = formatted.replace(imgRegex, '<img src="$1" style="max-width: 200px; max-height: 200px; border-radius: 8px; margin-top: 5px; display: block;" />');
    
    // Hỗ trợ link file
    const linkRegex = /\[(.*?)\]\((.*?)\)/g;
    formatted = formatted.replace(linkRegex, '<a href="$2" target="_blank" style="color: #3B82F6; text-decoration: underline;">$1</a>');
    
    // Nếu là URL ảnh trực tiếp không có markdown
    const directImgRegex = /^(https?:\/\/.*\.(?:png|jpg|jpeg|gif|webp))$/i;
    if (directImgRegex.test(formatted.trim())) {
        formatted = `<img src="${formatted.trim()}" style="max-width: 200px; max-height: 200px; border-radius: 8px; margin-top: 5px; display: block;" />`;
    }

    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    return formatted.replace(/\n/g, '<br>');
}

function processCopilotDraft(question) {
    customerQuestionText.textContent = `"${question}"`;
    draftTextarea.value = "Đang phân tích và soạn bản nháp...";
    
    btnApprove.disabled = true;
    btnEditSend.disabled = true;
    btnTakeover.disabled = true;

    setTimeout(() => {
        const result = calculateConfidence(question);
        
        confidenceSum += result.confidence;
        queryCount++;
        updateStats();

        draftTextarea.value = result.draftText;
        copilotConfidenceBadge.textContent = `${result.confidence}%`;
        
        copilotConfidenceBadge.className = '';
        if (result.confidence >= 80) {
            copilotConfidenceBadge.classList.add('conf-high');
        } else if (result.confidence >= 50) {
            copilotConfidenceBadge.classList.add('conf-mid');
        } else {
            copilotConfidenceBadge.classList.add('conf-low');
        }

        btnApprove.disabled = false;
        btnEditSend.disabled = false;
        btnTakeover.disabled = false;
    }, 500);
}

// HÀNH ĐỘNG 1: DUYỆT & GỬI NGAY (Approve)
btnApprove.addEventListener('click', () => {
    const finalReply = draftTextarea.value;
    appendMessageToPhone('bot', finalReply);
    appendMessageToAgent('bot', 'Bot AI (Bạn đã duyệt)', finalReply);

    approvedCount++;
    updateStats();
    resetDraftArea();
});

// HÀNH ĐỘNG 2: SỬA & DẠY BOT (Edit & Teach)
btnEditSend.addEventListener('click', () => {
    const editedReply = draftTextarea.value;
    appendMessageToPhone('bot', editedReply);
    appendMessageToAgent('bot', 'Bot AI (Đã sửa & dạy học)', editedReply);

    const keywords = extractKeywords(lastCustomerMessage);
    learnLesson(keywords, lastCustomerMessage, editedReply);

    approvedCount++;
    updateStats();
    resetDraftArea();
});

// HÀNH ĐỘNG 3: TRỰC TIẾP CHAT (Agent Takeover)
btnTakeover.addEventListener('click', () => {
    const manualReply = draftTextarea.value;
    appendMessageToPhone('agent', manualReply);
    appendMessageToAgent('agent', 'Agent (Bạn trực tiếp chat)', manualReply);

    const keywords = extractKeywords(lastCustomerMessage);
    learnLesson(keywords, lastCustomerMessage, manualReply);

    approvedCount++;
    updateStats();
    resetDraftArea();
});

function resetDraftArea() {
    customerQuestionText.textContent = "Đang đợi tin nhắn mới từ khách hàng...";
    draftTextarea.value = "";
    copilotConfidenceBadge.textContent = "--%";
    copilotConfidenceBadge.className = 'conf-low';
    
    btnApprove.disabled = true;
    btnEditSend.disabled = true;
    btnTakeover.disabled = true;
}

customerInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        const text = customerInput.value.trim();
        if (text) {
            handleCustomerSend(text);
            customerInput.value = '';
        }
    }
});

customerSendBtn.addEventListener('click', () => {
    const text = customerInput.value.trim();
    if (text) {
        handleCustomerSend(text);
        customerInput.value = '';
    }
});

queryChips.forEach(chip => {
    chip.addEventListener('click', () => {
        const text = chip.getAttribute('data-text');
        handleCustomerSend(text);
    });
});

// Khởi chạy khi tải trang
window.addEventListener('DOMContentLoaded', () => {
    initBrain();
    checkAuthOnStartup();
    fetchGlobalBotMode();
    const savedTab = localStorage.getItem('copilot_active_tab') || 'live';
    switchTab(savedTab);
    setupStaffChatDragAndDrop();
    setupStaffChatPaste();
});


// ===================================================================
// EASY TRIP & VISA - REAL-TIME LIVE CONTROL STUDIO EXTENSION
// ===================================================================

let activeSessionId = null;
let liveSessions = [];
let livePollingInterval = null;
let liveLessons = [];

// Chuyển đổi giữa 3 tab Sandbox, Live Channels và Quy Trình Vận Hành
function switchTab(tabName) {
    localStorage.setItem('copilot_active_tab', tabName);
    const tabSandbox = document.getElementById('tab-sandbox');
    const tabLive = document.getElementById('tab-live');
    const tabOps = document.getElementById('tab-ops');
    
    const btnSandbox = document.getElementById('tab-btn-sandbox');
    const btnLive = document.getElementById('tab-btn-live');
    const btnOps = document.getElementById('tab-btn-ops');

    // Reset active panels
    tabSandbox.classList.remove('active');
    tabLive.classList.remove('active');
    tabOps.classList.remove('active');
    
    // Reset active buttons
    btnSandbox.classList.remove('active');
    btnLive.classList.remove('active');
    btnOps.classList.remove('active');

    if (tabName === 'sandbox') {
        tabSandbox.classList.add('active');
        btnSandbox.classList.add('active');
        
        stopLivePolling();
        initBrain();
    } else if (tabName === 'live') {
        tabLive.classList.add('active');
        btnLive.classList.add('active');
        
        startLivePolling();
        loadLiveBrainLessons();
    } else if (tabName === 'ops') {
        tabOps.classList.add('active');
        btnOps.classList.add('active');
        
        stopLivePolling();
        // Initialize Operations defaults
        calculateOps();
        updateGreetingTemplate();
        updatePaymentTemplate();
        updateFeedbackTemplate();
    }
}

// Bắt đầu vòng lặp thăm dò
function startLivePolling() {
    stopLivePolling();
    pollLiveSessions();
    livePollingInterval = setInterval(pollLiveSessions, 2000);
}

// Dừng vòng lặp thăm dò
function stopLivePolling() {
    if (livePollingInterval) {
        clearInterval(livePollingInterval);
        livePollingInterval = null;
    }
}

// Ép làm mới danh sách phiên từ Backend SQLite
async function reloadLiveSessions() {
    const btn = document.getElementById('btn-reload-channels');
    if (btn) btn.innerHTML = '<span>⏳</span> <span>Đang tải...</span>';
    try {
        await fetch(`${BACKEND_URL}/api/sessions/reload`, { method: 'POST' });
        await pollLiveSessions();
        if (activeSessionId) {
            await updateActiveLiveSessionDetail(true, true);
        }
    } catch (e) {
        console.error("Lỗi reload sessions:", e);
    } finally {
        if (btn) btn.innerHTML = '<span>🔄</span> <span>Tải lại</span>';
    }
}

// Ép làm mới tin nhắn phiên hiện tại từ Database
async function reloadCurrentActiveSession() {
    const btn = document.getElementById('btn-reload-chat');
    if (btn) btn.innerHTML = '<span>⏳</span> <span>Đang tải...</span>';
    try {
        if (activeSessionId) {
            await updateActiveLiveSessionDetail(true, true);
        }
    } catch (e) {
        console.error("Lỗi reload active session:", e);
    } finally {
        if (btn) btn.innerHTML = '<span>🔄</span> <span>Làm mới</span>';
    }
}

// Thăm dò các phiên chat thực tế từ Backend
async function pollLiveSessions() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/sessions`);
        if (!response.ok) throw new Error("Offline");
        
        setBackendOnline(true);
        const data = await response.json();
        liveSessions = data;
        
        await fetchGlobalBotMode();
        renderLiveChannelsList();
        
        if (activeSessionId) {
            await updateActiveLiveSessionDetail();
        }
    } catch (e) {
        setBackendOnline(false);
    }
}

// Render danh sách các kênh thực tế
function renderLiveChannelsList() {
    const container = document.getElementById('live-channels-list-container');
    if (!container) return;
    
    if (liveSessions.length === 0) {
        container.innerHTML = `<div class="no-channels">Không có cuộc trò chuyện nào đang hoạt động.</div>`;
        return;
    }
    
    let html = '';
    liveSessions.forEach(session => {
        const isActive = session.session_id === activeSessionId ? 'active' : '';
        const platformClass = session.platform.toLowerCase();
        
        let modeLabel = '🟢 Auto';
        let modeClass = 'mode-auto';
        if (session.mode === 'copilot') {
            modeLabel = '🟡 Co-Pilot';
            modeClass = 'mode-copilot';
        } else if (session.mode === 'manual') {
            modeLabel = '🔴 Manual';
            modeClass = 'mode-manual';
        }
        
        const draftIndicator = session.pending_draft ? ' <span class="badge learned" style="font-size:0.6rem; margin-left:4px;">Draft</span>' : '';
        
        html += `
        <div class="channel-item ${isActive}" onclick="selectLiveSession('${session.session_id}')">
            <div class="channel-item-header">
                <span class="channel-name">${session.customer_name}</span>
                <span class="channel-platform ${platformClass}">${session.platform}</span>
            </div>
            <div class="channel-item-last-msg">${session.last_message || 'Không có nội dung'}</div>
            <div class="channel-item-footer">
                <span>${session.last_update ? session.last_update.split(' ')[1] : ''}</span>
                <span class="channel-mode-badge ${modeClass}">${modeLabel}${draftIndicator}</span>
            </div>
        </div>
        `;
    });
    
    container.innerHTML = html;
}

// Chọn cuộc chat thực tế
async function selectLiveSession(sessionId) {
    activeSessionId = sessionId;
    
    document.querySelectorAll('.channel-item').forEach(item => {
        item.classList.remove('active');
    });
    
    document.getElementById('session-mode-indicator-wrap').style.display = 'flex';
    document.getElementById('live-chat-input-area-container').style.display = 'flex';
    
    await updateActiveLiveSessionDetail(true);
}

// Cập nhật nội dung cuộc chat đang chọn
async function updateActiveLiveSessionDetail(forceScroll = false, forceRefresh = false) {
    if (!activeSessionId) return;
    
    try {
        const url = forceRefresh 
            ? `${BACKEND_URL}/api/session/${activeSessionId}?refresh=true` 
            : `${BACKEND_URL}/api/session/${activeSessionId}`;
        const response = await fetch(url);
        const data = await response.json();
        
        if (!data.success) return;
        
        const platformIcon = activeSessionId.split('_')[0] === 'telegram' ? '🔵' : (activeSessionId.split('_')[0] === 'zalo' ? '🔹' : (activeSessionId.split('_')[0] === 'facebook' ? '🔷' : '🌐'));
        document.getElementById('live-chat-platform-icon').textContent = platformIcon;
        document.getElementById('live-chat-client-name').textContent = data.customer_name;
        
        const select = document.getElementById('session-mode-select');
        if (select && select.value !== data.mode) {
            select.value = data.mode;
        }
        
        const historyContainer = document.getElementById('live-chat-history-container');
        let html = '';
        if (data.history.length === 0) {
            html = `<div class="no-active-chat"><p>Không có tin nhắn nào trong cuộc trò chuyện.</p></div>`;
        } else {
            data.history.forEach(msg => {
                let sender = 'Khách hàng';
                let roleClass = 'user';
                
                if (msg.role === 'assistant' || msg.role === 'model') {
                    sender = 'Bot AI';
                    roleClass = 'bot';
                } else if (msg.role === 'agent') {
                    sender = 'Agent (Bạn)';
                    roleClass = 'agent-manual';
                }
                
                html += `
                <div class="agent-message ${roleClass}">
                    <div class="sender-info">${sender}:</div>
                    <div class="bubble">${formatMarkdown(msg.content)}</div>
                </div>
                `;
            });
        }
        
        const wasAtBottom = historyContainer.scrollHeight - historyContainer.scrollTop <= historyContainer.clientHeight + 100;
        historyContainer.innerHTML = html;
        if (forceScroll || wasAtBottom) {
            historyContainer.scrollTop = historyContainer.scrollHeight;
        }
        
        const copilotCard = document.getElementById('live-copilot-draft-card');
        const draftTextarea = document.getElementById('live-draft-textarea');
        
        if (data.mode === 'copilot' && data.pending_draft) {
            copilotCard.style.display = 'block';
            if (draftTextarea && document.activeElement !== draftTextarea) {
                draftTextarea.value = data.pending_draft;
            }
        } else {
            copilotCard.style.display = 'none';
        }
        
    } catch (e) {
        console.error("Lỗi cập nhật chi tiết hội thoại live:", e);
    }
}

// ==========================================================
// ĐIỀU KHIỂN CHẾ ĐỘ BOT TOÀN HỆ THỐNG (GLOBAL BOT SWITCH)
// ==========================================================

// Cập nhật giao diện Badge & Select chế độ Bot toàn hệ thống
function updateGlobalBotUI(mode) {
    const badge = document.getElementById('global-bot-badge');
    const select = document.getElementById('global-bot-mode-select');
    if (select && select.value !== mode) {
        select.value = mode;
    }
    if (badge) {
        badge.className = 'global-bot-badge';
        if (mode === 'auto') {
            badge.classList.add('badge-auto');
            badge.textContent = '🟢 AUTO';
        } else if (mode === 'copilot') {
            badge.classList.add('badge-copilot');
            badge.textContent = '🟡 CO-PILOT';
        } else {
            badge.classList.add('badge-off');
            badge.textContent = '🔴 OFF';
        }
    }
}

// Lấy chế độ Bot toàn hệ thống từ Backend
async function fetchGlobalBotMode() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/system/bot-mode`);
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.global_mode) {
                updateGlobalBotUI(data.global_mode);
            }
        }
    } catch (e) {
        // im lặng nếu offline
    }
}

// Thay đổi chế độ Bot toàn hệ thống (BẬT Tự Động / Co-Pilot / TẮT Bot)
async function changeGlobalBotMode() {
    const select = document.getElementById('global-bot-mode-select');
    if (!select) return;
    const newMode = select.value;
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/system/bot-mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: newMode })
        });
        
        const data = await response.json();
        if (data.success) {
            updateGlobalBotUI(newMode);
            const modeText = newMode === 'auto' ? '🟢 BẬT Tự Động (Auto)' : (newMode === 'copilot' ? '🟡 Co-Pilot (Nháp & Duyệt)' : '🔴 TẮT Bot (Tạm Dừng / Test)');
            showNotification(`Đã chuyển trạng thái Bot toàn hệ thống sang: ${modeText}`);
        } else {
            showNotification(data.message || "Không thể đổi trạng thái", "warning");
        }
    } catch (e) {
        showNotification("Lỗi kết nối máy chủ", "warning");
    }
}

// Thay đổi chế độ của phiên chat cá nhân
async function changeSessionMode() {
    if (!activeSessionId) return;
    
    const select = document.getElementById('session-mode-select');
    const newMode = select.value;
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/session/${activeSessionId}/mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: newMode })
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification(`Đã chuyển sang chế độ ${newMode === 'auto' ? 'Tự Động' : (newMode === 'copilot' ? 'Co-Pilot' : 'Agent Takeover')}`);
            updateActiveLiveSessionDetail(true);
        }
    } catch (e) {
        showNotification("Lỗi kết nối khi đổi chế độ", "warning");
    }
}

// Gửi tin nhắn tay trực tiếp cho khách hàng (Agent Takeover)
async function sendLiveManualMessage() {
    if (!activeSessionId) return;
    
    const input = document.getElementById('live-chat-input');
    const text = input.value.trim();
    if (!text) return;
    
    input.value = '';
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/session/${activeSessionId}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification("Đã gửi tin nhắn trực tiếp!");
            document.getElementById('session-mode-select').value = 'manual';
            updateActiveLiveSessionDetail(true);
        } else {
            showNotification("Lỗi: " + data.message, "warning");
        }
    } catch (e) {
        showNotification("Lỗi kết nối server.", "warning");
    }
}

// Duyệt tin nhắn nháp của Bot
async function approveLiveDraft() {
    if (!activeSessionId) return;
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/session/${activeSessionId}/approve`, {
            method: 'POST'
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification("Đã duyệt và gửi tin nhắn!");
            updateActiveLiveSessionDetail(true);
        } else {
            showNotification("Lỗi: " + data.message, "warning");
        }
    } catch (e) {
        showNotification("Lỗi kết nối server.", "warning");
    }
}

// Chỉnh sửa và gửi tin nhắn nháp (đồng thời dạy Bot học)
async function editSendLiveDraft() {
    if (!activeSessionId) return;
    
    const draftTextarea = document.getElementById('live-draft-textarea');
    const text = draftTextarea.value.trim();
    if (!text) return;
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/session/${activeSessionId}/edit_send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification("Đã sửa, gửi và dạy Bot bài học thành công!");
            updateActiveLiveSessionDetail(true);
            loadLiveBrainLessons();
        } else {
            showNotification("Lỗi: " + data.message, "warning");
        }
    } catch (e) {
        showNotification("Lỗi kết nối server.", "warning");
    }
}

// Tải danh sách tri thức thực tế
async function loadLiveBrainLessons() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/knowledge`);
        const data = await response.json();
        
        if (!data.success) return;
        
        let html = '';
        
        data.manual.forEach((l, idx) => {
            html += `
            <div class="lesson-card" style="position:relative;">
                <button class="live-lessons-list-item-delete" onclick="deleteLiveLesson(${idx})" title="Xoá tri thức này">🗑️</button>
                <div class="lesson-meta">
                    <span class="badge learned">Đã dạy tay</span>
                </div>
                <div class="lesson-qa">
                    <div><strong>Hỏi:</strong> "${l.question}"</div>
                    <div><strong>Bot sẽ đáp:</strong> "${formatResponseForPreview(l.answer)}"</div>
                </div>
            </div>
            `;
        });
        
        data.original.forEach(l => {
            html += `
            <div class="lesson-card default">
                <div class="lesson-meta">
                    <span class="badge default">Tri thức gốc</span>
                </div>
                <div class="lesson-qa">
                    <div><strong>Hỏi:</strong> "${l.question}"</div>
                    <div><strong>Bot sẽ đáp:</strong> "${formatResponseForPreview(l.answer)}"</div>
                </div>
            </div>
            `;
        });
        
        const container = document.getElementById('live-brain-lessons-container');
        if (container) {
            container.innerHTML = html;
        }
    } catch (e) {
        console.error("Lỗi tải tri thức thực tế:", e);
    }
}

// Xoá một tri thức thực tế đã học
async function deleteLiveLesson(index) {
    if (!confirm("Bạn có chắc chắn muốn xoá tri thức đã dạy này không?")) return;
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/knowledge`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ index: index })
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification("Đã xoá tri thức thành công!");
            loadLiveBrainLessons();
        } else {
            showNotification("Lỗi: " + data.message, "warning");
        }
    } catch (e) {
        showNotification("Lỗi kết nối khi xoá tri thức.", "warning");
    }
}

// Đồng bộ tri thức từ Excel Master
async function syncExcelMaster() {
    const btn = document.getElementById('btn-sync-excel');
    const oldText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '🔄 Đang đồng bộ...';
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/sync-excel`, {
            method: 'POST'
        });
        const data = await response.json();
        if (data.success) {
            showNotification("Đồng bộ Excel Master thành công!");
            loadLiveBrainLessons();
        } else {
            showNotification("Lỗi đồng bộ: " + data.message, "warning");
        }
    } catch (e) {
        showNotification("Lỗi kết nối server.", "warning");
    } finally {
        btn.disabled = false;
        btn.innerHTML = oldText;
    }
}

// Lọc các phiên chat
function filterLiveSessions() {
    const query = document.getElementById('channels-search-input').value.toLowerCase();
    const items = document.querySelectorAll('.channel-item');
    
    items.forEach(item => {
        const name = item.querySelector('.channel-name').textContent.toLowerCase();
        const msg = item.querySelector('.channel-item-last-msg').textContent.toLowerCase();
        
        if (name.includes(query) || msg.includes(query)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

// Ráp phím enter cho live chat input
document.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        const liveInput = document.getElementById('live-chat-input');
        if (liveInput && document.activeElement === liveInput) {
            sendLiveManualMessage();
        }
    }
});

// Gửi ảnh hoặc file trực tiếp cho khách hàng (Agent Takeover)
async function uploadLiveMedia(inputElement) {
    if (!activeSessionId) return;
    const file = inputElement.files[0];
    if (!file) return;
    
    const clearInput = () => { inputElement.value = ''; };
    
    const formData = new FormData();
    formData.append('file', file);
    
    showNotification("Đang gửi ảnh/file...", "info");
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/session/${activeSessionId}/media`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification("Đã gửi ảnh/file trực tiếp!");
            document.getElementById('session-mode-select').value = 'manual';
            updateActiveLiveSessionDetail(true);
        } else {
            showNotification("Lỗi gửi: " + data.message, "warning");
        }
    } catch (e) {
        showNotification("Lỗi kết nối server khi gửi tệp.", "warning");
    } finally {
        clearInput();
    }
}

// ===================================================================
// EASY TRIP & VISA - OPERATIONS SOP & CALCULATOR HANDLERS
// ===================================================================

// Hàm sao chép văn bản vào clipboard
function copyText(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    
    let textVal = el.innerText || el.textContent || el.value;
    
    // Tạo textarea tạm thời để copy
    const tempTextarea = document.createElement('textarea');
    tempTextarea.value = textVal;
    document.body.appendChild(tempTextarea);
    tempTextarea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            showNotification('Đã sao chép vào bộ nhớ tạm!');
        } else {
            showNotification('Lỗi khi sao chép.', 'warning');
        }
    } catch (err) {
        showNotification('Lỗi trình duyệt không hỗ trợ sao chép.', 'warning');
    }
    
    document.body.removeChild(tempTextarea);
}

// Chuyển đổi giữa các tab cẩm nang vận hành (phía cột phải)
function switchSopTab(tabId) {
    // Ẩn tất cả các panels
    document.querySelectorAll('.sop-tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    // Bỏ kích hoạt tất cả các nút
    document.querySelectorAll('.sop-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Hiện panel và active nút được chọn
    const activePanel = document.getElementById(tabId);
    const activeBtn = document.getElementById(`sop-tab-btn-${tabId.split('-')[1]}`);
    if (activePanel) activePanel.classList.add('active');
    if (activeBtn) activeBtn.classList.add('active');
    
    // Tải dữ liệu tương ứng khi đổi tab
    if (tabId === 'sop-greeting') {
        updateGreetingTemplate();
    } else if (tabId === 'sop-payment') {
        updatePaymentTemplate();
    } else if (tabId === 'sop-feedback') {
        updateFeedbackTemplate();
    }
}

// Chuyển đổi giữa các hướng dẫn cửa khẩu
function showBorderGuide(guideId) {
    document.querySelectorAll('.guide-content').forEach(g => {
        g.classList.remove('active');
    });
    document.querySelectorAll('.btn-route-select').forEach(btn => {
        btn.classList.remove('active');
    });
    
    const guideEl = document.getElementById(`guide-${guideId}`);
    if (guideEl) guideEl.classList.add('active');
    
    const btnEl = document.getElementById(`btn-guide-${guideId}`);
    if (btnEl) btnEl.classList.add('active');
}

// Hàm kiểm tra quốc tịch có thuộc khối CIS hoặc nhóm ưu đãi đặc biệt (Nga, Belarus, Ukraine, Trung Á...)
function isCISGroup(nationality) {
    if (!nationality) return false;
    const norm = removeVietnameseTones(nationality).toLowerCase();
    const cisKws = ['nga', 'russia', 'kyrgyz', 'kazakh', 'uzbek', 'ukrain', 'tajik', 'belarus', 'armenia', 'azerbaijan', 'moldova', 'turkmenistan', 'cis', 'sng'];
    return cisKws.some(kw => norm.includes(kw));
}

// Bộ tính phí và lộ trình tự động
function calculateOps() {
    const custName = document.getElementById('ops-cust-name').value.trim() || 'John Doe';
    const nationalityRaw = document.getElementById('ops-nationality').value.trim();
    const city = document.getElementById('ops-city').value;
    const expiryVal = document.getElementById('ops-expiry').value;
    const visaType = document.getElementById('ops-visa-type').value;
    const entryType = document.getElementById('ops-entry-type').value;
    const transport = document.getElementById('ops-transport').value;
    const adults = parseInt(document.getElementById('ops-adults').value) || 1;
    const children = parseInt(document.getElementById('ops-children').value) || 0;
    const fasttrack = document.getElementById('ops-fasttrack').value;
    const isLoyalty = document.getElementById('ops-loyalty').checked;
    const isUrgent24h = document.getElementById('ops-urgent-24h').checked;

    let route = '--';
    let basePrice = 0;
    let surchargeNation = 0;
    let surchargeMulti = 0;
    let surchargeFasttrack = 0;
    let total = 0;
    
    let isDifficultNation = false;
    let difficultNationType = ''; // '850k' or '650k'

    // 1. Phân loại lộ trình dựa vào quốc tịch
    if (nationalityRaw) {
        const natNorm = removeVietnameseTones(nationalityRaw).toLowerCase();
        
        // Tự động chuyển đổi ngôn ngữ cẩm nang/tin nhắn mẫu
        let autoLang = 'en'; // mặc định tiếng Anh
        if (natNorm.includes('nga') || natNorm.includes('russia')) {
            autoLang = 'ru';
        } else if (natNorm.includes('han') || natNorm.includes('korea')) {
            autoLang = 'kr';
        } else if (natNorm.includes('phap') || natNorm.includes('france')) {
            autoLang = 'fr';
        } else if (natNorm.includes('viet') || natNorm.includes('kinh')) {
            autoLang = 'vi';
        } else if (natNorm.includes('ai cap') || natNorm.includes('egypt') || natNorm.includes('arab') || natNorm.includes('morocco') || natNorm.includes('ma roc') || natNorm.includes('tunisia') || natNorm.includes('uae')) {
            autoLang = 'ar';
        }
        
        const langSelect = document.getElementById('greet-lang-select');
        if (langSelect && langSelect.value !== autoLang) {
            langSelect.value = autoLang;
            changeSopLanguage();
        }

        // Nhóm đi Lào (Miễn visa Lào)
        const laosKws = ['nga', 'russia', 'han quoc', 'korea', 'belarus', 'malaysia', 'czech', 'sec', 'asean', 'thailand', 'singapore', 'philippines', 'indonesia', 'myanmar', 'cambodia', 'laos'];
        let matchesLaos = false;
        laosKws.forEach(kw => {
            if (natNorm.includes(kw)) matchesLaos = true;
        });
        
        if (matchesLaos) {
            if (isArabicUI) {
                route = 'نها ترانغ ↔ لاوس (معبر بو إي الحدودي)';
            } else if (isFrenchUI) {
                route = 'Nha Trang ↔ LAOS (Frontière de Bo Y)';
            } else {
                route = 'Nha Trang ↔ LÀO (Cửa khẩu Bờ Y)';
            }
        } else {
            if (isArabicUI) {
                route = 'نها ترانغ ↔ كمبوديا (معبر موk باي الحدودي)';
            } else if (isFrenchUI) {
                route = 'Nha Trang ↔ CAMBODGE (Frontière de Moc Bai)';
            } else {
                route = 'Nha Trang ↔ CAMPUCHIA (Cửa khẩu Mộc Bài)';
            }
        }
        
        // Nhóm phụ phí quốc tịch khó
        const difficult850 = ['ai cap', 'egypt', 'algeria', 'tunisia', 'tunusia', 'sri lanka', 'srilanka', 'mauritius'];
        const difficult650 = ['tho nhi ky', 'turkey', 'morocco', 'morroco', 'ma roc', 'uae', 'cac tieu vuong quoc arab thong nhat'];
        
        difficult850.forEach(kw => {
            if (natNorm.includes(kw)) {
                isDifficultNation = true;
                difficultNationType = '850k';
            }
        });
        
        difficult650.forEach(kw => {
            if (natNorm.includes(kw)) {
                isDifficultNation = true;
                difficultNationType = '650k';
            }
        });
    } else {
        if (isArabicUI) {
            route = 'يرجى إدخال الجنسية';
        } else if (isFrenchUI) {
            route = 'Veuillez saisir la nationalité';
        } else {
            route = 'Vui lòng nhập quốc tịch';
        }
    }

    // Kiểm tra và tự động đổi gói Free Visa nếu quốc tịch không được miễn thị thực vào VN
    const isExemptVN = isVietnamVisaExempt(nationalityRaw);
    const visaWarningEl = document.getElementById('ops-visa-warning');
    
    if (!isExemptVN && nationalityRaw) {
        const visaSelect = document.getElementById('ops-visa-type');
        if (visaType === 'visarun-laos-45d') {
            visaSelect.value = 'visarun-laos-90d';
        } else if (visaType === 'visarun-cambodia-45d') {
            visaSelect.value = 'visarun-cambodia-90d';
        }
        if (visaWarningEl) {
            let warnMsg = "⚠️ Quốc tịch này không được miễn thị thực VN, không thể chọn gói 45 ngày.";
            if (isArabicUI) {
                warnMsg = "⚠️ هذه الجنسية غير معفاة من تأشيرة فيتنام، لا يمكن اختيار إعفاء 45 يومًا.";
            } else if (isFrenchUI) {
                warnMsg = "⚠️ Cette nationalité n'est pas exemptée de visa pour le VN, le forfait de 45 jours n'est pas disponible.";
            }
            visaWarningEl.textContent = warnMsg;
            visaWarningEl.style.display = 'block';
        }
    } else {
        if (visaWarningEl) visaWarningEl.style.display = 'none';
    }

    // Lấy lại giá trị visaType sau khi đã tự động điều chỉnh ở trên
    const finalVisaType = document.getElementById('ops-visa-type').value;

    // 2. Tính toán Giá nền theo đúng 4 bảng giá Website (/english, /korean, /russian, /arabic)
    const isLaos = route.includes('LÀO') || route.includes('LAOS') || route.includes('لاوس');
    const isCIS = isCISGroup(nationalityRaw);
    const natNormLower = nationalityRaw ? removeVietnameseTones(nationalityRaw).toLowerCase() : '';
    const isArabNat = ['arab', 'saudi', 'uae', 'emirates', 'egypt', 'ai cap', 'qatar', 'kuwait', 'oman', 'bahrain', 'jordan', 'iraq', 'morocco', 'ma roc', 'algeria', 'tunisia', 'tunusia'].some(k => natNormLower.includes(k));
    const tierSelect = document.getElementById('ops-market-tier');
    const selectedTier = tierSelect ? tierSelect.value : 'auto';
    const marketTier = selectedTier === 'auto' ? (isArabNat ? 'ar' : (isCIS ? 'ru' : 'en_kr')) : selectedTier;
    const isArabicTier = marketTier === 'ar';
    const isRussianTier = marketTier === 'ru';
    
    let adultPrice = 0;
    let childPrice = 0;

    if (finalVisaType.startsWith('visarun-')) {
        const isExempt = finalVisaType.endsWith('-45d');
        const isDaNang = city === 'Da Nang';
        let standardAdultPackPrice = 4000000;
        if (isExempt) {
            standardAdultPackPrice = isDaNang ? (isLoyalty ? 850000 : 950000) : (isLoyalty ? 1300000 : 1400000);
        } else if (isDaNang) {
            standardAdultPackPrice = isLoyalty ? 3550000 : (isArabicTier ? 5300000 : 3800000);
        } else if (isArabicTier) {
            standardAdultPackPrice = isLoyalty ? 3550000 : (isLaos ? 5500000 : 6500000);
        } else if (isRussianTier) {
            standardAdultPackPrice = isLoyalty ? 3000000 : (isLaos ? 3400000 : 4400000);
        } else {
            standardAdultPackPrice = isLoyalty ? 3550000 : (isLaos ? 4000000 : 5000000);
        }
        const busTicketPrice = isDaNang ? (isLoyalty ? 850000 : 950000) : (isLoyalty ? 1300000 : 1400000);
        
        // Adult Price calculation
        if (transport === 'no') {
            if (isExempt) {
                adultPrice = 0;
            } else {
                adultPrice = isRussianTier ? 2000000 : Math.max(0, standardAdultPackPrice - busTicketPrice);
            }
        } else {
            adultPrice = standardAdultPackPrice;
        }

        // Child under 9 Price calculation (bus ticket is free 0 VND, E-visa portion only)
        if (isExempt) {
            childPrice = 0;
        } else {
            childPrice = isLoyalty ? 1480000 : (isArabicTier ? 2980000 : 1480000);
        }
        
        basePrice = (adults * adultPrice) + (children * childPrice);
    } else {
        // E-Visa khẩn cấp / tiêu chuẩn theo từng thị trường Website
        const pricingTableEnKr = {
            'ev-1h': { standard: 4600000, loyalty: 3300000 },
            'ev-2h': { standard: 3400000, loyalty: 2900000 },
            'ev-3h': { standard: 3000000, loyalty: 2500000 },
            'ev-4h': { standard: 2600000, loyalty: 1600000 },
            'ev-8h': { standard: 2900000, loyalty: 1900000 },
            'ev-1d': { standard: 2200000, loyalty: 1500000 },
            'ev-2d': { standard: 2150000, loyalty: 1450000 },
            'ev-std': { standard: 1810000, loyalty: 1110000 }
        };
        const pricingTableRu = {
            'ev-1h': { standard: 4600000, loyalty: 3300000 },
            'ev-2h': { standard: 3400000, loyalty: 2900000 },
            'ev-3h': { standard: 3000000, loyalty: 2500000 },
            'ev-4h': { standard: 2000000, loyalty: 1600000 },
            'ev-8h': { standard: 2200000, loyalty: 1800000 },
            'ev-1d': { standard: 1810000, loyalty: 1500000 },
            'ev-2d': { standard: 1760000, loyalty: 1450000 },
            'ev-std': { standard: 1610000, loyalty: 1110000 }
        };
        const table = isRussianTier ? pricingTableRu : pricingTableEnKr;
        const p = table[finalVisaType] || table['ev-std'];
        let evPrice = isLoyalty ? p.loyalty : p.standard;
        if (!isLoyalty && isArabicTier) {
            evPrice += 1500000;
        }
        basePrice = (adults + children) * evPrice;
    }

    // 3. Tính toán Phụ phí (Nhân với tổng số lượng khách)
    const totalPax = adults + children;
    if (isDifficultNation) {
        surchargeNation = (difficultNationType === '850k' ? 850000 : 650000) * totalPax;
    }
    
    // Nếu chọn Multi entry và dịch vụ hỗ trợ multi (không phải 45D exemption)
    const isExemption = finalVisaType.endsWith('-45d');
    if (entryType === 'multi' && !isExemption) {
        surchargeMulti = 1000000 * totalPax;
    } else {
        if (isExemption && entryType === 'multi') {
            document.getElementById('ops-entry-type').value = 'single';
        }
    }
    
    if (fasttrack !== 'none') {
        let ftPrice = 1855000; // $70 (CXR, DAD, PQC, VDO, HPH, HUI, VII, DLI, VCA)
        if (fasttrack === 'SGN' || fasttrack === 'HAN') {
            ftPrice = isLoyalty ? 675000 : 1200000;
        } else if (fasttrack === 'LAO_BORDER') {
            ftPrice = 300000;
        } else if (isLoyalty) {
            ftPrice = 540000;
        }
        surchargeFasttrack = ftPrice * totalPax;
    }

    total = basePrice + surchargeNation + surchargeMulti + surchargeFasttrack;

    // 4. Tính toán ngày đi (Hạn visa - 1 ngày)
    let departureDateStr = 'Đang chờ nhập ngày...';
    let formattedDepDate = '';
    const dateWarningEl = document.getElementById('ops-date-warning');

    if (expiryVal) {
        const expiryDate = new Date(expiryVal);
        const departureDate = new Date(expiryDate);
        departureDate.setDate(expiryDate.getDate() - 1);
        
        const dd = String(departureDate.getDate()).padStart(2, '0');
        const mm = String(departureDate.getMonth() + 1).padStart(2, '0');
        const yyyy = departureDate.getFullYear();
        formattedDepDate = `${dd}/${mm}/${yyyy}`;
        
        const depDayOfWeek = departureDate.getDay();
        const weekdays = ['Chủ Nhật', 'Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7'];
        departureDateStr = `${formattedDepDate} (${weekdays[depDayOfWeek]})`;
        
        if (!isLaos && nationalityRaw && (depDayOfWeek !== 0 && depDayOfWeek !== 2 && depDayOfWeek !== 4)) {
            if (dateWarningEl) {
                dateWarningEl.textContent = "⚠️ Xe đi Campuchia chỉ khởi hành vào Thứ 3, Thứ 5, Chủ Nhật.";
                dateWarningEl.style.display = 'block';
            }
        } else if ((finalVisaType === 'ev-4h' || finalVisaType === 'ev-8h') && (depDayOfWeek === 0 || depDayOfWeek === 6)) {
            if (dateWarningEl) {
                dateWarningEl.textContent = "⚠️ E-Visa 4–8h không xử lý cuối tuần (T7/CN) & ngày lễ. Hoàn 100% nếu trễ hạn GMT+7.";
                dateWarningEl.style.display = 'block';
            }
        } else {
            if (dateWarningEl) dateWarningEl.style.display = 'none';
        }
    } else if (finalVisaType === 'ev-4h' || finalVisaType === 'ev-8h') {
        const todayDow = new Date().getDay();
        if ((todayDow === 0 || todayDow === 6) && dateWarningEl) {
            dateWarningEl.textContent = "⚠️ Hôm nay là cuối tuần (T7/CN): gói 4–8h tạm nghỉ cuối tuần, hãy báo khách liên hệ WhatsApp/Telegram nếu khẩn.";
            dateWarningEl.style.display = 'block';
        } else if (dateWarningEl) {
            dateWarningEl.style.display = 'none';
        }
    } else if (dateWarningEl) {
        dateWarningEl.style.display = 'none';
    }

    // 5. Tính toán E-visa Khẩn Cấp dựa trên thời gian có dấu xuất cảnh
    const emergencyBox = document.getElementById('ops-emergency-box');
    const urgentPackageRow = document.getElementById('calc-urgent-package-row');
    const urgentPackageNameEl = document.getElementById('calc-urgent-package-name');
    const emergencyWarningEl = document.getElementById('ops-emergency-warning');

    if (finalVisaType.startsWith('ev-') && finalVisaType !== 'ev-std' && finalVisaType !== 'ev-2d' && finalVisaType !== 'ev-1d') {
        if (emergencyBox) emergencyBox.style.display = 'block';
        if (urgentPackageRow) urgentPackageRow.style.display = 'flex';
        
        const stampTimeStr = document.getElementById('ops-stamp-time').value;
        const releaseTimeStr = document.getElementById('ops-release-time').value;
        
        const [stampH, stampM] = stampTimeStr.split(':').map(Number);
        const stampMinutes = stampH * 60 + stampM;
        
        let recommendedPackage = 'ev-std';
        let recommendedName = 'Không khả dụng gói khẩn cấp cùng ngày';
        let warnMsg = '';

        if (releaseTimeStr === '11:30') {
            if (stampMinutes > 11 * 60) {
                warnMsg = "⚠️ Thời điểm nộp/dấu xuất cảnh sau 11:00 sáng. Vui lòng chuyển sang khung giờ chiều 17:30.";
                recommendedName = "N/A";
            } else {
                if (stampMinutes <= 8 * 60 + 30) {
                    recommendedPackage = 'ev-4h';
                    recommendedName = "Gói khẩn cấp 4 tiếng (Dấu xuất cảnh trễ nhất 8:30)";
                } else if (stampMinutes <= 9 * 60) {
                    recommendedPackage = 'ev-3h';
                    recommendedName = "Gói khẩn cấp 3 tiếng (Nhận dấu trước 9:00)";
                } else if (stampMinutes <= 10 * 60) {
                    recommendedPackage = 'ev-2h';
                    recommendedName = "Gói khẩn cấp 2 tiếng (Nhận dấu trước 10:00)";
                } else if (stampMinutes <= 11 * 60) {
                    recommendedPackage = 'ev-1h';
                    recommendedName = "Gói khẩn cấp 1 tiếng (Nhận dấu trước 11:00)";
                }
            }
        } else {
            // Chiều 17:30
            if (stampMinutes > 16 * 60 + 30) {
                warnMsg = "⚠️ Nộp/dấu xuất cảnh sau 16:30. Không thể nhận kết quả trong ngày, vui lòng chuyển sang ngày hôm sau.";
                recommendedName = "N/A";
            } else {
                if (stampMinutes <= 14 * 60) {
                    recommendedPackage = 'ev-4h';
                    recommendedName = "Gói khẩn cấp 4 tiếng (Dấu xuất cảnh trễ nhất 14:00)";
                } else if (stampMinutes <= 15 * 60) {
                    recommendedPackage = 'ev-2h';
                    recommendedName = "Gói khẩn cấp 2 tiếng hoặc 3 tiếng (Dấu trước 15:00)";
                } else if (stampMinutes <= 16 * 60 + 30) {
                    recommendedPackage = 'ev-1h';
                    recommendedName = "Gói khẩn cấp 1 tiếng (Dấu trước 16:30)";
                }
            }
        }

        if (urgentPackageNameEl) urgentPackageNameEl.textContent = recommendedName;
        if (emergencyWarningEl) {
            if (warnMsg) {
                emergencyWarningEl.textContent = warnMsg;
                emergencyWarningEl.style.display = 'block';
            } else {
        emergencyWarningEl.style.display = 'none';
            }
        }
    } else {
        if (emergencyBox) emergencyBox.style.display = 'none';
        if (urgentPackageRow) urgentPackageRow.style.display = 'none';
    }

    if (isUrgent24h) {
        if (emergencyWarningEl) {
            emergencyWarningEl.textContent = "⚠️ Đăng ký khẩn cấp trước 24 tiếng. Cần thỏa thuận lại mức giá và điều khoản!";
            emergencyWarningEl.style.display = 'block';
        }
    }

    // 5. Cập nhật giao diện Kết quả
    document.getElementById('calc-route').textContent = route;
    document.getElementById('calc-departure').textContent = departureDateStr;
    document.getElementById('calc-surcharge-nation').textContent = surchargeNation.toLocaleString('vi-VN') + ' VND';
    document.getElementById('calc-surcharge-multi').textContent = surchargeMulti.toLocaleString('vi-VN') + ' VND';
    document.getElementById('calc-surcharge-fasttrack').textContent = surchargeFasttrack.toLocaleString('vi-VN') + ' VND';
    document.getElementById('calc-total').textContent = total.toLocaleString('vi-VN') + ' VND';

    // 6. Tạo lệnh Command Copy Telegram/WhatsApp
    const depDateShort = formattedDepDate ? formattedDepDate.substring(0, 5) : '[Ngày/Tháng]';
    
    // Command 1: Lệnh đăng ký Bus General
    const visaCode = finalVisaType.includes('45d') ? '45D' : '90D';
    const destCode = isLaos ? 'Laos' : 'Cambodia';
    const paxDetails = children > 0 ? `${adults}L+${children}TE` : `${adults} khách`;
    document.getElementById('cmd-bus-booking').textContent = `Scheme ${depDateShort} - ${visaCode} ${destCode} x ${paxDetails}`;

    // Command 2: Lệnh khóa ghế
    const seatLockCmd = 
`${depDateShort} - ${visaCode} ${destCode}
${custName} x ${adults} ghế ${children > 0 ? `(+ ${children} trẻ em nằm chung cabin)` : ''}
Số ghế: [Đợi nhà xe cập nhật sơ đồ]
Điểm đón: [Chọn ví dụ: 40 Hòn Chồng Nha Trang]
Nguồn: Zalo/WhatsApp
Trạng thái: Unpaid (Cần thanh toán trước 14:00 ngày đi)`;
    document.getElementById('cmd-seat-lock').textContent = seatLockCmd;

    // Command 3: Chi tiết nộp EV WhatsApp
    const entryBorder = isLaos ? 'Bờ Y' : 'Mộc Bài';
    const evType = (entryType === 'multi') ? 'MULTI' : 'SINGLE';
    const evApplyCmd = 
`${evType}
E-VISA 90 ngày x ${totalPax} khách ${children > 0 ? `(${adults} người lớn, ${children} trẻ em)` : ''}
${depDateShort} - 8:00 exit ${entryBorder}
${depDateShort} - 11:30 enter ${entryBorder}
EFFECTIVE DATE EV: ${depDateShort}`;
    document.getElementById('cmd-ev-apply').textContent = evApplyCmd;
}

function onVisaTypeChange() {
    calculateOps();
}

// 7. Cấu hình cẩm nang đa ngôn ngữ (Cập nhật dữ liệu từ Google Sheet)
const greetingTemplates = {
    vi: {
        greet: `Welcome to Easy Trip & Visa Co. Ltd, the only legitimate visarun service in Vietnam.
Business registration number: 4202051389.
Please tell us: your nationality, the city you are currently staying in Vietnam, and your visa expiry date!
* Nhằm cung cấp trải nghiệm dịch vụ tốt nhất xin quý khách hãy cho chúng tôi biết dịch vụ mà bạn muốn sử dụng: Free visa 45 hay E-visa 90 ngày (Áp dụng cho khách hàng đến từ các quốc gia được miễn thị thực Việt Nam).`,
        route: `🚌 Lựa chọn lộ trình phù hợp dựa vào quốc tịch:

👉 TUYẾN LÀO (Cửa khẩu Bờ Y): Dành cho các quốc tịch được miễn visa Lào (Nga, Hàn Quốc, Belarus, Malaysia, Czech, ASEAN...).
- Free Visa 45 ngày Lào: Vé xe buýt khởi hành hàng ngày lúc 21:30 tại 40 Hòn Chồng (https://maps.app.goo.gl/XCinCHmvwBAT5x7Q7). Giá: 1.400.000 VND.
- E-Visa 90 ngày Lào: Xe chạy tối Thứ 3, Thứ 5, Chủ Nhật hàng tuần lúc 21:30. Giá người Nga: Khách Mới 3.400.000 VND (Single) / 4.400.000 VND (Multi) | Khách Cũ 3.000.000 VND (Single) / 4.000.000 VND (Multi).

👉 TUYẾN CAMPUCHIA (Cửa khẩu Mộc Bài): Dành cho các quốc tịch còn lại (Mỹ, Anh, Úc, Canada, Ukraine, Kyrgyz, Brazil...).
- Vé xe buýt (45 ngày hoặc 90 ngày) khởi hành tối Thứ 3, Thứ 5, Chủ Nhật hàng tuần lúc 21:30 tại 40 Hòn Chồng (Bản đồ: https://maps.app.goo.gl/AUkyctD6mwBtkiBF7).
- Giá xe buýt đi Campuchia 45 ngày: 1.400.000 VND.
- Giá xe buýt + E-visa Việt Nam 90 ngày: 4.000.000 VND.`,
        danang: `🚌 LỘ TRÌNH ĐÀ NẴNG - LAO BẢO (E-Visa 90 Phút):
1. Khởi hành: Có mặt trước 15-30 phút. Đón lúc 5:45 sáng tại Bến xe trung tâm Đà Nẵng (Định vị: https://maps.app.goo.gl/ioAj2jBXYm31yC7s5).
2. Có mặt tại cửa khẩu Lao Bảo lúc 10:30 sáng cùng ngày.
3. Phí đóng dấu: Quý khách chuẩn bị 200.000 VND tiền mặt gửi cho Hanie (nhân viên hỗ trợ của chúng tôi tại cửa khẩu).
4. Nhận visa điện tử trong vòng 90 phút (dự kiến hoàn tất trước 12:15 trưa).
5. Trở về Đà Nẵng lúc 18:00 chiều.
💰 Chi phí trọn gói:
- 3.550.000 VND (Đăng ký trước ngày khởi hành ít nhất 03 ngày).
- 3.800.000 VND (Hồ sơ xử lý khẩn cấp).`
    },
    en: {
        greet: `Welcome to Easy Trip & Visa Co. Ltd, the only legitimate visarun service in Vietnam.
Business registration number: 4202051389.
Please tell us: your nationality, the city you are currently staying in Vietnam, and your visa expiry date!
* To provide you with the best service, please tell us which service you want to use: Free visa 45 days or E-visa 90 days (Applicable to countries exempt from Vietnam visa).`,
        route: `🚌 Recommended Route Options:

👉 LAOS ROUTE (Bo Y border): Recommended for nationalities exempt from Laos visa (Russia, South Korea, Belarus, Malaysia, Czech Republic, ASEAN...).
- Free Visa 45 days Laos: Bus departs daily at 9:30 PM from 40 Hon Chong (https://maps.app.goo.gl/XCinCHmvwBAT5x7Q7). Cost: 1,400,000 VND.
- E-Visa 90 days Laos: Bus departs Tue, Thu, Sun at 9:30 PM. Cost: 3,400,000 VND.

👉 CAMBODIA ROUTE (Moc Bai border): Recommended for other nationalities (USA, UK, Australia, Canada, Ukraine, Brazil...).
- Bus departs Tue, Thu, Sun at 9:30 PM from 40 Hon Chong (Map: https://maps.app.goo.gl/AUkyctD6mwBtkiBF7).
- Cambodia 45 days cost: 1,400,000 VND (excl. Cambodia visa fee).
- Cambodia 90 days E-visa package: 4,000,000 VND (includes bus round trip + urgent 4h Vietnam E-visa).`,
        danang: `🚌 DA NANG - LAO BAO BORDER RUN (90-Minute E-Visa):
1. Departure: Be present 15-30 mins early. Pickup at 5:45 AM at Da Nang Central Bus Station (https://maps.app.goo.gl/ioAj2jBXYm31yC7s5).
2. Arrival at Lao Bao Border around 10:30 AM on the same day.
3. Stamping fee: Prepare 200,000 VND cash to give to Hanie (our checkpoint support staff).
4. E-visa processed within 90 minutes (completed by 12:15 PM).
5. Arrival back in Da Nang at 6:00 PM.
💰 Cost:
- 3,550,000 VND (registered at least 3 days in advance).
- 3,800,000 VND (urgent same-day processing).`
    }
};

const reqDocsTemplates = {
    vi: `📷 HƯỚNG DẪN CUNG CẤP HỒ SƠ LÀM E-VISA:
Xin quý khách vui lòng gửi cho chúng tôi:
1. Ảnh chụp trang thông tin hộ chiếu (Passport Bio Page).
2. Ảnh chân dung (ảnh chụp khuôn mặt để lộ rõ trán, mắt nhìn thẳng, không đeo kính).
🚨 Yêu cầu ảnh chụp hộ chiếu: Chụp vuông góc đủ 4 góc, rõ nét các ký tự, không bị lóa sáng và không có ngón tay xuất hiện trong ảnh.
* Đối với khách đi visarun hoặc bay đi Thái Lan/Malaysia trong ngày: Bắt buộc chụp ảnh dấu xuất cảnh (Exit Stamp) gửi cho chúng tôi ngay khi qua hải quan Việt Nam để bắt đầu xử lý visa khẩn cấp.`,
    en: `📷 PORTRAIT AND PASSPORT PHOTO GUIDELINES:
Please send us the following documents:
1. Scanned or clear photograph of your passport's information page (Bio Page).
2. A recent portrait photo (showing your face, forehead, and ears clearly, looking straight, no glasses).
🚨 Photo requirements: Must show all 4 corners of the passport page, clearly readable text, no glare, and no fingers holding the passport.
* For visarun or fly-out customers: Please send us a photo of your exit stamp immediately after exiting Vietnam boundary to start the emergency processing.`
};

const busDispatchTemplates = {
    vi: `🚍 THÔNG TIN XE BUÝT DÀNH CHO KHÁCH HÀNG:
Kính chào quý khách, chúng tôi xin thông báo thông tin xe buýt cho hành trình của bạn:
- Biển số xe buýt (License Plate): [Nhân viên nhập biển số thực tế]
- Điểm đón (Pickup): 40 Hòn Chồng, Bắc Nha Trang, Khánh Hòa.
  (Xem bản đồ: https://maps.app.goo.gl/AUkyctD6mwBtkiBF7)
- Giờ xuất phát (Departure): 21:30 PM (Vui lòng có mặt trước 15-30 phút).
- Mật khẩu Wi-Fi trên xe (Bus Wi-Fi Password): **19002679**`,
    en: `🚍 DEPARTURE BUS INFORMATION:
Dear customer, here is the bus details for your upcoming visa run:
- License Plate: [Staff insert license plate]
- Pickup location: 40 Hon Chong, North Nha Trang, Khanh Hoa.
  (View map: https://maps.app.goo.gl/AUkyctD6mwBtkiBF7)
- Departure time: 21:30 PM (Please arrive 15-30 minutes early).
- Bus Wi-Fi Password: **19002679**`
};

const paymentTemplates = {
    vi: `💰 THÔNG TIN THANH TOÁN EASY TRIP & VISA:
Quý khách có thể chọn thanh toán bằng chuyển khoản ngân hàng, USDT (crypto) hoặc tiền mặt VND/USD:

🏦 Ngân hàng: Vietcombank (VCB) / VRB
👤 Chủ tài khoản: EASY TRIP & VISA CO. LTD
🔢 Số tài khoản (VCB OneQR): QRPACQ1ZZZZ50600546
🔢 Số tài khoản thường: 1068582577
🌐 Mã SWIFT: BFTVVNVX
🪙 Crypto: Hỗ trợ thanh toán USDT

📍 Địa chỉ văn phòng Easy Trip & Visa Nha Trang: 21 Phan Vinh, Nha Trang.
(Định vị Google Maps: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9)

🚨 LƯU Ý QUAN TRỌNG:
- Thanh toán tiền xe buýt TRƯỚC 14:00 ngày khởi hành.
- E-Visa 4–8h không xử lý Thứ 7, Chủ Nhật & ngày lễ. Hoàn tiền 100% nếu không đạt đúng hạn GMT+7.
- Sau khi nhận thanh toán, nhân viên đóng dấu mộc đỏ công ty lên receipt và chụp ảnh gửi khách hàng.`,
    en: `💰 PAYMENT DETAILS — EASY TRIP & VISA CO. LTD:
You may pay via Bank Transfer, USDT (crypto), or Cash (VND / USD):

🏦 Bank: Vietcombank (VCB) / VRB
👤 Recipient: EASY TRIP & VISA CO. LTD
🔢 Account number (VCB OneQR): QRPACQ1ZZZZ50600546
🔢 Standard Account number: 1068582577
🌐 SWIFT Code: BFTVVNVX
🪙 Crypto: USDT accepted

📍 Office address in Nha Trang: 21 Phan Vinh, South Nha Trang.
(Google Maps: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9)

🚨 IMPORTANT NOTES:
- Bus ticket payment must be completed BEFORE 2:00 PM (14:00) on departure day.
- 4–8h urgent E-visa processing is unavailable on Sat/Sun & public holidays. 100% full refund if E-visa is not delivered within promised GMT+7 hours.
- We will issue a red-stamped confirmation receipt once payment is confirmed.`,
    ru: `💰 СПОСОБЫ ОПЛАТЫ — EASY TRIP & VISA CO. LTD:
Вы можете оплатить наличными (VND / USD), криптовалютой USDT или банковским переводом:

🏦 Банк: Vietcombank (VCB) / VRB
👤 Получатель: EASY TRIP & VISA CO. LTD
🔢 Номер счета (VCB OneQR): QRPACQ1ZZZZ50600546
🔢 Номер счета: 1068582577
🌐 SWIFT: BFTVVNVX
🪙 Криптовалюта: принимаем USDT

📍 Офис в Нячанге: 21 Phan Vinh, South Nha Trang.
(Карта: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9)

🚨 ВАЖНО:
- Оплата автобуса строго до 14:00 в день отправления.
- Срочные E-Visa 4–8ч не оформляются в сб/вс и праздники. Гарантия возврата 100% при несоблюдении сроков (GMT+7).`,
    ar: `💰 تفاصيل الدفع — EASY TRIP & VISA CO. LTD:
يمكنكم الدفع نقداً (VND / USD)، أو بعملة USDT، أو عبر التحويل البنكي:

🏦 البنك: Vietcombank (VCB) / VRB
👤 اسم الحساب: EASY TRIP & VISA CO. LTD
🔢 رقم الحساب: 1068582577
🌐 رمز SWIFT: BFTVVNVX
🪙 العملات الرقمية: نقبل الدفع بـ USDT

📍 عنوان المكتب في نها ترانج: 21 Phan Vinh, South Nha Trang.
(الخريطة: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9)

🚨 ملاحظات هامة:
- يجب دفع تذكرة الحافلة قبل الساعة 14:00 في يوم المغادرة.
- استرداد 100% في حال عدم استلام التأشيرة ضمن المدة المحددة (GMT+7).`
};

const feedbackTemplates = {
    vi: `✨ Cảm ơn quý khách đã tin tưởng và sử dụng dịch vụ của Easy Trip & Visa!
Nếu quý khách hài lòng, xin vui lòng gửi đánh giá ủng hộ chúng tôi trên Google Maps để nhận các ưu đãi lần sau:
🔗 https://g.page/r/CREMymPQwmBuEBI/review

Mọi góp ý hoặc phản hồi trực tiếp, vui lòng liên hệ:
👤 Mr. Ly Viet Hoang - Chairman, Easy Trip & Visa Co. Ltd
📞 +84 89 69 16 361 (Hỗ trợ tiếng Anh)`,
    en: `✨ Thank you for choosing Easy Trip & Visa!
If you are satisfied with our service, please leave us a positive review on Google Maps:
🔗 https://g.page/r/CREMymPQwmBuEBI/review

For direct feedback, please contact management:
👤 Mr. Ly Viet Hoang - Chairman, Easy Trip & Visa Co. Ltd
📞 +84 89 69 16 361 (باللغة الإنجليزية)`,
    fr: `✨ Merci de faire confiance à Easy Trip & Visa !

Si vous êtes satisfait, veuillez laisser un avis sur Google Maps :
🔗 https://g.page/r/CREMymPQwmBuEBI/review

Pour tout retour direct, veuillez contacter la direction :
👤 Mr. Ly Viet Hoang - Président, Easy Trip & Visa Co. Ltd
📞 +84 89 69 16 361 (Support en anglais)`
};

const warningTemplates = {
    vi: `🚨 CẢNH BÁO KIỂM TRA HẠN THỊ THỰC TẠI CỬA KHẨU:

Tránh việc nhân viên biên giới đóng dấu sai hạn lưu trú (không khớp E-visa), quý khách vui lòng KIỂM TRA THẬT KỸ ngày đóng dấu trên hộ chiếu trước khi rời quầy kiểm soát/cửa khẩu!`,
    en: `🚨 BORDER CONTROL ENTRY STAMP WARNING:

Please DOUBLE CHECK the entry stamp expiry date on your passport before leaving the border counter to ensure the officer stamped the correct date matching your E-visa.`,
    kr: `🚨 입국 심사 날짜 스탬프 확인 경고:

출입국 관리 직원의 업무 과다로 가끔 비자 기간과 다른 스탬프가 찍히는 경우가 발생합니다. 국경을 떠나기 전에 꼭 확인하시기 바랍니다.`,
    ru: `🚨 ВНИМАНИЕ: ПРОВЕРЯЙТЕ ДАТУ НА ШТАМПЕ!

Во избежание ошибок сотрудников погранконтроля, пожалуйста, внимательно ПРОВЕРЬТЕ дату окончания пребывания на штампе в паспорте перед тем, как покинуть пункт контроля.`,
    ar: `🚨 تحذير هام بشأن ختم الدخول عند المعبر الحدودي:

يرجى التحقق مرتين من تاريخ انتهاء الصلاحية الموضح على ختم الدخول في جواز سفرك قبل مغادرة شباك الجوازات لضمان تطابقه مع تأشيرة E-visa الخاصة بك.`,
    fr: `🚨 AVERTISSEMENT CONTRÔLE VISA À LA FRONTIÈRE :

Veuillez VERIFIER ATTENTIVEMENT la date d'expiration imprimée sur le tampon d'entrée de votre passeport avant de quitter le guichet frontalier pour vous assurer qu'elle correspond à votre E-visa.`
};

function updateFeedbackTemplate() {
    const langSelect = document.getElementById('greet-lang-select');
    const lang = langSelect ? langSelect.value : 'vi';
    const feedbackText = feedbackTemplates[lang] || feedbackTemplates.vi;
    const warningText = warningTemplates[lang] || warningTemplates.vi;
    
    const feedEl = document.getElementById('tmpl-feedback-text');
    const warnEl = document.getElementById('tmpl-warning-text');
    if (feedEl) feedEl.textContent = feedbackText;
    if (warnEl) warnEl.textContent = warningText;
}

function updateGreetingTemplate() {
    const langSelect = document.getElementById('greet-lang-select');
    const lang = langSelect ? langSelect.value : 'vi';
    const data = greetingTemplates[lang] || greetingTemplates.en || greetingTemplates.vi;
    
    const greetEl = document.getElementById('tmpl-greeting-text');
    const routeEl = document.getElementById('tmpl-route-text');
    if (greetEl) greetEl.textContent = data.greet;
    if (routeEl) routeEl.textContent = data.route;
}

function updatePaymentTemplate() {
    const langSelect = document.getElementById('greet-lang-select');
    const lang = langSelect ? langSelect.value : 'vi';
    const text = paymentTemplates[lang] || paymentTemplates.en || paymentTemplates.vi;
    const el = document.getElementById('tmpl-payment-text');
    if (el) el.textContent = text;
}

function updateReqDocsTemplate() {
    const langSelect = document.getElementById('greet-lang-select');
    const lang = langSelect ? langSelect.value : 'vi';
    const text = reqDocsTemplates[lang] || reqDocsTemplates.en || reqDocsTemplates.vi;
    const el = document.getElementById('tmpl-req-docs');
    if (el) el.textContent = text;
}

function updateBusDispatchTemplate() {
    const langSelect = document.getElementById('greet-lang-select');
    const lang = langSelect ? langSelect.value : 'vi';
    const text = busDispatchTemplates[lang] || busDispatchTemplates.en || busDispatchTemplates.vi;
    const el = document.getElementById('tmpl-bus-dispatch');
    if (el) el.textContent = text;
}

function updateDanangTemplate() {
    const langSelect = document.getElementById('greet-lang-select');
    const lang = langSelect ? langSelect.value : 'vi';
    const data = greetingTemplates[lang] || greetingTemplates.en || greetingTemplates.vi;
    const el = document.getElementById('tmpl-danang-text');
    if (el && data.danang) {
        el.textContent = data.danang;
    } else if (el) {
        // Fallback to english danang template if selected language doesn't have it
        const fallbackData = greetingTemplates.en || greetingTemplates.vi;
        el.textContent = fallbackData.danang || '';
    }
}

// Hàm điều phối thay đổi ngôn ngữ cẩm nang toàn cục
function changeSopLanguage() {
    updateGreetingTemplate();
    updatePaymentTemplate();
    updateFeedbackTemplate();
    updateReqDocsTemplate();
    updateBusDispatchTemplate();
    updateDanangTemplate();
}

// 8. LOGIC CHATBOT AI ĐÀO TẠO & HỎI ĐÁP NGHIỆP VỤ NHÂN VIÊN (Staff Internal Training & Helpdesk AI)
const staffAIDatabase = [
    {
        keywords: ['4 website', 'bang gia', 'arabic', 'a rap', 'korean', 'russian', 'english', 'english', 'fast track', '$70', '1.855'],
        answer: `🌍 **BẢNG GIÁ ĐỒNG BỘ 4 WEBSITE (/english, /korean, /russian, /arabic):**
1. **Quốc tế & Hàn Quốc (/english, /korean):**
   - Mộc Bài (T3/T5/CN 21:30): **6.000.000đ** (Multi+Cam) | **5.000.000đ** (Single+Cam) | **4.000.000đ** (Bus+90D EV, +1M Cam) | **1.400.000đ** (45D).
   - Bờ Y (Lào): **1.400.000đ** (45D hằng ngày) | **4.000.000đ** (90D không phải Nga).
   - Đà Nẵng–Lào Bảo: **3.800.000đ** (90D, đặt >=3d còn 3.550.000đ) | **950.000đ** (45D).
   - E-visa lẻ: 1h 4.6M | 2h 3.4M | 4h 2.6M | 8h 2.9M | 1d 2.2M | 2d 2.15M | 3-5d 1.81M (Multi +1M) | Trẻ <9T: **1.480.000đ** + miễn 100% vé xe.
2. **Nga & CIS (/russian):**
   - Bờ Y 90D Single: **3.400.000đ** (Khách cũ CRM 3.0M) | Multi: **4.400.000đ** (Khách cũ 4.0M) | 45D: **1.400.000đ** (Khách cũ 1.3M).
   - Mộc Bài: **5.400.000đ** (Multi+Cam) | **4.400.000đ** (Single+Cam) | **3.400.000đ** (90D Single Bus+EV) | **1.400.000đ** (45D).
   - E-visa lẻ RU: 1h 4.6M | 2h 3.4M | 4h **2.0M** | 1d **1.81M** | 2d **1.76M** | 3-5d **1.61M** (Multi +1M).
3. **Ả Rập (/arabic = Giá EN + 1.500.000đ):**
   - Mộc Bài: **7.5M** (Multi+Cam) | **6.5M** (Single+Cam) | **5.5M** (Bus+90D EV) | Đà Nẵng–Lào: **5.3M**.
   - E-visa lẻ AR: 1h 6.1M | 2h 4.9M | 4h 4.1M | 1d 3.7M | 2d 3.65M | 3-5d 3.31M | Trẻ <9T card: **2.98M**.
4. **VIP Fast Track & Hỗ trợ cửa khẩu:**
   - Sân bay CXR / DAD / PQC / VDO / HPH / HUI / VII / DLI / VCA: **1.855.000đ ($70)**.
   - Sân bay SGN / HAN: **1.200.000đ** | Hỗ trợ cửa khẩu Lào (Lao Bảo / Bờ Y): **300.000đ**.`
    },
    {
        keywords: ['nham dau', '45d', '45 ngay', 'sai dau', 'dong dau sai', 'in a4', 'pdf', 'moc bai', 'giay a4'],
        answer: `🚨 **XỬ LÝ SỰ CỐ CỬA KHẨU & GIẤY TỜ E-VISA:**
1. **Sự cố đóng nhầm dấu 45 ngày dù khách có E-visa 90 ngày:**
   - Nguyên nhân: Khách quên báo hoặc quên đưa bản E-visa tại quầy nhập cảnh.
   - Xử lý: Yêu cầu khách giữ bình tĩnh, đứng tại khu vực quầy hải quan, đưa bản E-visa ra ngay cho cán bộ kiểm soát đối chiếu để **hủy dấu 45D và đóng lại dấu đúng hạn 90D** trước khi rời cửa khẩu! Không rời khỏi trạm rồi mới báo.
2. **In giấy A4 tại Mộc Bài vs PDF tại Bờ Y / Lao Bảo:**
   - **Mộc Bài (Campuchia):** **BẮT BUỘC in E-visa ra giấy A4** (có tiệm photo ngay khu vực cửa khẩu hỗ trợ in).
   - **Bờ Y & Lao Bảo (Lào):** Dùng file PDF trên điện thoại là được chấp nhận.`
    },
    {
        keywords: ['gui dau tre', 'sau 08:00', 'sau 8:00', 'lo xe', '13:00', '2 gio chieu', 'xe quay ve'],
        answer: `⏰ **XỬ LÝ KHI KHÁCH GỬI ẢNH DẤU XUẤT CẢNH TRỄ (>08:00) HOẶC LỠ CHUYẾN 13:00:**
- Quy chuẩn Mộc Bài: Khách qua cửa khẩu 07:30–08:00, gửi ảnh dấu xuất cảnh **trước 08:00** để chạy gói 4h nhận E-visa lúc 11:30–12:00, kịp lên xe về lúc **13:00**.
- Nếu khách gửi dấu trễ sau 08:30 (trễ mốc sáng):
  1. Báo ngay cho nhóm điều hành / Anh Luân kiểm tra nâng cấp gói **2h hoặc 1h** (nếu còn kịp chốt 11:30) hoặc chuyển sang ca chiều trả lúc **17:30**.
  2. Nếu nhà xe không thể đợi quá 13:00 (trả kết quả ca chiều 17:30): Báo rõ cho khách phương án đi xe khách tuyến sau / xe riêng từ Mộc Bài về TP.HCM/Nha Trang và báo Giám đốc Mr. Lý Việt Hoàng (+84 89 69 16 361) hỗ trợ điều phối.`
    },
    {
        keywords: ['cuoi tuan', 'thu 7', 'chu nhat', 'ngay le', 'hoan tien', '100%', 'refund'],
        answer: `🛡️ **CHÍNH SÁCH CUỐI TUẦN T7/CN & CAM KẾT HOÀN TIỀN 100%:**
- **Cuối tuần (Thứ 7, Chủ Nhật) & Ngày lễ:** Không xử lý E-visa khẩn gói 4–8h theo lịch chuẩn. Nếu khách cần cực gấp cuối tuần, hướng dẫn liên hệ trực tiếp **WhatsApp (+84 85 320 1277)** hoặc **Telegram (@easytripvisa_co_ltd)** để Giám đốc kiểm tra ca hỗ trợ riêng.
- **Cam kết hoàn tiền 100%:** Nếu E-visa không ra đúng khung giờ đã cam kết theo giờ Việt Nam (**GMT+7**), Easy Trip & Visa hoàn tiền **100%**.
- **Điều kiện hộ chiếu:** Bắt buộc còn hạn **>= 6 tháng**.`
    },
    {
        keywords: ['so do ghe', 'mau trang', 'gach vang', 'lock ghe', 'scheme', 'tang tren', 'tang duoi', 'a11', 'a20'],
        answer: `🚌 **QUY TẮC ĐỌC SƠ ĐỒ GHẾ & LỆNH TELEGRAM:**
- **Cấu trúc xe:** CHỈ có Tầng dưới số lẻ (\`A1, B1, A3, B3, A5, B5, A7, B7, A9, B9\`) và Tầng trên số chẵn (\`A2, B2, A4, B4, A6, B6, A8, B8, A10, B10\`, đôi khi có \`A12\` dài 160cm). **TUYỆT ĐỐI KHÔNG** có \`A11, B11, A13..A20\`.
- **Cách đọc ảnh sơ đồ:**
  - ⬜ **Ô màu trắng (không gạch):** CÒN TRỐNG — khách được chọn.
  - 🟨 **Ô gạch vàng / đánh dấu X:** ĐÃ ĐẶT — tuyệt đối không cho khách chọn.
- **Lệnh Telegram Topic General:** \`Scheme [DD/MM] - [45D/90D] [Laos/Cambodia]\` -> Đợi nhà xe gửi ảnh -> Cho khách chọn ô trắng -> Gửi lệnh Topic **Lock Ghế** trước **14:00** ngày khởi hành.`
    },
    {
        keywords: ['tre em', 'cabin', 'duoi 9 tuoi', 'so luong', 'khong xe buyt', 'khong di xe buyt', 'tu di chuyen'],
        answer: `👶 **CHÍNH SÁCH TRẺ EM & PHƯƠNG TIỆN (VISA RUN):**
- **Trẻ em dưới 9 tuổi:** **MIỄN PHÍ 100% vé xe buýt (0 VND)** khi nằm chung cabin với bố mẹ. E-visa khẩn trợ giá: **1.480.000đ** (Web Quốc tế/Nga, đăng ký trước 4 ngày) hoặc **2.980.000đ** (Web `/arabic`).
- **Khách tự di chuyển (Không sử dụng xe buýt):**
  - Nga / CIS: Visa 90D lẻ (không bus) **2.000.000 VND**.
  - Các quốc tịch khác: Trừ 1.400.000đ tiền vé xe khỏi gói combo tương ứng.`
    },
    {
        keywords: ['gia', 'khan cap', 'bao nhieu', '1 gio', '2 gio', '3 gio', '4 gio', '8 gio', '1 ngay', '2 ngay', 'tieu chuan'],
        answer: `💵 **BẢNG GIÁ E-VISA KHẨN CẤP LẺ (SINGLE — MULTI +1.000.000đ):**
- **Quốc tế & Hàn Quốc (`/english`, `/korean`):** 1h: 4.6M | 2h: 3.4M | 4h: 2.6M | 8h: 2.9M | 1d: 2.2M | 2d: 2.15M | 3–5d: 1.81M.
- **Nga & CIS (`/russian`):** 1h: 4.6M | 2h: 3.4M | 4h: **2.0M** | 1d: **1.81M** | 2d: **1.76M** | 3–5d: **1.61M**.
- **Ả Rập (`/arabic`):** Cộng thêm **+1.500.000đ** vào giá `/english` (1h 6.1M | 4h 4.1M | 1d 3.7M | 3–5d 3.31M).
- **Nội bộ Loyalty / Đại lý:** 1h 3.3M | 2h 2.9M | 3h 2.5M | 4h 1.6M | 8h 1.9M | 1d 1.5M | 2d 1.45M | 3–5d 1.11M.
- **Phụ phí quốc tịch khó:** Nhóm 1 (Ai Cập, Algeria, Tunisia, Sri Lanka, Mauritius) **+850k** | Nhóm 2 (Thổ Nhĩ Kỳ, Morocco, UAE) **+650k**.`
    },
    {
        keywords: ['tai khoan', 'ngan hang', 'vcb', 'vietcombank', 'vrb', 'usdt', 'bank', 'stk', 'swift', 'chuyen khoan', 'thanh toan', 'moc do', 'receipt'],
        answer: `🏦 **THÔNG TIN THANH TOÁN & QUY TRÌNH RECEIPT MỘC ĐỎ:**
- **Ngân hàng:** Vietcombank (**VCB**) hoặc **VRB**
- **Chủ tài khoản:** \`EASY TRIP & VISA CO. LTD\` | **STK:** \`1068582577\` | **VCB OneQR:** \`QRPACQ1ZZZZ50600546\` | **SWIFT:** \`BFTVVNVX\`
- **Hình thức khác:** Tiền mặt VND/USD tại văn phòng **21 Phan Vinh, Nha Trang**, hoặc **USDT (Crypto)**.
- **Quy trình bắt buộc:** Sau khi xác nhận tiền vào tài khoản, đóng **dấu mộc đỏ công ty** lên receipt, chụp ảnh gửi khách và cập nhật trạng thái Paid trên Telegram Lock Ghế (hạn chót vé xe trước **14:00** ngày đi).`
    },
    {
        keywords: ['dia chi', 'van phong', 'dinh vi', 'office', 'nha trang', 'phan vinh', 'maps', 'o dau'],
        answer: `📍 **THÔNG TIN VĂN PHÒNG & ĐIỂM ĐÓN:**
- **Văn phòng:** 21 Phan Vinh, Nha Trang ([Google Maps](https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9)) — MST: \`4202051389\`
- **Điểm đón Nha Trang:** 40 Hòn Chồng / Oceanus (21:30) hoặc Số 4 Trần Phú (21:15).
- **Hotline Điều hành & Giám đốc:** Mr. Lý Việt Hoàng (+84 89 69 16 361) | WhatsApp/Zalo CSKH: +84 85 320 1277 | Telegram: @easytripvisa_co_ltd.`
    },
    {
        keywords: ['ho so', 'bio', 'chup', 'anh', 'forehead', 'tran', 'passport', 'ho chieu'],
        answer: `📷 **QUY ĐỊNH HỒ SƠ YÊU CẦU:**
1. **Passport Bio Page:** Rõ nét, chụp vuông góc đủ **4 góc**, không lóa đèn, không che ngón tay, hộ chiếu còn hạn **>= 6 tháng**.
2. **Ảnh chân dung (Portrait):** Nền sáng, nhìn thẳng, **lộ rõ trán và hai tai**, không đeo kính.
3. **Ảnh dấu xuất cảnh (Exit Stamp):** Gửi ngay khi qua hải quan Việt Nam (trước **08:00 sáng** tại Mộc Bài).`
    },
    {
        keywords: ['lich', 'chay', 'lao', 'campuchia', 'bo y', 'bus', 'xe buyt', 'thoi gian', 'da nang'],
        answer: `🚌 **LỊCH TRÌNH & TUYẾN XE VISARUN:**
- **Nha Trang ⇄ Lào (Bờ Y):** CHỈ dành cho Nga, Belarus, Hàn Quốc, Nhật, Luxembourg, 12 nước ASEAN. 45D chạy **hàng ngày** (1.4M); 90D chạy **T3, T5, CN** lúc 21:30 (Nga 3.4M / 4.4M Multi; Non-RU 4.0M).
- **Nha Trang ⇄ Campuchia (Mộc Bài):** Toàn bộ quốc tịch khác (Mỹ, EU, Kazakhstan, Ukraine, Ả Rập...). Chạy **T3, T5, CN** lúc 21:30 tại 40 Hòn Chồng.
- **Đà Nẵng ⇄ Lao Bảo (Lào):** 90D chạy T2–T6 lúc 05:30–18:30 (3.8M website / 3.55M đặt trước >=3d; Web `/arabic` 5.3M; +Hanie tại cửa khẩu). 45D chạy T2–T7 (950k).`
    }
];

// State variables for staff chat attachments, history, and training mode
let staffAttachments = [];
let staffChatHistory = [];
let staffChatMode = 'training';

function setStaffChatMode(mode) {
    if (!['training', 'reply_draft', 'quiz'].includes(mode)) mode = 'training';
    staffChatMode = mode;

    document.querySelectorAll('.staff-mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    const input = document.getElementById('staff-chat-input');
    if (input) {
        if (mode === 'reply_draft') {
            input.placeholder = 'Dán tin nhắn khách hỏi (Anh/Nga/Hàn/Ả Rập/Việt) để AI soạn câu trả lời chuẩn...';
        } else if (mode === 'quiz') {
            input.placeholder = 'Nhập câu trả lời xử lý tình huống của bạn (hoặc bấm "Ra bài tập tình huống")...';
        } else {
            input.placeholder = 'Nhập tình huống bạn chưa rõ, hỏi SOP, dán ảnh passport... (Enter để gửi)';
        }
    }
}

function resetStaffChat() {
    staffChatHistory = [];
    const chatWindow = document.getElementById('staff-chat-window');
    if (chatWindow) {
        chatWindow.innerHTML = `
            <div class="staff-msg bot">
                <div class="staff-msg-content">
                    🔄 Đã bắt đầu phiên đào tạo / hỏi đáp mới (chế độ hiện tại: <strong>${staffChatMode === 'reply_draft' ? '💬 Soạn tin trả lời khách' : staffChatMode === 'quiz' ? '🎯 Luyện tập tình huống' : '🎓 Hỏi tình huống / SOP'}</strong>). Bạn hãy nhập câu hỏi hoặc tình huống nhé!
                </div>
            </div>
        `;
    }
}

function startQuizScenario() {
    setStaffChatMode('quiz');
    quickAskStaff('Hãy ra cho tôi 1 tình huống thực tế khó vừa phải tại quầy hoặc cửa khẩu Easy Trip & Visa để tôi tập xử lý.');
}

function copyStaffBotReply(btnEl) {
    const msgEl = btnEl.closest('.staff-msg.bot');
    const raw = msgEl ? (msgEl.dataset.rawText || msgEl.innerText) : '';
    if (!raw) return;
    navigator.clipboard.writeText(raw).then(() => {
        const prev = btnEl.textContent;
        btnEl.textContent = '✅ Đã chép';
        setTimeout(() => { btnEl.textContent = prev; }, 1500);
    });
}

function autoResizeStaffInput(el) {
    el.style.height = 'auto';
    el.style.height = (el.scrollHeight) + 'px';
}

function handleStaffFileSelect(input) {
    const files = Array.from(input.files);
    processStaffFiles(files);
    input.value = ''; // Reset file input
}

function processStaffFiles(files) {
    files.forEach(file => {
        if (staffAttachments.length >= 5) {
            showNotification("Chỉ được đính kèm tối đa 5 tệp tin.", "warning");
            return;
        }
        
        const fileId = 'staff-file-' + Date.now() + '-' + Math.round(Math.random() * 100000);
        const isImage = file.type.startsWith('image/');
        
        const attachment = {
            id: fileId,
            file: file,
            name: file.name,
            type: file.type,
            size: file.size,
            url: '',
            uploaded: false
        };
        
        staffAttachments.push(attachment);
        renderStaffPreviews();
        
        if (isBackendOnline) {
            uploadStaffFileToServer(attachment);
        } else {
            // Simulated upload for sandbox
            setTimeout(() => {
                attachment.url = URL.createObjectURL(file);
                attachment.uploaded = true;
                renderStaffPreviews();
            }, 300);
        }
    });
}

async function uploadStaffFileToServer(attachment) {
    const formData = new FormData();
    formData.append('file', attachment.file);
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/staff/media`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.success) {
            attachment.url = data.url;
            attachment.uploaded = true;
        } else {
            showNotification("Lỗi tải tệp: " + data.message, "warning");
            removeStaffAttachment(attachment.id);
        }
    } catch (e) {
        console.error("Upload error, using local url instead", e);
        attachment.url = URL.createObjectURL(attachment.file);
        attachment.uploaded = true;
    }
    renderStaffPreviews();
}

function renderStaffPreviews() {
    const previewArea = document.getElementById('staff-chat-attachment-preview');
    if (!previewArea) return;
    
    if (staffAttachments.length === 0) {
        previewArea.style.display = 'none';
        previewArea.innerHTML = '';
        return;
    }
    
    previewArea.style.display = 'flex';
    let html = '';
    staffAttachments.forEach(att => {
        const isImg = att.type.startsWith('image/');
        const opacity = att.uploaded ? '1' : '0.5';
        const loadingIndicator = att.uploaded ? '' : '<span style="font-size:0.55rem; color:var(--warning); margin-left:2px;">...</span>';
        
        let previewIconHtml = '';
        if (isImg) {
            const imgUrl = att.url || URL.createObjectURL(att.file);
            previewIconHtml = `<img src="${imgUrl}" class="staff-preview-thumbnail" />`;
        } else {
            let icon = '📁';
            if (att.name.endsWith('.pdf')) icon = '📕';
            else if (att.name.endsWith('.xlsx') || att.name.endsWith('.xls')) icon = '📗';
            else if (att.name.endsWith('.docx') || att.name.endsWith('.doc')) icon = '📘';
            else if (att.name.endsWith('.zip') || att.name.endsWith('.rar')) icon = '🗂️';
            previewIconHtml = `<span class="staff-preview-doc-icon">${icon}</span>`;
        }
        
        html += `
        <div class="staff-preview-badge" id="preview-${att.id}" style="opacity: ${opacity};">
            ${previewIconHtml}
            <span class="staff-preview-name" title="${att.name}">${att.name}</span>
            ${loadingIndicator}
            <button class="staff-preview-remove" onclick="removeStaffAttachment('${att.id}')" title="Xóa">×</button>
        </div>
        `;
    });
    previewArea.innerHTML = html;
}

function removeStaffAttachment(id) {
    const index = staffAttachments.findIndex(att => att.id === id);
    if (index !== -1) {
        const att = staffAttachments[index];
        if (att.url && att.url.startsWith('blob:')) {
            URL.revokeObjectURL(att.url);
        }
        staffAttachments.splice(index, 1);
    }
    renderStaffPreviews();
}

function setupStaffChatDragAndDrop() {
    const chatWindow = document.getElementById('staff-chat-window');
    if (!chatWindow) return;
    
    ['dragenter', 'dragover'].forEach(eventName => {
        chatWindow.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            chatWindow.classList.add('drag-over');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        chatWindow.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            chatWindow.classList.remove('drag-over');
        }, false);
    });
    
    chatWindow.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = Array.from(dt.files);
        if (files.length > 0) {
            processStaffFiles(files);
        }
    }, false);
}

function setupStaffChatPaste() {
    const input = document.getElementById('staff-chat-input');
    if (!input) return;
    
    input.addEventListener('paste', (e) => {
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        const files = [];
        for (const item of items) {
            if (item.kind === 'file') {
                const file = item.getAsFile();
                if (file) {
                    files.push(file);
                }
            }
        }
        if (files.length > 0) {
            e.preventDefault();
            processStaffFiles(files);
        }
    });
}

function handleStaffChatTextareaKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendStaffChatMessage();
    }
}

function appendStaffMessage(chatWindow, sender, text, attachmentsList = []) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `staff-msg ${sender}`;
    if (text) {
        msgDiv.dataset.rawText = text;
    }
    
    let contentHtml = '';
    if (text) {
        contentHtml += `<div class="staff-msg-content">${formatMarkdown(text)}</div>`;
    }
    
    if (attachmentsList.length > 0) {
        let attachmentsHtml = '<div class="staff-message-attachments" style="margin-top: 5px; display: flex; flex-direction: column; gap: 6px;">';
        attachmentsList.forEach(att => {
            const isImg = att.type.startsWith('image/');
            if (isImg) {
                attachmentsHtml += `<img src="${att.url}" class="staff-msg-image" onclick="window.open('${att.url}')" />`;
            } else {
                let icon = '📁';
                if (att.name.endsWith('.pdf')) icon = '📕';
                else if (att.name.endsWith('.xlsx') || att.name.endsWith('.xls')) icon = '📗';
                else if (att.name.endsWith('.docx') || att.name.endsWith('.doc')) icon = '📘';
                else if (att.name.endsWith('.zip') || att.name.endsWith('.rar')) icon = '🗂️';
                
                let sizeStr = '';
                if (att.size) {
                    const kb = att.size / 1024;
                    sizeStr = kb > 1024 ? (kb / 1024).toFixed(1) + ' MB' : kb.toFixed(0) + ' KB';
                }
                
                attachmentsHtml += `
                <a href="${att.url}" target="_blank" class="staff-file-card">
                    <span class="staff-file-icon">${icon}</span>
                    <span class="staff-file-info">
                        <div class="staff-file-name">${att.name}</div>
                        <div class="staff-file-meta">${sizeStr || 'Tài liệu'}</div>
                    </span>
                    <span class="staff-file-download">📥</span>
                </a>`;
            }
        });
        attachmentsHtml += '</div>';
        contentHtml += attachmentsHtml;
    }

    if (sender === 'bot' && text) {
        contentHtml += `
        <div class="staff-msg-actions">
            <button class="staff-copy-msg-btn" onclick="copyStaffBotReply(this)">📋 Sao chép</button>
        </div>`;
    }
    
    msgDiv.innerHTML = contentHtml;
    chatWindow.appendChild(msgDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function sendStaffChatMessage() {
    const input = document.getElementById('staff-chat-input');
    const chatWindow = document.getElementById('staff-chat-window');
    if (!input || !chatWindow) return;
    
    const question = input.value.trim();
    if (!question && staffAttachments.length === 0) return;
    
    const currentAttachments = [...staffAttachments];
    const historySnapshot = staffChatHistory.slice(-10);
    
    appendStaffMessage(chatWindow, 'user', question, currentAttachments);
    
    input.value = '';
    input.style.height = 'auto';
    staffAttachments = [];
    renderStaffPreviews();
    
    const botMsgDiv = document.createElement('div');
    botMsgDiv.className = 'staff-msg bot typing-indicator';
    botMsgDiv.innerHTML = '<span style="font-style: italic; color: var(--text-secondary);">🤖 Mentor AI đang phân tích tình huống...</span>';
    chatWindow.appendChild(botMsgDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    const apiAttachments = currentAttachments.map(att => ({
        url: att.url,
        filename: att.name,
        content_type: att.type
    }));

    fetch(`${BACKEND_URL}/api/staff/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            question: question,
            history: historySnapshot,
            mode: staffChatMode,
            attachments: apiAttachments
        })
    })
    .then(res => {
        if (!res.ok) throw new Error("HTTP error " + res.status);
        return res.json();
    })
    .then(data => {
        if (botMsgDiv.parentNode) chatWindow.removeChild(botMsgDiv);
        let replyText = '';
        if (data.success && data.answer && !data.answer.startsWith('🤖 Không thể kết nối với AI')) {
            replyText = data.answer;
        } else {
            replyText = getLocalStaffAnswer(question, staffChatMode);
        }
        appendStaffMessage(chatWindow, 'bot', replyText);
        if (question) staffChatHistory.push({ role: 'user', content: question });
        if (replyText) staffChatHistory.push({ role: 'assistant', content: replyText });
        if (staffChatHistory.length > 12) staffChatHistory = staffChatHistory.slice(-12);
    })
    .catch(err => {
        console.warn("⚠️ Staff AI API Error, falling back to local keywords:", err);
        if (botMsgDiv.parentNode) chatWindow.removeChild(botMsgDiv);
        const localAnswer = getLocalStaffAnswer(question, staffChatMode);
        appendStaffMessage(chatWindow, 'bot', localAnswer);
        if (question) staffChatHistory.push({ role: 'user', content: question });
        if (localAnswer) staffChatHistory.push({ role: 'assistant', content: localAnswer });
        if (staffChatHistory.length > 12) staffChatHistory = staffChatHistory.slice(-12);
    });
}

function getLocalStaffAnswer(question, mode = 'training') {
    if (mode === 'quiz' && removeVietnameseTones(question).toLowerCase().includes('tinh huong')) {
        return `🎯 **BÀI TẬP TÌNH HUỐNG MẪU (CHẾ ĐỘ OFFLINE):**
Khách quốc tịch **Kazakhstan** nhắn tin: *"Xin chào, visa của tôi sắp hết hạn sau 4 ngày. Tôi đang ở Nha Trang và muốn đi xe sang Lào Bờ Y gói 90 ngày, có mang theo con 6 tuổi."*
👉 **Câu hỏi cho bạn:**
1. Khách này đi tuyến nào? Có đi Lào Bờ Y được không?
2. Báo tổng chi phí là bao nhiêu tiền (theo bảng giá \`/russian\` hoặc \`/english\`)?
3. Nhắn lại cho khách như thế nào và cần dặn in giấy A4 hay dùng PDF?`;
    }

    let answerText = '';
    const cleanQuestion = removeVietnameseTones(question).toLowerCase();
    
    // Score keywords so multi-keyword queries hit the best entry
    let bestScore = 0;
    for (const item of staffAIDatabase) {
        let score = 0;
        for (const kw of item.keywords) {
            const cleanKw = removeVietnameseTones(kw).toLowerCase();
            if (cleanQuestion.includes(cleanKw)) {
                score += 1;
            }
        }
        if (score > bestScore) {
            bestScore = score;
            answerText = item.answer;
        }
    }
    
    if (!answerText) {
        answerText = `🤖 Hiện đang dùng bộ tra cứu ngoại tuyến nên chưa phân tích được chi tiết câu hỏi tự do này.
Bạn có thể hỏi các tình huống như: *"bảng giá 4 website"*, *"nhầm dấu 45D"*, *"gửi dấu trễ >08:00"*, *"cuối tuần & hoàn tiền 100%"*, *"sơ đồ ghế trắng vàng"*, *"thanh toán VCB / VRB / USDT"*, hoặc kiểm tra kết nối AI Backend!`;
    }
    return answerText;
}

function handleStaffChatKey(event) {
    if (event.key === 'Enter') {
        sendStaffChatMessage();
    }
}

function quickAskStaff(question) {
    const input = document.getElementById('staff-chat-input');
    if (input) {
        input.value = question;
        autoResizeStaffInput(input);
        sendStaffChatMessage();
    }
}

// Hàm chuẩn hoá chuỗi tiếng Việt không dấu để so khớp
function removeVietnameseTones(str) {
    if (!str) return '';
    str = str.replace(/à|á|ạ|ả|ã|â|ầ|ấ|ậ|ẩ|ẫ|ă|ằ|ắ|ặ|ẳ|ẵ/g,"a"); 
    str = str.replace(/è|é|ẹ|ẻ|ẽ|ê|ề|ế|ệ|ể|ễ/g,"e"); 
    str = str.replace(/ì|í|ị|ỉ|ĩ/g,"i"); 
    str = str.replace(/ò|ó|ọ|ỏ|õ|ô|ồ|ố|ộ|ổ|ỗ|ơ|ờ|ớ|ợ|ở|ỡ/g,"o"); 
    str = str.replace(/ù|ú|ụ|ủ|ũ|ư|ừ|ứ|ự|ử|ữ/g,"u"); 
    str = str.replace(/ỳ|ý|ỵ|ỷ|ỹ/g,"y"); 
    str = str.replace(/đ/g,"d");
    str = str.replace(/À|Á|Ạ|Ả|Ã|Â|Ầ|Ấ|Ậ|Ẩ|Ẫ|Ă|Ằ|Ắ|Ặ|Ẳ|Ẵ/g, "A");
    str = str.replace(/È|É|Ẹ|Ẻ|Ẽ|Ê|Ề|Ế|Ệ|Ể|Ễ/g, "E");
    str = str.replace(/Ì|Í|Ị|Ỉ|Ĩ/g, "I");
    str = str.replace(/Ò|Ó|Ọ|Ỏ|Õ|Ô|Ồ|Ố|Ộ|Ổ|Ỗ|Ơ|Ờ|Ớ|Ợ|Ở|Ỡ/g, "O");
    str = str.replace(/Ù|Ú|Ụ|Ủ|Ũ|Ư|Ừ|Ứ|Ự|Ử|Ữ/g, "U");
    str = str.replace(/Ỳ|Ý|Ỵ|Ỷ|Ỹ/g, "Y");
    str = str.replace(/Đ/g, "D");
    // Remove extra spaces
    str = str.replace(/\s+/g, ' ');
    return str.trim();
}

// Hàm kiểm tra quốc tịch có được miễn thị thực vào Việt Nam hay không
function isVietnamVisaExempt(nationality) {
    if (!nationality) return false;
    const norm = removeVietnameseTones(nationality).toLowerCase();
    // Danh sách các quốc tịch miễn thị thực đơn phương/song phương vào Việt Nam
    const exemptList = [
        'nga', 'russia', 'han quoc', 'korea', 'nhat ban', 'japan', 'belarus',
        'anh', 'united kingdom', 'uk', 'phap', 'france', 'duc', 'germany',
        'y', 'italy', 'tay ban nha', 'spain', 'dan mach', 'denmark',
        'thuy dien', 'sweden', 'na uy', 'norway', 'phan lan', 'finland',
        'singapore', 'thailan', 'thai lan', 'malaysia', 'philippin', 'indonesia',
        'myanmar', 'brunei', 'campuchia', 'cambodia', 'lao'
    ];
    return exemptList.some(kw => norm.includes(kw));
}


