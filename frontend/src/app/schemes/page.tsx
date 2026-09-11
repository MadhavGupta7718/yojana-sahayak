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
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-3xl text-[var(--navy)]">{t(messages, "exploreSchemes")}</h1>
      <div className="mt-6 grid gap-4">
        {schemes.length === 0 && <p className="panel">{t(messages, "emptySchemes")}</p>}
        {schemes.map((s: any) => (
          <article key={s.id} className="panel">
            <h2 className="text-xl font-semibold">{s.name}</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">{s.description?.slice(0, 280) || t(messages, "notAvailable")}</p>
            <div className="mt-3 flex flex-wrap gap-4 text-sm">
              <span>
                Max loan: {s.max_loan != null ? `₹${s.max_loan}` : t(messages, "notAvailable")}
              </span>
              <span>
                Interest: {s.interest_rate != null ? `${s.interest_rate}%` : t(messages, "notAvailable")}
              </span>
              <span>
                {t(messages, "freshness")}: {s.freshness}
              </span>
            </div>
            {s.source_url && (
              <a className="mt-3 inline-block text-[var(--navy)] underline" href={s.source_url} target="_blank" rel="noreferrer">
                {t(messages, "officialSource")}
              </a>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
