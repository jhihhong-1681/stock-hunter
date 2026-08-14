// 共用設定：報酬日曆(firebase-sync.js)跟持股更新(holdings-editor.js)都讀同一份、寫同一份文件。
export const FIREBASE_CONFIG = {
  apiKey: "AIzaSyAcj24QP1xLOFReTCzj0EyLqDsm0C4tNSg",
  authDomain: "portfolio-calendar-1f1c7.firebaseapp.com",
  projectId: "portfolio-calendar-1f1c7",
  storageBucket: "portfolio-calendar-1f1c7.firebasestorage.app",
  messagingSenderId: "699401670138",
  appId: "1:699401670138:web:102eaa63a756ae537a6843",
  measurementId: "G-CC53RJC2TZ"
};

// 只有這個帳號登入後才有編輯權限（Firestore 安全規則那邊也要鎖同一個 email）。
export const OWNER_EMAIL = "jhihhong0810@gmail.com";

export const PORTFOLIO_DOC_PATH = ["portfolio", "current"];
export const NETWORTH_DOC_PATH = ["networth", "history"];
