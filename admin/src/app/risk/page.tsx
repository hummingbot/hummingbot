import { StatusPill } from "@/components/StatusPill";

const controls = [
  { name: "数据充足性", state: "enabled", detail: "K 线不足时只能观察，禁止创建 Executor" },
  { name: "主动亏损上限", state: "enabled", detail: "达到阈值立即进入 Protect" },
  { name: "波动与成交量尖峰", state: "enabled", detail: "ATR 或 Volume Z-score 异常时停止新风险" },
  { name: "做空权限", state: "enabled", detail: "allow_short=false 时任何空头路由均被拦截" },
  { name: "单腿套利恢复", state: "enabled", detail: "超时停止，失败时重复发出幂等 Stop 动作" },
  { name: "全局资金分配器", state: "missing", detail: "尚未统一限制多个策略共享资本" },
  { name: "实盘发布审批", state: "policy", detail: "纸面 → Canary → 实盘，禁止越级" },
];

export default function RiskPage() {
  return <div className="page-stack"><section className="page-hero"><div><span className="eyebrow">CAPITAL PROTECTION</span><h1>风险中心</h1><p>收益优化只能在硬风控之内运行；Protect 的优先级永远高于策略选择。</p></div><StatusPill tone="green">PAPER-FIRST</StatusPill></section><section className="control-grid">{controls.map((control) => <div className="control-card" key={control.name}><StatusPill tone={control.state === "enabled" ? "green" : control.state === "missing" ? "red" : "amber"}>{control.state}</StatusPill><strong>{control.name}</strong><span>{control.detail}</span></div>)}</section><section className="panel"><div className="panel-head"><div><span className="eyebrow">PROMOTION GATES</span><h2>实盘晋级前置条件</h2></div></div><div className="gate-steps">{["Adapter 与停止路径完整","样本外回测扣除费用","Paper 观察窗口通过","极端场景与断线恢复通过","小资金 Canary 人工批准","持续监控与自动降级"].map((item, index) => <div key={item}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item}</strong></div>)}</div></section></div>;
}
