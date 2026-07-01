from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "pdf"
TMP_DIR = ROOT / "tmp" / "pdfs"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

PDF_PATH = OUT_DIR / "prediction_market_arbitrage_research_2026-06-19.pdf"


FONT_REGULAR = "/Library/Fonts/Arial Unicode.ttf"
FONT_FALLBACK = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
font_path = FONT_REGULAR if Path(FONT_REGULAR).exists() else FONT_FALLBACK
pdfmetrics.registerFont(TTFont("CJK", font_path))
pdfmetrics.registerFont(TTFont("CJK-Bold", font_path))


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName="CJK-Bold",
            fontSize=24,
            leading=31,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#111827"),
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["BodyText"],
            fontName="CJK",
            fontSize=10.5,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=18,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="CJK-Bold",
            fontSize=16,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=12,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="CJK-Bold",
            fontSize=12,
            leading=17,
            textColor=colors.HexColor("#111827"),
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName="CJK",
            fontSize=9.5,
            leading=15,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["BodyText"],
            fontName="CJK",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#374151"),
        ),
        "table": ParagraphStyle(
            "table",
            parent=base["BodyText"],
            fontName="CJK",
            fontSize=7.6,
            leading=10.5,
            textColor=colors.HexColor("#111827"),
        ),
        "table_head": ParagraphStyle(
            "table_head",
            parent=base["BodyText"],
            fontName="CJK-Bold",
            fontSize=7.8,
            leading=10.5,
            textColor=colors.white,
        ),
        "callout": ParagraphStyle(
            "callout",
            parent=base["BodyText"],
            fontName="CJK-Bold",
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#0F172A"),
            backColor=colors.HexColor("#E0F2FE"),
            borderColor=colors.HexColor("#0284C7"),
            borderWidth=0.8,
            borderPadding=8,
            spaceAfter=10,
        ),
    }


S = styles()


def P(text, style="body"):
    return Paragraph(text, S[style])


def T(rows, widths, header=True):
    converted = []
    for r_i, row in enumerate(rows):
        converted.append([P(str(cell), "table_head" if header and r_i == 0 else "table") for cell in row])
    table = Table(converted, colWidths=widths, repeatRows=1 if header else 0)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A") if header else colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]
        )
    )
    return table


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("CJK", 7.5)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(18 * mm, 12 * mm, "Prediction market arbitrage research - Hummingbot integration")
    canvas.drawRightString(192 * mm, 12 * mm, f"{doc.page}")
    canvas.restoreState()


