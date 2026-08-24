// Easy Trip & Visa — Google Apps Script Webhook
// Paste this into ALL 4 partner sheets (Sergei, Bolot, Luan, Tung)
// Then deploy as Web App (anyone can access, no login needed)

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var sheet = SpreadsheetApp.getActiveSpreadsheet();
    
    // Get or create tab named by current month (e.g. "T5/2025")
    var now = new Date();
    var tabName = "T" + (now.getMonth() + 1) + "/" + now.getFullYear();
    var ws = sheet.getSheetByName(tabName);
    if (!ws) {
      ws = sheet.insertSheet(tabName);
      // Add headers
      ws.appendRow([
        "Order ID", "Ngày tạo", "Tên / Năm sinh", "Tuyến",
        "Ngày khởi hành", "Ghế", "Điểm đón", "SĐT",
        "Giá (VND)", "Trạng thái", "Kênh", "Đại lý", "Ghi chú"
      ]);
      ws.getRange(1, 1, 1, 13).setFontWeight("bold").setBackground("#4a86e8").setFontColor("white");
    }
    
    // Append the order row
    ws.appendRow([
      data["Order ID"] || "",
      data["Created At"] || new Date().toLocaleDateString("vi-VN"),
      data["Full Name"] || "",
      data["Route"] || "",
      data["Departure Date"] || "",
      data["Seat"] || "",
      data["Pickup Point"] || "",
      data["Phone"] || "",
      data["Price (VND)"] || 0,
      data["Status"] || "PAID",
      data["Source Channel"] || "",
      data["Agent"] || "",
      data["Payment Note"] || ""
    ]);
    
    return ContentService
      .createTextOutput(JSON.stringify({success: true}))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch(err) {
    return ContentService
      .createTextOutput(JSON.stringify({success: false, error: err.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Test function - run this to check the script works
function testScript() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet();
  Logger.log("Sheet name: " + sheet.getName());
  Logger.log("Script is working!");
}
