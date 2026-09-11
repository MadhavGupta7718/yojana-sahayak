export type Locale = "en" | "hi";

export async function getMessages(locale: Locale) {
  if (locale === "hi") {
    return (await import("../../locales/hi/common.json")).default;
  }
  return (await import("../../locales/en/common.json")).default;
}

export function t(
  messages: Record<string, unknown>,
  key: string,
  fallback = ""
): string {
  const parts = key.split(".");
  let cur: unknown = messages;
  for (const p of parts) {
    if (cur && typeof cur === "object" && p in (cur as object)) {
      cur = (cur as Record<string, unknown>)[p];
    } else {
      return fallback || key;
    }
  }
  return typeof cur === "string" ? cur : fallback || key;
}
