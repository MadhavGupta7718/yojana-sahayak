import type { Metadata } from "next";
import { cookies } from "next/headers";
import "./globals.css";
import { SiteHeader } from "@/components/SiteHeader";
import { Footer } from "@/components/Footer";
import { getMessages, type Locale } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "YojanaSahayak | योजना सहायक",
  description:
    "AI-driven government scheme matching for marginalized entrepreneurs. Official-source linked guidance only.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const locale = (cookieStore.get("locale")?.value === "hi" ? "hi" : "en") as Locale;
  const messages = (await getMessages(locale)) as Record<string, string>;

  return (
    <html lang={locale}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Noto+Sans+Devanagari:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <SiteHeader messages={messages} locale={locale} />
        <main>{children}</main>
        <Footer messages={messages} />
      </body>
    </html>
  );
}
