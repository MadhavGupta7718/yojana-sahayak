import { cookies } from "next/headers";
import FindClient from "@/components/FindClient";
import { getMessages, type Locale } from "@/lib/i18n";

export default async function FindPage() {
  const cookieStore = await cookies();
  const locale = (cookieStore.get("locale")?.value === "hi" ? "hi" : "en") as Locale;
  const messages = (await getMessages(locale)) as Record<string, string>;
  return <FindClient messages={messages} locale={locale} />;
}
