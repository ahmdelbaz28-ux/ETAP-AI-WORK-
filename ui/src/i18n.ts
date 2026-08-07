<<<<<<< HEAD
import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";
import arData from "./locales/ar.json";
import enData from "./locales/en.json";
=======
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import enData from './locales/en.json'
import arData from './locales/ar.json'
>>>>>>> origin/fix/scenario-tests-properly

const resources = {
  en: { translation: enData },
  ar: { translation: arData },
<<<<<<< HEAD
};
=======
}
>>>>>>> origin/fix/scenario-tests-properly

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
<<<<<<< HEAD
    fallbackLng: "en",
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
    },
    interpolation: { escapeValue: false },
  });

export default i18n;
=======
    fallbackLng: 'en',
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
    interpolation: { escapeValue: false },
  })

export default i18n
>>>>>>> origin/fix/scenario-tests-properly
