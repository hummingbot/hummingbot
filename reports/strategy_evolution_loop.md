# 多策略进化 Loop

## 目标

把每个策略当成独立实验对象，统一执行以下闭环：

```text
策略假设 → 证据采集 → 门禁评估 → 单一实验 → 验证 → 记录 → 推进/暂停
```

PMM、趋势和套利策略各自维护状态、证据与实验，不共享参数结论。统一监督器只负责执行共同纪律，不负责替策略做交易。

## 当前结构

```text
conf/strategy_evolution.json
        │
        ├── 每个策略的 thesis、证据路径、纸盘门槛和检查命令
        ▼
hummingbot/strategy_v2/evolution/
        ├── models.py       阶段、门禁、证据、实验和状态协议
        ├── config.py       配置验证；强制 allow_live_actions=false
        ├── evidence.py     只读采集报告、运行快照和 SQLite
        ├── engine.py       单策略单轮状态机与实验规划
        ├── playbooks.py    基于已有证据生成单参数轴候选
        ├── automation.py   全局选择、安全执行与结果判决
        ├── lineage.py      不可变候选、研究冠军与正负反馈谱系
        ├── paper.py        PMM 纸盘配置暂存、预检、启动与回滚协议
        ├── runtime.py      离线实验隔离运行时
        ├── operations.py   发布源码指纹与运行身份
        ├── store.py        原子状态与 append-only 逐轮账本
        └── supervisor.py   多策略隔离推进、锁和汇总战报

hummingbot/strategy_v2/backtesting/candidate_io.py
                            将隔离候选传给现有滚动验证脚本
        ▼
data/strategy-evolution/
        ├── latest.json / latest.md
        ├── supervisor-events.jsonl
        ├── experiments/<experiment-id>/候选、报告与判决
        └── strategies/<id>/
            ├── state.json + events.jsonl
            ├── candidates/ + evaluations/ + lineage.jsonl
            └── paper/staged.json + active.json + deployments/
```

## V2.1 能力

- 三个首批策略：`pmm_mister`、`funding_rate_arb`、`supertrend_v1`。
- 每个策略独立判断适配器、停止路径、含成本滚动样本外、证据新鲜度、纸盘样本、纸盘亏损和人工批准。
- 每轮最多提出一个实验，参数变更预算最多为 1；自动实验必须先通过证据完整性与确定性检查。
- 智能选择器从全部策略中挑选至多一个可执行实验；处于纸盘采样期的策略继续后台观察，不阻塞其他策略的离线实验。
- 自动实验在 Hummingbot Docker 环境中运行：源码只读覆盖，只有当前实验目录可写，宿主缺少 Python 依赖不再阻断验证。
- PMM 对每个固定候选使用相同样本外窗口做配对验证；动态折内选择不能冒充可部署冠军。
- 正负结果都会进入候选谱系；失败参数会降低步长并影响下一参数轴，已评估参数不会机械重复。
- 未通过绝对门槛的完整报告也会记录所选候选、全部提议参数和失败原因；研究拒绝采用 1 小时起步、最高 24 小时的递增冷却，避免守护进程每轮空转。
- 通过后生成 `candidate_id + code_hash + parameter_hash + dataset_fingerprint + artifact_sha256`，并建立或比较研究冠军。
- PMM 研究冠军会生成独立的 controller/script 纸盘配置包，不覆盖当前基线配置。
- 纸盘自动切换必须同时满足：纯纸盘、快照新鲜、无持仓、无活动订单、配置哈希匹配以及启动凭据可用；否则保持等待。
- runtime 必须回传 candidate/deployment/config 三个标识，SQLite 也按候选隔离，旧纸盘样本不能晋级新候选。
- 纸盘运行证据只接受 `*_paper_trade` 连接器。
- 实盘连接器混入或亏损越线单次立即熔断；普通运行故障连续三轮熔断。熔断为粘性状态，必须明确恢复并连续健康两轮。
- 每个策略失败不会阻止其他策略完成本轮。
- 状态原子写入，历史事件只追加。
- 状态损坏 fail-closed，不再静默重置为第一代。
- 自动实验采用不可变事务记录；无启动记录的 outcome、旧实验重放和内容不同的重复 outcome 都会被拒绝。
- 监督器重启时会协调遗留 in-flight：已有 outcome 时幂等提交，没有 outcome 时记录 `executor_interrupted`、清理租约并冷却后重试。
- PMM 纸盘启动采用 `staged → starting → runtime verification → active`；验证窗口内不会重复重启，runtime 缺失、损坏、不新鲜或配置哈希不一致时 fail-closed。
- 相同纸盘部署和相同 paper champion 的重复操作保持幂等，不覆盖真正的 previous champion。
- 每轮开始、完成、退避和停止均写结构化 heartbeat；长实验使用 running deadline，不再被普通新鲜度阈值误报。
- 策略内部异常写入独立错误事件和告警账本，并将监督器标记为 degraded。
- 持续模式使用 5 秒起步的指数退避和 jitter，守护日志按 5 MiB 自动轮转。
- macOS `Documents` 工作区使用带 `restart unless-stopped` 和容器 healthcheck 的 Docker 服务托管；不依赖受 TCC 限制的 launchd 进程。
- 生产守护使用固定基础镜像摘要和源码指纹镜像，不再挂载本机源码；运行身份写入 heartbeat 和部署清单。
- liveness、readiness、safety 三类健康状态分离：进程活着不再掩盖熔断或回滚阻塞，Docker healthcheck 使用 readiness。
- 容器以宿主非 root 用户运行，根文件系统只读，移除全部 capabilities，启用 no-new-privileges、PID/CPU/内存限制。
- 升级先保留旧容器，只有新容器通过源码指纹与活性校验才提交；支持一条命令回滚。
- 状态、候选运行快照和纸盘 SQLite 每 6 小时生成校验备份，默认保留 14 份；JSONL 账本按 25 MiB、5 代轮转。
- 告警始终写本地账本；配置 `STRATEGY_EVOLUTION_ALERT_WEBHOOK_URL` 后同步投递外部 webhook，投递结果不记录 URL。

