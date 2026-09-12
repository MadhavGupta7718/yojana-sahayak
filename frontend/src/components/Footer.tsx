import Link from "next/link";

export function Footer({ messages }: { messages: Record<string, string> }) {
  return (
    <footer className="ys-footer">
      <div className="ys-footer__inner">
        <div className="ys-footer__brand-block">
          <p className="ys-footer__brand">{messages.brand}</p>
          <p className="ys-footer__tag">Official-source scheme guidance</p>
        </div>
        <nav className="ys-footer__nav" aria-label="Footer">
          <Link href="/">{messages.navHome}</Link>
          <Link href="/find">{messages.navFind}</Link>
          <Link href="/schemes">{messages.navExplore}</Link>
          <Link href="/admin">{messages.navAdmin}</Link>
        </nav>
      </div>
      <p className="ys-footer__note">{messages.footerNote}</p>
    </footer>
  );
}
