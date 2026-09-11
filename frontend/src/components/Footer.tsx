"use client";

export function Footer({ messages }: { messages: Record<string, string> }) {
  return (
    <footer className="mt-16 border-t border-[var(--border)] bg-[var(--navy)] text-white">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <p className="font-display text-2xl">{messages.brand}</p>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-white/85">{messages.disclaimer}</p>
        <p className="mt-6 text-xs text-white/60">{messages.footerNote}</p>
      </div>
    </footer>
  );
}
