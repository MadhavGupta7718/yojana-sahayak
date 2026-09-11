import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const locale = request.cookies.get("locale")?.value || "en";
  const response = NextResponse.next();
  response.headers.set("x-locale", locale);
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
