"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { translations, type Locale, type TranslationKey } from "./translations";

type I18nStore = {
  locale: Locale;
  setLocale: (l: Locale) => void;
};

// `skipHydration: true` keeps SSR and first client render identical
// (both return the default `locale: "ru"`), and we trigger rehydrate
// explicitly in a useEffect below — eliminating the hydration warning
// that React StrictMode + dev HMR can otherwise amplify into a
// recovery render which loses CSS chunk references.
export const useI18n = create<I18nStore>()(
  persist(
    (set) => ({
      locale: "ru",
      setLocale: (locale) => set({ locale }),
    }),
    {
      name: "buchuchet.locale",
      storage: createJSONStorage(() => (typeof window === "undefined"
        ? ({
            length: 0, clear: () => {}, key: () => null,
            getItem: () => null, setItem: () => {}, removeItem: () => {},
          } as Storage)
        : window.localStorage)),
      skipHydration: true,
    },
  ),
);

/**
 * Returns a translator bound to the current locale. Resolves dotted keys
 * against the translations table, falling back to the key itself if missing
 * so a missing entry is visible but never crashes the UI.
 */
export function useT(): (key: TranslationKey) => string {
  const locale = useI18n((s) => s.locale);
  return (key) => translations[locale][key] ?? translations.ru[key] ?? key;
}

/** Mount-once helper: triggers the deferred localStorage rehydrate after
 *  the first client render so server HTML and first client HTML match. */
import { useEffect } from "react";
export function I18nRehydrate() {
  useEffect(() => { void useI18n.persist.rehydrate(); }, []);
  return null;
}

export const LOCALES: { value: Locale; label: string; native: string }[] = [
  { value: "ru", label: "Russian", native: "Русский" },
  { value: "en", label: "English", native: "English" },
];
