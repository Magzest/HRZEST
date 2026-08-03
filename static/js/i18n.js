/* ==============================================================================
   i18n.js — Client-Side Multi-Language Internationalization Engine
   Supports English (EN), Spanish (ES), and Hindi (HI) with instant DOM translation.
   ============================================================================== */

(function () {
  const TRANSLATIONS = {
    en: {
      "nav_dashboard": "Dashboard",
      "nav_attendance": "Attendance",
      "nav_leave": "Leave Requests",
      "nav_salary": "Salary & Payslips",
      "nav_support": "Help & Support",
      "nav_profile": "My Profile",
      "btn_punch_in": "Punch In Now",
      "btn_punch_out": "Punch Out",
      "btn_touch_id": "Register Touch ID / Biometric",
      "lbl_status": "Status",
      "lbl_welcome": "Welcome back",
      "lbl_quick_actions": "Quick Actions",
    },
    es: {
      "nav_dashboard": "Panel Principal",
      "nav_attendance": "Asistencia",
      "nav_leave": "Solicitud de Permisos",
      "nav_salary": "Salario y Recibos",
      "nav_support": "Soporte y Ayuda",
      "nav_profile": "Mi Perfil",
      "btn_punch_in": "Registrar Entrada",
      "btn_punch_out": "Registrar Salida",
      "btn_touch_id": "Registrar Huella / Biométrico",
      "lbl_status": "Estado",
      "lbl_welcome": "Bienvenido de nuevo",
      "lbl_quick_actions": "Acciones Rápidas",
    },
    hi: {
      "nav_dashboard": "डैशबोर्ड",
      "nav_attendance": "उपस्थिति",
      "nav_leave": "छुट्टी के अनुरोध",
      "nav_salary": "वेतन और पे-स्लिप",
      "nav_support": "सहायता एवं सपोर्ट",
      "nav_profile": "मेरी प्रोफ़ाइल",
      "btn_punch_in": "पंच इन करें",
      "btn_punch_out": "पंच आउट करें",
      "btn_touch_id": "फिंगरप्रिंट / बायोमेट्रिक दर्ज करें",
      "lbl_status": "स्थिति",
      "lbl_welcome": "पुनः स्वागत है",
      "lbl_quick_actions": "त्वरित कार्रवाइयां",
    }
  };

  let currentLang = localStorage.getItem("app_lang") || "en";

  function setLanguage(lang) {
    if (!TRANSLATIONS[lang]) lang = "en";
    currentLang = lang;
    localStorage.setItem("app_lang", lang);

    const dict = TRANSLATIONS[lang];
    document.querySelectorAll("[data-i18n]").forEach(el => {
      const key = el.getAttribute("data-i18n");
      if (dict[key]) {
        if (el.tagName === "INPUT" && el.type === "placeholder") {
          el.placeholder = dict[key];
        } else {
          el.textContent = dict[key];
        }
      }
    });

    const selector = document.getElementById("langSelector");
    if (selector) selector.value = lang;
  }

  window.i18n = {
    setLanguage: setLanguage,
    getLanguage: () => currentLang,
    t: (key) => (TRANSLATIONS[currentLang] && TRANSLATIONS[currentLang][key]) || key
  };

  document.addEventListener("DOMContentLoaded", () => {
    setLanguage(currentLang);
  });
})();
