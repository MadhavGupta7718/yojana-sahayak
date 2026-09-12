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
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    document.cookie = `locale=${lang};path=/;max-age=31536000`;
  }, [lang]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function switchLang(next: Locale) {
    setLang(next);
    document.cookie = `locale=${next};path=/;max-age=31536000`;
    window.location.reload();
  }

  return (
    <header className={`ys-header${scrolled ? " is-scrolled" : ""}`}>
      <div className="ys-header__inner">
        <Link href="/" className="ys-logo">
          <span className="ys-logo__mark" aria-hidden />
          <span className="ys-logo__text">{messages.brand}</span>
        </Link>
        <nav className="ys-nav" aria-label="Main">
          <Link href="/">{messages.navHome}</Link>
          <Link href="/find">{messages.navFind}</Link>
          <Link href="/schemes">{messages.navExplore}</Link>
          <Link href="/admin">{messages.navAdmin}</Link>
          <div className="ys-lang" role="group" aria-label="Language">
            <button type="button" onClick={() => switchLang("en")} className={lang === "en" ? "is-active" : ""}>
              EN
            </button>
            <span aria-hidden>/</span>
            <button type="button" onClick={() => switchLang("hi")} className={lang === "hi" ? "is-active" : ""}>
              हिं
            </button>
          </div>
        </nav>
      </div>
    </header>
  );
}
