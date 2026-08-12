/* 
  i18n.js - 다국어(한국어/영어) 지원 로직
*/

const translations = {
  ko: {
    // Nav
    "nav.login": "로그인",
    "nav.install": "📱 앱 설치",
    "nav.logout": "로그아웃",

    // Auth Screen
    "auth.title": "AutoPost AI",
    "auth.subtitle": "로그인하고 시작하세요",
    "auth.email.label": "이메일",
    "auth.email.placeholder": "you@example.com",
    "auth.password.label": "비밀번호",
    "auth.password.placeholder": "8자 이상",
    "auth.btn.login": "이메일로 시작하기",
    "auth.btn.signup": "무료로 시작하기",
    "auth.kakao": "카카오로 시작하기",
    "auth.google": "Google로 시작하기",

    // Landing
    "landing.hook": "글쓰기 스트레스? 이제 AI에게 맡기세요.",
    "landing.desc": "업종, 지역, 특징만 입력하면 알아서 완벽한 SNS 원고를 뽑아냅니다.",
    "landing.btn": "무료로 시작하기",

    // Common
    "btn.next": "다음",
    "btn.prev": "이전",
    "btn.start": "무료로 생성하기",
    "btn.magic": "✨ 요술봉 (AI 다듬기)",
    "btn.restore": "↩️ 복구",
    "btn.copy": "📋 클립보드 복사",
    "btn.download": "📥 텍스트 다운로드",
    "btn.publish": "🚀 지금 바로 올리기",
    "btn.schedule": "📅 나중에 예약하기"
  },
  en: {
    // Nav
    "nav.login": "Log in",
    "nav.install": "📱 Install App",
    "nav.logout": "Log out",

    // Auth Screen
    "auth.title": "AutoPost AI",
    "auth.subtitle": "Log in to get started",
    "auth.email.label": "Email",
    "auth.email.placeholder": "you@example.com",
    "auth.password.label": "Password",
    "auth.password.placeholder": "Min 8 chars",
    "auth.btn.login": "Continue with Email",
    "auth.btn.signup": "Start for Free",
    "auth.kakao": "Continue with Kakao",
    "auth.google": "Continue with Google",

    // Landing
    "landing.hook": "Stressed about writing? Let AI handle it.",
    "landing.desc": "Enter your industry, location, and features, and we'll generate the perfect SNS post.",
    "landing.btn": "Start for Free",

    // Common
    "btn.next": "Next",
    "btn.prev": "Previous",
    "btn.start": "Generate for Free",
    "btn.magic": "✨ Magic Wand",
    "btn.restore": "↩️ Restore",
    "btn.copy": "📋 Copy to Clipboard",
    "btn.download": "📥 Download Text",
    "btn.publish": "🚀 Publish Now",
    "btn.schedule": "📅 Schedule Later"
  }
};

let currentLang = localStorage.getItem("app_lang") || "ko";

function updateLanguage(lang) {
  currentLang = lang;
  localStorage.setItem("app_lang", lang);
  document.documentElement.setAttribute("lang", lang);

  const dict = translations[lang];
  if (!dict) return;

  // Replace textContent for elements with data-i18n
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    if (dict[key]) {
      // Keep existing inner structure if there are icons, but for now we just use simple textContent for these elements
      // For elements with emojis, we'll include emojis in the dict strings
      el.textContent = dict[key];
    }
  });

  // Replace placeholders for inputs with data-i18n-placeholder
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (dict[key]) {
      el.setAttribute("placeholder", dict[key]);
    }
  });
}

function toggleLanguage() {
  const newLang = currentLang === "ko" ? "en" : "ko";
  updateLanguage(newLang);
}

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  updateLanguage(currentLang);
});
