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
      <section className="hero">
        <div className="hero__bg" aria-hidden="true" />
        <div className="hero__content">
          <p className="hero__brand fade-up">{t(messages, "brand")}</p>
          <h1 className="hero__title fade-up" style={{ animationDelay: "0.08s" }}>
            {t(messages, "tagline")}
          </h1>
          <p className="hero__lead fade-up" style={{ animationDelay: "0.16s" }}>
            {t(messages, "partnerPrivacy")}
          </p>
          <div className="hero__actions fade-up" style={{ animationDelay: "0.24s" }}>
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
        <div className="section__inner">
          <h2 className="section__title">{t(messages, "howItWorks")}</h2>
          <div className="card-grid cols-4">
            {how.map((text, i) => (
              <div key={text} className="panel">
                <div className="step-num">0{i + 1}</div>
                <p style={{ margin: 0 }}>{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section section-muted">
        <div className="section__inner">
          <h2 className="section__title">{t(messages, "categories")}</h2>
          <div className="card-grid cols-3">
            {[t(messages, "catBusiness"), t(messages, "catEducation"), t(messages, "catMicro")].map((c) => (
              <div key={c} className="panel panel-accent">
                <p style={{ margin: 0, fontSize: "1.1rem", fontWeight: 600 }}>{c}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section__inner">
          <h2 className="section__title">{t(messages, "whyPlatform")}</h2>
          <ul className="card-grid cols-2" style={{ listStyle: "none", padding: 0, marginTop: "1.5rem" }}>
            {why.map((w) => (
              <li key={w} className="panel">
                {w}
              </li>
            ))}
          </ul>
          <p className="muted" style={{ marginTop: "1.5rem" }}>
            {t(messages, "multilingual")}
          </p>
        </div>
      </section>

      <section className="section section-dark">
        <div className="section__inner">
          <h2 className="section__title" style={{ color: "white" }}>
            {t(messages, "transparency")}
          </h2>
          <div className="pipeline">
            {pipeline.map((p, i) => (
              <div key={p} style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <div className="pipeline__item">{p}</div>
                {i < pipeline.length - 1 && <span className="pipeline__arrow">→</span>}
              </div>
            ))}
          </div>
          <p style={{ marginTop: "2rem", maxWidth: "42rem", color: "rgba(255,255,255,0.8)" }}>
            {t(messages, "partnerExplain")}
          </p>
        </div>
      </section>

      <section className="section">
        <div className="section__inner">
          <div className="panel panel-warn">
            <h2 className="section__title" style={{ fontSize: "1.45rem" }}>
              Disclaimer / अस्वीकरण
            </h2>
            <p className="muted" style={{ marginTop: "0.75rem", lineHeight: 1.65 }}>
              {t(messages, "disclaimer")}
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
