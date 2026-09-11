export function Footer({ messages }: { messages: Record<string, string> }) {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <p className="font-display" style={{ fontSize: "1.6rem", margin: 0 }}>
          {messages.brand}
        </p>
        <p style={{ marginTop: "0.85rem", maxWidth: "48rem", lineHeight: 1.6, color: "rgba(255,255,255,0.85)", fontSize: "0.95rem" }}>
          {messages.disclaimer}
        </p>
        <p style={{ marginTop: "1.5rem", fontSize: "0.8rem", color: "rgba(255,255,255,0.6)" }}>
          {messages.footerNote}
        </p>
      </div>
    </footer>
  );
}
