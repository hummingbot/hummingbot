import type { ReactNode } from "react";

export function StatusPill({ tone = "neutral", children }: { tone?: "green" | "amber" | "red" | "blue" | "neutral"; children: ReactNode }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

export function MetricCard({ label, value, hint, tone = "neutral" }: { label: string; value: string; hint: string; tone?: "green" | "amber" | "red" | "blue" | "purple" | "neutral" }) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-hint">{hint}</div>
    </div>
  );
}
