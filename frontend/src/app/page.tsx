import Link from "next/link";
import { cookies } from "next/headers";
import { getMessages, t, type Locale } from "@/lib/i18n";

export default async function HomePage() {
  const cookieStore = await cookies();
  const locale = (cookieStore.get("locale")?.value === "hi" ? "hi" : "en") as Locale;
  const messages = await getMessages(locale);

  const how = ["1", "2", "3", "4"].map((n) => t(messages, `howSteps.${n}`));
  const why = ["1", "2", "3", "4"].map((n) => t(messages, `whyPoints.${n}`));
  const pipeline = ["1", "2", "3", "4", "5", "6"].map((n) => t(messages, `pipeline.${n}`));

  return (
    <div>
      <section className="relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(135deg, rgba(11,58,91,0.92), rgba(31,107,74,0.88)), url('data:image/svg+xml,%3Csvg width=\"60\" height=\"60\" xmlns=\"http://www.w3.org/2000/svg\"%3E%3Cg fill=\"none\" stroke=\"%23ffffff22\" stroke-width=\"1\"%3E%3Cpath d=\"M0 30h60M30 0v60\"/%3E%3C/g%3E%3C/svg%3E')",
            backgroundSize: "cover, 40px 40px",
          }}
        />
        <div className="relative mx-auto flex min-h-[78vh] max-w-6xl flex-col justify-center px-4 py-16 text-white">
          <p className="fade-up font-display text-5xl font-bold leading-tight md:text-6xl">
            {t(messages, "brand")}
          </p>
          <h1 className="fade-up mt-4 max-w-3xl text-2xl font-semibold leading-snug md:text-3xl" style={{ animationDelay: "0.08s" }}>
            {t(messages, "tagline")}
          </h1>
          <p className="fade-up mt-4 max-w-2xl text-base text-white/85" style={{ animationDelay: "0.16s" }}>
            {t(messages, "partnerPrivacy")}
          </p>
          <div className="fade-up mt-8 flex flex-wrap gap-3" style={{ animationDelay: "0.24s" }}>
            <Link href="/find" className="btn btn-primary">
              {t(messages, "findScheme")}
            </Link>
            <Link href="/schemes" className="btn btn-secondary">
              {t(messages, "exploreSchemes")}
            </Link>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="font-display text-3xl text-[var(--navy)]">{t(messages, "howItWorks")}</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-4">
            {how.map((text, i) => (
              <div key={text} className="panel">
                <div className="mb-2 text-sm font-bold text-[var(--saffron)]">0{i + 1}</div>
                <p className="text-[var(--ink)]">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section bg-white/50">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="font-display text-3xl text-[var(--navy)]">{t(messages, "categories")}</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {[t(messages, "catBusiness"), t(messages, "catEducation"), t(messages, "catMicro")].map((c) => (
              <div key={c} className="panel border-l-4 border-l-[var(--green)]">
                <p className="text-lg font-semibold">{c}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="font-display text-3xl text-[var(--navy)]">{t(messages, "whyPlatform")}</h2>
          <ul className="mt-6 grid gap-3 md:grid-cols-2">
            {why.map((w) => (
              <li key={w} className="panel">
                {w}
              </li>
            ))}
          </ul>
          <p className="mt-6 text-[var(--muted)]">{t(messages, "multilingual")}</p>
        </div>
      </section>

      <section className="section bg-[var(--navy)] text-white">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="font-display text-3xl">{t(messages, "transparency")}</h2>
          <div className="mt-8 flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center">
            {pipeline.map((p, i) => (
              <div key={p} className="flex items-center gap-3">
                <div className="rounded-lg bg-white/10 px-4 py-3 text-sm font-semibold">{p}</div>
                {i < pipeline.length - 1 && <span className="hidden text-white/50 md:inline">→</span>}
              </div>
            ))}
          </div>
          <p className="mt-8 max-w-3xl text-white/80">{t(messages, "partnerExplain")}</p>
        </div>
      </section>

      <section className="section">
        <div className="mx-auto max-w-6xl px-4">
          <div className="panel border-l-4 border-l-[var(--saffron)]">
            <h2 className="font-display text-2xl text-[var(--navy)]">Disclaimer / अस्वीकरण</h2>
            <p className="mt-3 leading-relaxed text-[var(--muted)]">{t(messages, "disclaimer")}</p>
          </div>
        </div>
      </section>
    </div>
  );
}
