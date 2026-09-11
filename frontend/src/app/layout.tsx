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
      <body>
        <SiteHeader messages={messages} locale={locale} />
        <main>{children}</main>
        <Footer messages={messages} />
      </body>
    </html>
  );
}
