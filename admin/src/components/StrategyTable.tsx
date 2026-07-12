"use client";

import { useMemo, useState } from "react";
import type { StrategyItem, StrategyStatus } from "@/lib/types";
import { StatusPill } from "./StatusPill";

const statusLabel: Record<StrategyStatus, string> = { enabled: "已启用", shadow: "影子评估", research: "研究池", blocked: "禁止晋级" };
const tone: Record<StrategyStatus, "green" | "blue" | "neutral" | "red"> = { enabled: "green", shadow: "blue", research: "neutral", blocked: "red" };

export function StrategyTable({ strategies }: { strategies: StrategyItem[] }) {
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState("all");
  const [status, setStatus] = useState("all");
  const families = Array.from(new Set(strategies.map((item) => item.family))).sort();
  const visible = useMemo(() => strategies.filter((item) => {
    const text = `${item.id} ${item.name} ${item.summary} ${item.source}`.toLowerCase();
    return (!query || text.includes(query.toLowerCase())) && (family === "all" || item.family === family) && (status === "all" || item.status === status);
  }), [strategies, query, family, status]);

  return (
    <>
      <div className="filterbar">
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索策略、来源或机制" />
        <select value={family} onChange={(event) => setFamily(event.target.value)}><option value="all">全部家族</option>{families.map((value) => <option key={value}>{value}</option>)}</select>
        <select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">全部状态</option><option value="enabled">已启用</option><option value="shadow">影子评估</option><option value="research">研究池</option><option value="blocked">禁止晋级</option></select>
        <span className="filter-count">{visible.length} / {strategies.length}</span>
      </div>
      <div className="table-shell">
        <table>
          <thead><tr><th>策略</th><th>家族 / 行情</th><th>证据</th><th>风险</th><th>来源</th><th>状态</th></tr></thead>
          <tbody>{visible.map((item) => (
            <tr key={item.id}>
              <td><strong>{item.name}</strong><code>{item.id}</code><small>{item.summary}</small></td>
              <td><span className="family-tag">{item.family}</span><small>{item.regimes.join(" · ")}</small></td>
              <td><strong>{item.evidence.replaceAll("_", " ")}</strong><small>Adapter: {item.adapter}</small></td>
              <td><span className="risk-text">{item.risk.replaceAll("_", " ")}</span></td>
              <td><strong>{item.source}</strong><small>{item.license}</small></td>
              <td><StatusPill tone={tone[item.status]}>{statusLabel[item.status]}</StatusPill></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}
