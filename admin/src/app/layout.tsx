import type { Metadata } from "next";
import "./globals.css";
import "./overrides.css";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = { title: "Hummingbot AI Admin", description: "AI strategy routing and risk operations" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body><Shell>{children}</Shell></body></html>;
}
