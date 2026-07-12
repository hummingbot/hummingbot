"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

const nav = [
  { href: "/", label: "运营总览", icon: "◫", group: "决策中心" },
  { href: "/router", label: "行情与路由", icon: "⌁", group: "决策中心" },
  { href: "/strategies", label: "策略资产库", icon: "◇", group: "策略运营" },
  { href: "/risk", label: "风险中心", icon: "△", group: "策略运营" },
  { href: "/operations", label: "迭代与部署", icon: "◎", group: "系统运维" },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const groups = Array.from(new Set(nav.map((item) => item.group)));
  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">H</div>
          <div><strong>Hummingbot AI</strong><span>Strategy Operations</span></div>
        </div>
        <nav>
          {groups.map((group) => (
            <div className="nav-group" key={group}>
              <div className="nav-label">{group}</div>
              {nav.filter((item) => item.group === group).map((item) => {
                const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                return <Link key={item.href} href={item.href} className={`nav-item ${active ? "active" : ""}`} onClick={() => setOpen(false)}><span>{item.icon}</span>{item.label}</Link>;
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot"><span className="status-dot" /> PAPER-FIRST<br /><small>实盘晋级默认关闭</small></div>
      </aside>
      <div className="main-frame">
        <header className="topbar">
          <button className="menu-button" onClick={() => setOpen((value) => !value)} aria-label="打开导航">☰</button>
          <div><span className="eyebrow">AI 策略运营台</span><strong>收益证据优先于策略数量</strong></div>
          <div className="operator"><span className="status-dot" /> 本机运营节点</div>
        </header>
        <main>{children}</main>
      </div>
      {open && <button className="mobile-scrim" onClick={() => setOpen(false)} aria-label="关闭导航" />}
    </div>
  );
}
