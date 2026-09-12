import { cookies } from "next/headers";
import { getMessages, t, type Locale } from "@/lib/i18n";

async function fetchSchemes() {
  const base = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${base}/api/v1/schemes`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
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
          <p className="ys-kicker">Catalogue</p>
          <h1 className="ys-h1">{t(messages, "exploreSchemes")}</h1>
          <p className="ys-sub">
            {locale === "hi"
              ? "आधिकारिक स्रोतों से जुड़ी योजनाएँ — विवरण सरकारी वेबसाइट पर सत्यापित करें।"
              : "Schemes linked to official sources — always verify on the government website."}
          </p>
        </div>
      </header>

      <div className="ys-wrap ys-schemes">
        {schemes.length === 0 && <p className="ys-empty">{t(messages, "emptySchemes")}</p>}
        {schemes.map((s: any) => (
          <article key={s.id} className="ys-scheme">
            <h2>{s.name}</h2>
            <p>{s.description?.slice(0, 280) || t(messages, "notAvailable")}</p>
            <div className="ys-scheme__meta">
              <span>
                Max loan:{" "}
                {s.max_loan != null ? `₹${Number(s.max_loan).toLocaleString("en-IN")}` : t(messages, "notAvailable")}
              </span>
              <span>
                Interest: {s.interest_rate != null ? `${s.interest_rate}%` : t(messages, "notAvailable")}
              </span>
              <span>
                {t(messages, "freshness")}: {s.freshness}
              </span>
            </div>
            {s.source_url && (
              <a className="ys-link" href={s.source_url} target="_blank" rel="noreferrer">
                {t(messages, "officialSource")} →
              </a>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
