import { StatusPill } from "@/components/StatusPill";
import { zhLabel } from "@/lib/i18n";

const controls = [
  { name: "数据充足性", state: "enabled", detail: "K 线不足时只能观察，禁止创建执行器" },
  { name: "主动亏损上限", state: "enabled", detail: "达到阈值立即进入保护模式" },
  { name: "波动与成交量尖峰", state: "enabled", detail: "平均真实波幅或成交量标准分异常时停止新增风险" },
  { name: "做空权限", state: "enabled", detail: "做空配置关闭时，任何空头路由均被拦截" },
  { name: "单腿套利恢复", state: "enabled", detail: "超时停止，失败时重复发出幂等停止动作" },
  { name: "全局资金分配器", state: "missing", detail: "尚未统一限制多个策略共享资本" },
  { name: "实盘发布审批", state: "policy", detail: "纸面 → 小额灰度 → 实盘，禁止越级" },
];

export default function RiskPage() {
  return <div className="page-stack"><section className="page-hero"><div><span className="eyebrow">资金保护</span><h1>风险中心</h1><p>收益优化只能在硬风控之内运行；保护模式的优先级永远高于策略选择。</p></div><StatusPill tone="green">纸面优先</StatusPill></section><section className="control-grid">{controls.map((control) => <div className="control-card" key={control.name}><StatusPill tone={control.state === "enabled" ? "green" : control.state === "missing" ? "red" : "amber"}>{control.state === "policy" ? "策略约束" : zhLabel(control.state)}</StatusPill><strong>{control.name}</strong><span>{control.detail}</span></div>)}</section><section className="panel"><div className="panel-head"><div><span className="eyebrow">晋级门禁</span><h2>实盘晋级前置条件</h2></div></div><div className="gate-steps">{["适配器与停止路径完整","样本外回测已扣除费用","纸面观察窗口通过","极端场景与断线恢复通过","小资金灰度人工批准","持续监控与自动降级"].map((item, index) => <div key={item}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item}</strong></div>)}</div></section></div>;
}
