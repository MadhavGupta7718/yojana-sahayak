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
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--surface)]/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="font-display text-xl font-bold tracking-tight text-[var(--navy)]">
          {messages.brand}
        </Link>
        <nav className="flex flex-wrap items-center gap-3 text-sm font-medium text-[var(--ink)]">
          <Link href="/" className="hover:text-[var(--saffron)]">
            {messages.navHome}
          </Link>
          <Link href="/find" className="hover:text-[var(--saffron)]">
            {messages.navFind}
          </Link>
          <Link href="/schemes" className="hover:text-[var(--saffron)]">
            {messages.navExplore}
          </Link>
          <Link href="/admin" className="hover:text-[var(--saffron)]">
            {messages.navAdmin}
          </Link>
          <div className="ml-2 flex overflow-hidden rounded-md border border-[var(--border)]">
            <button
              type="button"
              onClick={() => switchLang("en")}
              className={`px-2 py-1 ${lang === "en" ? "bg-[var(--navy)] text-white" : "bg-white"}`}
            >
              English
            </button>
            <button
              type="button"
              onClick={() => switchLang("hi")}
              className={`px-2 py-1 ${lang === "hi" ? "bg-[var(--navy)] text-white" : "bg-white"}`}
            >
              हिन्दी
            </button>
          </div>
        </nav>
      </div>
    </header>
  );
}