## 永久边界

- 监督器没有实盘下单、实盘部署、密钥读取或资金操作代码。
- 小额灰度和实盘发布分别需要人工批准。
- 不允许通过提高仓位、杠杆、亏损线或并发数修复策略。
- 研究/回测数据不能覆盖运行快照与 SQLite 事实。
- 数据过期时不得输出健康或晋级结论。
- 无新证据时保持观察或暂停，不能靠重复报告制造进展。

## 使用

只读推进全部策略一轮：

```bash
python3 scripts/strategy_evolution_loop.py
```

只推进一个策略并运行确定性检查：

```bash
python3 scripts/strategy_evolution_loop.py --strategy pmm_mister --run-checks
```

智能选择并执行一项安全回测实验：

```bash
python3 scripts/strategy_evolution_loop.py --run-checks --auto-experiment
```

持续观察模式：

```bash
python3 scripts/strategy_evolution_loop.py --watch 300 --max-iterations 0
```

持续模式默认只重复证据采集和评估。带 `--auto-experiment` 时，每轮最多执行一个隔离回测。PMM 已支持参数级研究进化、版本化纸盘配置、纸盘预检和受控启动/回滚；策略代码变异、Funding 双腿模拟永续适配器、SuperTrend 永续空头模拟仍未自动化。

健康检查：

```bash
python3 scripts/check_strategy_evolution_health.py
python3 scripts/check_strategy_evolution_health.py --mode readiness
python3 scripts/check_strategy_evolution_health.py --mode safety
```

长期运行入口：

```bash
scripts/run_strategy_evolution_daemon.sh
```

当前 macOS `Documents` 工作区的推荐托管方式：

```bash
scripts/manage_strategy_evolution_container.sh install
scripts/manage_strategy_evolution_container.sh status
scripts/manage_strategy_evolution_container.sh logs
scripts/manage_strategy_evolution_container.sh backup
scripts/manage_strategy_evolution_container.sh rollback
```

容器基于锁定摘要构建不可变 Evolution 镜像，仅挂载运行数据、只读证据报告、生成配置目录和备份目录。容器运行时强制使用 `experiment_runtime=host`，避免嵌套 Docker；纸盘自动启动仍单独由 `STRATEGY_EVOLUTION_AUTO_START_PAPER=1` 控制，默认关闭。外部告警地址只通过运行环境传入，不写入仓库。

备份校验与隔离恢复演练：

```bash
python3 scripts/strategy_evolution_backup.py verify /path/to/archive.tar.gz
python3 scripts/strategy_evolution_backup.py restore /path/to/archive.tar.gz \
  --destination /tmp/evolution-restore-drill --confirm RESTORE
```

## 生产判定

Loop 的研究、回测、证据、候选发布清单和纸盘监督基础设施已达到可持续运行标准；它不等于策略已经可投入实盘。readiness 或 safety 非零时必须按生产事故处理，不能因为 liveness 正常而忽略。当前 PMM 的既有纸盘暴露仍使回滚处于阻塞状态，Funding 与 SuperTrend 也未通过各自策略门禁，因此系统会保持 degraded/unhealthy，禁止晋级。这是安全门禁生效，不是守护进程故障。

真正的实盘发布仍永久不在本 Loop 职责内，且必须另行完成策略纸盘时长/成交量、外部 webhook 地址配置、异机备份同步和人工审批。

`deploy/launchd/com.hummingbot.strategy-evolution.plist.example` 只适用于不受 macOS TCC 保护的工作目录。安装器会拒绝从 `~/Documents` 安装，防止形成每 30 秒失败一次的坏服务。不要把 `CONFIG_PASSWORD` 写进 plist 或容器定义；实盘批准始终由人工完成。

## 2026-07-13 实际闭环验证

- PMM 第一次自动实验因各 fold 参数不稳定被拒绝，失败证据已进入谱系。
- 改为固定候选配对样本外验证后，自动建立研究冠军 `pmm_mister-1f3cb6f6ac8e`：`spread=0.002`、`take_profit=0.003`、`refresh_seconds=120`。
- 该固定候选完成 3 个样本外 fold，盈利 fold 比例约 66.7%，费用调整后净收益约 2.27 quote，最大回撤约 0.69%；这些结果只证明当前数据窗口中的研究门禁通过，不代表未来盈利保证。
- 对应纸盘 controller/script 配置与发布清单已经生成。自动应用开关当前关闭；现有基线纸盘还有活动订单，因此候选保持 `waiting_for_valid_flat_runtime`，未重启纸盘容器。
- Funding 自动实验真实执行后遭遇外部接口 HTTP 429；系统将其分类为 `external_rate_limited` 并设置 15 分钟持久冷却，没有误判成策略失败。
- V2.1 守护容器真实完成 Funding 候选实验：6 个 fold 均无有效仓位，候选 `funding_rate_arb-5e959e809178` 被 `reject_challenger` 拒绝并写入负反馈谱系；下一次实验冷却 1 小时，未建立伪冠军。
- SuperTrend 的确定性编译检查已在 Docker 环境通过，但停止、撤单和平仓路径尚未证明，仍停留在 shadow。
- Evolution 单元、安全、恢复、健康和运维测试现为 32 项全部通过；生产容器源码指纹活性检查通过，重启次数为 0。readiness 会如实报告现有 PMM 回滚阻塞，不再显示伪 healthy。