def build():
    doc = BaseDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="Prediction Market Arbitrage Research",
        author="Codex",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=header_footer)])

    story = []
    story.append(P("预测市场套利工具调研报告", "title"))
    story.append(P("面向 Hummingbot 底层架构的多平台接入与套利执行路线", "subtitle"))
    story.append(P(f"调研日期：{date(2026, 6, 19).isoformat()} | 范围：独立预测市场与事件合约平台，不包含传统交易所普通现货/永续/期权产品", "subtitle"))

    story.append(P("核心结论", "h1"))
    story.append(P("可工程化套利的平台池比市场宣传口径小得多。广义预测/竞猜/积分平台可以累计到几十个甚至上百个，但满足“真钱交易、可程序化行情、可下单撤单、明确结算、足够流动性”的平台，目前应按 5-20 个候选池管理，第一阶段只建议接入 Polymarket 与 Kalshi，再扩展少数链上体育/预测协议。", "callout"))
    story.append(P("Hummingbot 的现有优势是 connector、订单跟踪、策略执行和风控框架；缺口不是交易基础设施，而是预测市场语义层：事件、outcome、结算规则、概率价格、平台费用、事件匹配和双腿/多腿执行风险。", "body"))

    story.append(P("建议优先级", "h2"))
    priority = [
        ["阶段", "目标", "说明"],
        ["P0", "只读数据层", "接入 Polymarket/Kalshi 的市场列表、订单簿、成交、费用、结算字段；先不自动下单。"],
        ["P1", "事件匹配与机会扫描", "建立 World Cup、加密货币、宏观事件的手动映射表，计算净价差和可成交尺寸。"],
        ["P2", "小资金执行", "支持 IOC/限价双腿执行、partial fill 处理、失败回滚和单事件敞口限制。"],
        ["P3", "横向扩展", "加入 Azuro/Omen/Manifold 等低优先级或特定场景平台；只把 API/流动性达标者纳入自动交易。"],
    ]
    story.append(T(priority, [22 * mm, 43 * mm, 100 * mm]))

    story.append(P("市场版图", "h1"))
    story.append(P("本报告把平台分成四类：A 类适合自动套利，B 类适合行情和半自动，C 类适合研究/信号，D 类暂不建议。这个分法比“平台数量”更重要，因为套利系统最怕把无法成交、无法结算或结算口径不同的市场当成同一资产。", "body"))
    universe = [
        ["类别", "定义", "代表平台", "工程含义"],
        ["A 类", "真钱、订单簿/API、可程序化交易、结算规则清晰", "Polymarket, Kalshi", "第一阶段接入；可做跨平台套利、组合套利、做市。"],
        ["B 类", "链上或协议型，有交易路径但流动性/盘口结构不如 A 类", "Azuro, Omen/Gnosis, Augur/Seer 等", "观察和专项接入；适合体育或链上事件，不宜一开始重仓。"],
        ["C 类", "有预测数据但交易性弱或不是现金市场", "Manifold, Metaculus", "作为信号源、事件发现和概率参考，不作为自动执行主腿。"],
        ["D 类", "活动、竞猜、地区化产品、无公开 API 或规则不透明", "大量新兴 App/营销活动", "只做 discovery，不进入自动交易。"],
    ]
    story.append(T(universe, [18 * mm, 45 * mm, 42 * mm, 60 * mm]))

    story.append(P("重点平台可接入性评分", "h1"))
    platforms = [
        ["平台", "交易/市场结构", "API 与自动化", "流动性判断", "接入优先级"],
        ["Polymarket", "CLOB + 条件代币；价格为 0-1 概率；覆盖体育、政治、宏观、科技等。", "官方文档包含 Markets & Events、Prices & Orderbook、Trading、WebSocket、Market Makers、SDK。", "最高；世界杯等大事件有深盘口和活跃做市。", "最高"],
        ["Kalshi", "美国合规 event contracts；二元/多结果事件；美元账户体系。", "官方说明 Predictions APIs 提供 REST、WebSocket、FIX，并有 demo 环境和 API key。", "高；体育占比很高，宏观/政治也有市场。", "最高"],
        ["PredictIt", "政治事件为主；历史悠久，交易规则限制多。", "公开自动交易能力弱于 Polymarket/Kalshi；监管限制需要单独核实。", "中；适合政治类信号，不适合作第一批执行腿。", "中"],
        ["Manifold", "积分/声誉为主；曾有 Sweepcash，后已停止真钱兑换。", "API 明确支持 markets/bets，文档称可用于 bots 和 automated trading，但不是稳定真钱套利场景。", "中低；信号价值大于套利价值。", "低"],
        ["Azuro", "去中心化体育预测/博彩协议；vAMM/LP 池模型。", "提供开发者中心、SDK、合约、subgraph/索引和 betting engine 文档。", "事件集中在体育；流动性和对手方模型与 CLOB 不同。", "中"],
        ["Omen/Gnosis/Seer/Augur", "链上预测市场协议或老平台；多为 AMM/条件代币/预言机结算。", "可通过链上合约、subgraph 或协议 SDK 接入；统一性较差。", "通常低于 Polymarket；长尾市场多。", "低-中"],
        ["Crypto.com/CDNA/FanDuel Predicts/Fanatics Markets", "合规事件合约或体育预测产品。", "公开资料显示产品存在或推出，但面向外部 bot 的 API 开放程度需逐项确认。", "潜力高，开放性未知。", "观察"],
    ]
    story.append(T(platforms, [25 * mm, 38 * mm, 47 * mm, 31 * mm, 24 * mm]))

    story.append(P("套利机会类型", "h1"))
    arb_types = [
        ["类型", "公式/判断", "主要风险", "适合阶段"],
        ["同 outcome 跨平台价差", "A 平台买 YES，B 平台卖 YES；净边际 = bid_B - ask_A - fees - slippage。", "两边事件规则不完全一致；一腿成交一腿失败；提现/区域限制。", "P1-P2"],
        ["YES/NO 组合套利", "同一事件 YES ask + NO ask < 1，买满组合锁定结算收益。", "平台是否支持完整组合、费用、结算延迟、市场取消。", "P2"],
        ["多 outcome 篮子", "所有互斥 outcome 的总买入成本 < 1。", "遗漏 outcome、规则包含 void/invalid、资金占用久。", "P2-P3"],
        ["事件市场 vs 传统价格源", "预测 BTC 是否触价，与期权/永续隐含概率比较。", "不是纯预测平台套利；需金融模型和对冲腿。", "后续专项"],
        ["流动性奖励套利", "做市收益 + 平台奖励 > 库存风险 + 结算风险。", "奖励规则变化、刷量检测、边界概率市场深度虚高。", "P3"],
    ]
    story.append(T(arb_types, [32 * mm, 50 * mm, 55 * mm, 28 * mm]))

    story.append(P("Hummingbot 需要新增的代码层", "h1"))
    story.append(P("现有仓库已经有 connector、strategy、controller、gateway/data_feed 等框架。预测市场接入不应把事件市场硬编码成普通 BTC-USDT 交易对，而应在 connector 和 controller 之间增加一个 prediction_market 包。", "body"))
    modules = [
        ["模块", "建议路径", "职责"],
        ["平台能力注册", "hummingbot/prediction_market/venue_registry.py", "记录 API、订单簿、真钱属性、结算规则、地区限制、费率、是否允许自动交易。"],
        ["标准数据模型", "hummingbot/prediction_market/data_types.py", "PredictionEvent、PredictionMarket、Outcome、OutcomeToken、ResolutionStatus、PredictionOrderBook。"],
        ["平台 connector", "hummingbot/connector/exchange/polymarket/ 和 kalshi/", "REST/WS 行情、账户、订单生命周期、签名、余额、仓位、成交回报。"],
        ["事件匹配", "hummingbot/prediction_market/event_matcher.py", "人工映射优先；文本相似度、到期时间、结算来源、outcome 语义辅助。"],
        ["概率/费用归一化", "hummingbot/prediction_market/probability.py, fees.py", "把 0-1 概率、美元 cent、AMM odds、手续费和滑点转成统一可比较价格。"],
        ["套利扫描器", "hummingbot/prediction_market/arb_scanner.py", "计算净边际、可成交尺寸、资金占用、过期窗口、结算差异惩罚。"],
        ["执行器", "hummingbot/strategy_v2/executors 或 controllers/generic/prediction_market_arb.py", "双腿/多腿限价执行、partial fill、撤单、对冲、失败状态机。"],
        ["审计与回放", "data/prediction_market/ 或外部 DB", "保存市场元数据、订单簿快照、机会、成交、结算结果，用于回测和事故复盘。"],
    ]
    story.append(T(modules, [35 * mm, 56 * mm, 74 * mm]))

    story.append(P("最小可行版本设计", "h1"))
    story.append(P("MVP 不建议一开始自动下单。第一版目标是高可信发现机会：每 1-5 秒读取盘口，基于手动事件映射计算净价差，并输出带证据的机会记录。这样可以先验证事件匹配、费用、盘口深度和结算规则，而不是把风险集中到执行器。", "body"))
    mvp = [
        ["组件", "输入", "输出"],
        ["MarketDiscovery", "Polymarket/Kalshi 市场列表、标签、到期时间、规则文本", "候选事件池和原始平台 market_id。"],
        ["ManualMapping", "人工配置 YAML/SQLite 表", "canonical_event_id 与 platform_market_id/outcome_id 的映射。"],
        ["OrderBookNormalizer", "平台订单簿或 AMM 报价", "统一 bid/ask/depth，按 outcome 维度展开。"],
        ["ArbScanner", "统一盘口、费用、最小利润阈值、最大敞口", "机会列表：edge、size、venue pair、规则差异提示。"],
        ["RiskGate", "事件状态、结算源、close time、钱包/账户余额", "允许报警/禁止交易/需要人工确认。"],
    ]
    story.append(T(mvp, [38 * mm, 67 * mm, 60 * mm]))

    story.append(P("关键风险", "h1"))
    risks = [
        ["风险", "为什么重要", "控制办法"],
        ["事件不等价", "两个问题标题相似，但结算依据、时间范围、取消条件不同。", "人工映射为默认；自动匹配只能建议，不自动授权。"],
        ["结算/争议风险", "预测市场常见争议、clarification、oracle 投票、void/invalid。", "记录规则快照；事件临近结算降低仓位；高争议市场禁入。"],
        ["流动性幻觉", "盘口顶层有价但尺寸小，或奖励驱动导致成交质量差。", "用深度加权价格，不用 mid price；设置最小可成交量。"],
        ["双腿执行失败", "一边成交后另一边价格消失，会形成裸露方向敞口。", "IOC/限价保护、超时撤单、仓位上限、失败后人工/自动对冲。"],
        ["地区与合规限制", "平台可能限制国家/州/地区，且规则变化快。", "venue_registry 中加入 jurisdiction 和 account eligibility，不绕过限制。"],
        ["API 稳定性", "新平台文档和接口变化快，WebSocket/订单回报不稳定。", "每个平台先只读运行，再小额灰度；接口版本锁定。"],
    ]
    story.append(T(risks, [35 * mm, 62 * mm, 68 * mm]))

    story.append(P("工程路线图", "h1"))
    roadmap = [
        ["周期", "交付物", "验收标准"],
        ["第 1 周", "平台能力注册表、标准数据模型、Polymarket/Kalshi 只读 market discovery。", "能稳定列出事件、outcome、到期时间、规则文本、market_id/token_id。"],
        ["第 2 周", "订单簿归一化、手动事件映射、机会扫描器。", "能对世界杯/加密/宏观事件输出净 edge 和 size，并保存快照。"],
        ["第 3 周", "回放器和纸面交易；加入费用、滑点、最小深度、结算风险评分。", "纸面交易结果可复盘，机会误报原因可解释。"],
        ["第 4 周", "小额执行器，仅白名单事件和白名单平台。", "双腿成交、partial fill、撤单和失败状态都有日志和风控。"],
        ["第 5 周+", "扩展 Azuro/Omen/其他平台，做市场匹配自动建议。", "新增平台不改策略核心，只新增 connector/adapter。"],
    ]
    story.append(T(roadmap, [24 * mm, 81 * mm, 60 * mm]))

    story.append(P("可信度评估", "h1"))
    story.append(P("本报告对平台采用三类证据：官方开发者文档优先，其次为主流媒体/监管新闻，最后为学术或开源研究。对没有官方 API 文档或无法验证交易接口的平台，本报告只给“观察”或“低优先级”，不作为自动套利候选。", "body"))
    evidence = [
        ["判断", "可信度", "依据"],
        ["Polymarket/Kalshi 是第一批工程候选", "高", "两者都有官方 API/SDK/订单簿/交易文档，且近期市场活跃度高。"],
        ["全球广义平台可达几十个以上", "中", "包括真钱、积分、链上协议、历史平台、地区性产品；但口径差异大。"],
        ["自动套利候选目前只有 5-20 个", "中高", "过滤条件包括 API、真钱、流动性、清晰结算和可自动交易，满足条件的平台显著减少。"],
        ["新兴体育预测产品值得跟踪", "中", "FanDuel/Crypto.com 等方向增长快，但外部 API 开放性需要逐一确认。"],
    ]
    story.append(T(evidence, [50 * mm, 24 * mm, 91 * mm]))

    story.append(P("参考来源", "h1"))
    refs = [
        "Polymarket Documentation: https://docs.polymarket.com/ - 官方文档列出 Markets & Events、Prices & Orderbook、Trading、WebSocket、Market Makers、SDK。",
        "Kalshi API Documentation: https://docs.kalshi.com/ - 官方文档说明 Predictions APIs 支持 REST、WebSocket、FIX，并提供 OpenAPI/AsyncAPI spec。",
        "Manifold API Documentation: https://docs.manifold.markets/api - 官方 API 文档说明 markets/bets、认证、rate limit、自动化用途和 alpha 状态。",
        "Azuro Docs: https://docs.azuro.org/ - 官方文档说明其为 EVM 链上预测市场协议，提供 Developer Hub、SDK、合约和 subgraph/API。",
        "Business Insider, 2026-06-19: prediction markets gained World Cup activity versus sportsbooks, naming Kalshi and Polymarket.",
        "Financial Times, 2026-06-11: World Cup winner prediction market volume reported near USD 2bn, dominated by Polymarket and Kalshi.",
        "PredictionMarketBench, arXiv 2602.00133 - 强调订单簿、费用、结算生命周期和真实执行仿真的重要性。",
        "PolyBench, arXiv 2604.14199 - 基于 Polymarket CLOB 和新闻流评估交易代理，说明订单簿状态对策略评估很关键。",
        "Decomposing Crowd Wisdom, arXiv 2602.19520 - 使用 Kalshi/Polymarket 大样本交易研究校准偏差，提示价格不能机械视为真实概率。",
        "本地 Hummingbot 仓库：hummingbot/connector、controllers/generic、hummingbot/data_feed、hummingbot/strategy。用于判断接入点和模块边界。",
    ]
    for ref in refs:
        story.append(P("• " + ref, "small"))
        story.append(Spacer(1, 2))

    story.append(P("附录：平台初筛规则", "h1"))
    story.append(P("新增平台进入自动交易候选池前，必须回答七个问题：是否真钱结算；是否有稳定 market discovery；是否有 orderbook 或可计算成交报价；是否有下单/撤单/成交回报；是否有清晰规则文本和结算来源；是否允许当前账户/地区交易；是否有足够盘口深度覆盖手续费和执行风险。只要任一核心项为否，就只能做行情监控或研究信号。", "body"))

    doc.build(story)
    return PDF_PATH


if __name__ == "__main__":
    print(build())
