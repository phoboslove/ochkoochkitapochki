export type Locale = "ru" | "en";

/**
 * Flat key → string dictionary. Flat (not nested) on purpose: simpler typing,
 * easier grep, no path-resolution helper needed. Add keys here as you wire up
 * useT() in more files. Missing keys fall back to the key string itself, so
 * partial coverage is safe — untranslated UI shows the raw key, not a crash.
 */
const ru = {
  // Sidebar group headers
  "nav.group.operations":  "Операции",
  "nav.group.automation":  "Автоматизация",
  "nav.group.management":  "Управление",
  "nav.group.system":      "Система",

  // Sidebar items
  "nav.dashboard":         "Сводка",
  "nav.invoices":          "Счета",
  "nav.documents":         "Документы",
  "nav.approvals":         "Подтверждения",
  "nav.assistant":         "AI-ассистент",
  "nav.workflows":         "Сценарии",
  "nav.recovery":          "Восстановление",
  "nav.clients":           "Контрагенты",
  "nav.employees":         "Сотрудники",
  "nav.team":              "Команда",
  "nav.reports":           "Отчёты",
  "nav.calculators":       "Калькуляторы",
  "nav.settings":          "Бизнес",
  "nav.onboarding":        "Мастер настройки",
  "nav.integrations":      "Интеграции",
  "nav.activity":          "Журнал",
  "nav.ops":               "Операционка",
  "nav.logs":              "Логи",

  // Sidebar misc
  "sidebar.collapse":      "Свернуть боковую панель",
  "sidebar.expand":        "Развернуть боковую панель",
  "sidebar.brand_tagline": "Backoffice OS",

  // Topbar
  "topbar.search":         "Поиск чего угодно…",
  "topbar.density.compact":     "Компактный вид",
  "topbar.density.comfortable": "Просторный вид",
  "topbar.notifications":  "Уведомления",
  "topbar.theme":          "Сменить тему",
  "topbar.logout":         "Выйти",

  // Settings — tabs
  "settings.title":            "Настройки организации",
  "settings.subtitle":         "Центральная конфигурация бизнеса — каждая часть приложения читает отсюда.",
  "settings.tab.company":       "Компания",
  "settings.tab.accounting":    "Учёт",
  "settings.tab.branding":      "Брендинг",
  "settings.tab.templates":     "Шаблоны",
  "settings.tab.approvals":     "Подтверждения",
  "settings.tab.notifications": "Уведомления",
  "settings.tab.integrations":  "Интеграции",
  "settings.tab.knowledge":     "База знаний",
  "settings.tab.security":      "Безопасность",
  "settings.tab.language":      "Язык",
  "settings.tab.billing":       "Подписка",

  // Settings — language section
  "settings.language.title":       "Язык интерфейса",
  "settings.language.hint":        "Выбор сохраняется в этом браузере. Смена языка применяется мгновенно.",
  "settings.language.label":       "Текущий язык",
  "settings.language.note":        "Локализация бета-версии: часть интерфейса всё ещё на английском. Перевод идёт постранично.",
};

const en: typeof ru = {
  "nav.group.operations":  "Operations",
  "nav.group.automation":  "Automation",
  "nav.group.management":  "Management",
  "nav.group.system":      "System",

  "nav.dashboard":         "Dashboard",
  "nav.invoices":          "Invoices",
  "nav.documents":         "Documents",
  "nav.approvals":         "Approvals",
  "nav.assistant":         "AI Assistant",
  "nav.workflows":         "Workflows",
  "nav.recovery":          "Recovery",
  "nav.clients":           "Counterparties",
  "nav.employees":         "Employees",
  "nav.team":              "Team",
  "nav.reports":           "Reports",
  "nav.calculators":       "Calculators",
  "nav.settings":          "Business",
  "nav.onboarding":        "Setup guide",
  "nav.integrations":      "Integrations",
  "nav.activity":          "Activity",
  "nav.ops":               "Operations",
  "nav.logs":              "Logs",

  "sidebar.collapse":      "Collapse sidebar",
  "sidebar.expand":        "Expand sidebar",
  "sidebar.brand_tagline": "Backoffice OS",

  "topbar.search":         "Search anything…",
  "topbar.density.compact":     "Compact density",
  "topbar.density.comfortable": "Comfortable density",
  "topbar.notifications":  "Notifications",
  "topbar.theme":          "Toggle theme",
  "topbar.logout":         "Logout",

  "settings.title":            "Organization settings",
  "settings.subtitle":         "Central business configuration — every part of the app reads from here.",
  "settings.tab.company":       "Company",
  "settings.tab.accounting":    "Accounting",
  "settings.tab.branding":      "Branding",
  "settings.tab.templates":     "Templates",
  "settings.tab.approvals":     "Approvals",
  "settings.tab.notifications": "Notifications",
  "settings.tab.integrations":  "Integrations",
  "settings.tab.knowledge":     "Knowledge",
  "settings.tab.security":      "Security",
  "settings.tab.language":      "Language",
  "settings.tab.billing":       "Subscription",

  "settings.language.title":       "Interface language",
  "settings.language.hint":        "Selection is saved in this browser. Switch is applied instantly.",
  "settings.language.label":       "Current language",
  "settings.language.note":        "Beta localization: parts of the UI are still English. Translation rolls out page by page.",
};

export type TranslationKey = keyof typeof ru;
export const translations: Record<Locale, Record<TranslationKey, string>> = { ru, en };
