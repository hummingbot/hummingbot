import type { Metadata } from "next";
import "./globals.css";
import "./overrides.css";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = { title: "Hummingbot AI 策略运营台", description: "AI 行情路由、策略晋级与风险运营" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body><Shell>{children}</Shell></body></html>;
}
