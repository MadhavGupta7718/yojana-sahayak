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
  const categories = [
    t(messages, "catBusiness"),
    t(messages, "catEducation"),
    t(messages, "catMicro"),
  ];

  return (
    <div className="ys-home">
      <section className="ys-hero">
        <div className="ys-hero__media" aria-hidden="true" />
        <div className="ys-hero__panel">
          <p className="ys-hero__brand reveal">{t(messages, "brand")}</p>
          <h1 className="ys-hero__title reveal reveal-delay-1">{t(messages, "tagline")}</h1>
          <p className="ys-hero__lead reveal reveal-delay-2">{t(messages, "partnerPrivacy")}</p>
          <div className="ys-hero__actions reveal reveal-delay-3">
            <Link href="/find" className="ys-btn ys-btn--solid">
              {t(messages, "findScheme")}
            </Link>
            <Link href="/schemes" className="ys-btn ys-btn--ghost">
              {t(messages, "exploreSchemes")}
            </Link>
          </div>
        </div>
      </section>

      <section className="ys-block">
        <div className="ys-wrap">
          <p className="ys-kicker">01 — Process</p>
          <h2 className="ys-h2">{t(messages, "howItWorks")}</h2>
          <ol className="ys-timeline">
            {how.map((text, i) => (
              <li key={text} className="ys-timeline__item">
                <span className="ys-timeline__num">{String(i + 1).padStart(2, "0")}</span>
                <p>{text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="ys-block ys-block--tint">
        <div className="ys-wrap">
          <p className="ys-kicker">02 — Focus</p>
          <h2 className="ys-h2">{t(messages, "categories")}</h2>
          <p className="ys-sub">{t(messages, "multilingual")}</p>
          <ul className="ys-mega">
            {categories.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="ys-block">
        <div className="ys-wrap ys-split">
          <div>
            <p className="ys-kicker">03 — Trust</p>
            <h2 className="ys-h2">{t(messages, "whyPlatform")}</h2>
          </div>
          <ul className="ys-checklist">
            {why.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="ys-block ys-block--forest">
        <div className="ys-wrap">
          <p className="ys-kicker ys-kicker--light">04 — Source chain</p>
          <h2 className="ys-h2 ys-h2--light">{t(messages, "transparency")}</h2>
          <div className="ys-chain">
            {pipeline.map((p, i) => (
              <div key={p} className="ys-chain__node">
                <span>{p}</span>
                {i < pipeline.length - 1 && <i aria-hidden />}
              </div>
            ))}
          </div>
          <p className="ys-chain__note">{t(messages, "partnerExplain")}</p>
        </div>
      </section>

      <section className="ys-block ys-block--end">
        <div className="ys-wrap">
          <p className="ys-kicker">Disclaimer</p>
          <p className="ys-legal">{t(messages, "disclaimer")}</p>
        </div>
      </section>
    </div>
  );
}
