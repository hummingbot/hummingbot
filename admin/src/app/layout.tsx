import type { Metadata } from "next";
import "./globals.css";
import "./overrides.css";
import "./trading.css";
import "./routing.css";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = { title: "Hummingbot 智能策略运营台", description: "智能行情路由、策略晋级与风险运营" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body><Shell>{children}</Shell></body></html>;
}
