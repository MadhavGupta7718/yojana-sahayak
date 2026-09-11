"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Locale } from "@/lib/i18n";

export function SiteHeader({
  messages,
  locale,
}: {
  messages: Record<string, string>;
  locale: Locale;
}) {
  const [lang, setLang] = useState<Locale>(locale);

  useEffect(() => {
    document.cookie = `locale=${lang};path=/;max-age=31536000`;
  }, [lang]);

  function switchLang(next: Locale) {
    setLang(next);
    document.cookie = `locale=${next};path=/;max-age=31536000`;
    window.location.reload();
  }

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link href="/" className="site-header__brand">
          {messages.brand}
        </Link>
        <nav className="site-header__nav" aria-label="Main">
          <Link href="/">{messages.navHome}</Link>
          <Link href="/find">{messages.navFind}</Link>
          <Link href="/schemes">{messages.navExplore}</Link>
          <Link href="/admin">{messages.navAdmin}</Link>
          <div className="lang-switch" role="group" aria-label="Language">
            <button
              type="button"
              onClick={() => switchLang("en")}
              className={lang === "en" ? "is-active" : ""}
            >
              English
            </button>
            <button
              type="button"
              onClick={() => switchLang("hi")}
              className={lang === "hi" ? "is-active" : ""}
            >
              हिन्दी
            </button>
          </div>
        </nav>
      </div>
    </header>
  );
}
