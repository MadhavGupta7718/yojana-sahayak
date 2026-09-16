import { cookies } from "next/headers";
import { getMessages, t, type Locale } from "@/lib/i18n";
import SchemesClient from "@/components/SchemesClient";

async function fetchSchemes() {
  const base = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${base}/api/v1/schemes`, {
      cache: "no-store",
      next: { revalidate: 0 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : data.schemes || [];
  } catch {
    return [];
  }
}

export default async function SchemesPage() {
  const cookieStore = await cookies();
  const locale = (cookieStore.get("locale")?.value === "hi" ? "hi" : "en") as Locale;
  const messages = await getMessages(locale);
  const schemes = await fetchSchemes();

  return (
    <div className="ys-page">
      <header className="ys-pagehead">
        <div className="ys-wrap">
          <p className="ys-kicker">{locale === "hi" ? "सूची" : "Catalogue"}</p>
          <h1 className="ys-h1">{t(messages, "exploreSchemes")}</h1>
          <p className="ys-sub">
            {locale === "hi"
              ? "आधिकारिक स्रोतों से जुड़ी योजनाएँ — विवरण सरकारी वेबसाइट पर सत्यापित करें।"
              : "Schemes linked to official sources — always verify on the government website."}
          </p>
        </div>
      </header>

      <SchemesClient
        initialSchemes={schemes}
        locale={locale}
        labels={{
          empty: t(messages, "emptySchemes"),
          notAvailable: t(messages, "notAvailable"),
          freshness: t(messages, "freshness"),
          officialSource: t(messages, "officialSource"),
          searchPlaceholder:
            locale === "hi" ? "योजना नाम / उद्देश्य खोजें…" : "Search scheme name / purpose…",
          showing:
            locale === "hi"
              ? "दिखा रहे हैं {shown} / कुल {total} योजनाएँ"
              : "Showing {shown} of {total} schemes",
          loadError:
            locale === "hi"
              ? "योजनाएँ लोड नहीं हो सकीं। पुनः प्रयास करें।"
              : "Could not load schemes. Please retry.",
          retry: locale === "hi" ? "फिर से लोड करें" : "Reload",
          maxLoan: locale === "hi" ? "अधिकतम ऋण" : "Max loan",
          interest: locale === "hi" ? "ब्याज" : "Interest",
          allPurposes: locale === "hi" ? "सभी उद्देश्य" : "All purposes",
        }}
      />
    </div>
  );
}
