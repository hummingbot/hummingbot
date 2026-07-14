# Hummingbot AI 管理后台

这是 AI 行情路由与策略资产的运营面板。它读取仓库内真实的 Routing、Evolution、策略目录、交易账本、代码版本和本机纸盘容器状态；提供纸盘路由重算、受控 Worker 启停和人工纸盘余额模拟划转，但不提供实盘开仓、实盘划转或密钥编辑入口。

## 本地启动

```bash
cd admin
npm ci
HUMMINGBOT_ROOT=.. npm run dev -- -H 127.0.0.1 -p 3217
```

访问 `http://127.0.0.1:3217/admin`。页面包括运营总览、策略路由编排、策略资产库、风险中心、交易账本和迭代中心。路由编排页每 5 秒读取一次聚合状态，展示主/子账户配置、资金分配、兼容矩阵、Worker 与 Docker 双重事实、Evolution 发布冲突、生命周期和审计流水。

## 容器启动

```bash
docker compose -f docker-compose.cloud.yml --profile admin up -d --build admin strategy-router
```

管理后台只绑定 `127.0.0.1:3217`。如果需要通过公网域名访问，必须先在反向代理层增加身份认证和 TLS；不要直接暴露端口。

同一 `admin` profile 会启动 `hummingbot-strategy-router` 守护容器。它每半个路由周期动态读取当前 `active_verified` / `paper_champion` 发布和候选运行快照，更新路由决策与心跳。默认 `STRATEGY_ROUTER_APPLY_WORKERS=0`，所以守护进程只维护纸盘计划，不会自动启停或切换 Worker；执行动作仍需显式操作和密码门禁。

交易账本页可控制唯一配置的纸盘 Worker `hummingbot-pmm-mister-paper`：启动、停止，或“新建观察期”。接口会同步 `data/strategy-routing/workers.json`，并按当前 Evolution 发布清单定位候选数据库与运行快照；发布状态不是 `active_verified` 或 `paper_champion` 时拒绝启动和新建观察期。归档不会删除历史文件，也不会控制任何实盘容器。该能力通过本机 Docker socket 实现，因此后台只能保持回环地址并受反向代理认证保护。

策略路由编排页还提供三项纸盘操作：

- “纸盘资金与风险限制”只允许编辑账户的资金、回撤、敞口、委托数和行情过期阈值；保存前校验完整配置，并原子写入被 Git 忽略、单独可写挂载的 `conf/runtime/strategy_router_accounts.yml`。账户拓扑、凭据和权限不可从 UI 修改。
- “按最新快照重算”只生成新的路由计划，不会应用 Worker 启停；Evolution 发布不可路由时失败关闭。
- “人工纸盘模拟划转”复用 Python 域模型的白名单、保留资金、单笔/日限额、冷却期、人工审批和幂等账本校验；只写 `data/strategy-routing/paper-balances.json` 与 `transfers.jsonl`，不会调用交易所 API。

## 局域网部署目标

局域网 Mac 的部署信息在 `.deploy.lan.env.example`：`allenxing00@192.168.102.7:22`。远端 `/Users/allenxing00/Documents/soft/hummingbot` 是 Humm Control Plane，不是本仓库的官方执行引擎；执行引擎部署到独立目录 `/Users/allenxing00/Documents/soft/hummingbot-engine`，不会覆盖控制台。该主机已验证 SSH 密钥/Agent 登录，Docker Desktop 与 Docker Compose 也已就绪；不需要、也不应保存 SSH 密码。

首次部署只同步无凭据的执行引擎源码并启动回环地址上的后台：

```bash
bash scripts/deploy-lan-hummingbot.sh deploy
```

局域网直接访问时，将 `LAN_ADMIN_BIND_HOST` 设为 M2 的固定局域网 IP `192.168.102.7`，然后访问 `http://192.168.102.7:3217/admin`。不要设为 `0.0.0.0`：后台具备固定纸盘容器的启停能力，只应开放给受信任的局域网。部署会保留 Hummingbot 的加密密码校验文件，以便纸盘容器验证配置密码；不会同步交易所连接器、日志或任何 API 密钥。历史账本只在首次迁移时同步，之后 M2 是唯一写入端。

## 币安纸盘实例

纸盘高级纯做市使用 `binance_paper_trade`，可以用下面的方式启动或重启：

```bash
CONFIG_PASSWORD='远端新配置密码' \
HUMMINGBOT_DOCKER_CONFIG="$PWD/.docker" \
HUMMINGBOT_DOCKER_NETWORK=bridge \
HUMMINGBOT_DISABLE_PROXY=true \
bash scripts/run_pmm_mister_paper.sh
```

脚本只会启动 `hummingbot-pmm-mister-paper` 这个纸盘容器，并保持交易记录写入本仓库的 `data/`。如果本机代理监听在 `127.0.0.1`，脚本会自动转换为 Docker Desktop 可访问的 `host.docker.internal`；也可显式设置 `HUMMINGBOT_CONTAINER_PROXY`。若该代理无法与币安完成 TLS 握手，可设置 `HUMMINGBOT_DISABLE_PROXY=true` 走直连。不设置任何实盘连接器或 API 密钥。

### 币安手续费与返佣

纸盘成本按“币安实际费率 − 40% 返佣”计算。启动脚本会运行 `scripts/sync_binance_fee_profile.py`：没有账户查询权限时，明确使用标准 `10 bps` 毛费率、返佣后 `6 bps` 净费率作为兜底，并在交易账本标注“待账户同步”。

要同步账户的实际 Maker/Taker 费率，请在**启动命令的环境变量**中提供仅有 `USER_DATA` 权限、不开启交易权限的币安 API 凭据：

```bash
BINANCE_FEE_API_KEY='只读密钥' \
BINANCE_FEE_API_SECRET='只读密钥密文' \
CONFIG_PASSWORD='你的本地配置密码' \
bash scripts/run_pmm_mister_paper.sh
```

同步只请求 Binance 的账户接口，不会下单或撤单；程序只提取并持久化佣金字段，不会持久化账户余额。结果写入 `data/binance_fee_profile.json`，并在下一次纸盘启动时应用；不要把凭据写入仓库或 `conf/`。

## 数据边界

- 策略目录：`reports/strategy_catalog.json`
- 核心策略证据：`reports/strategy_promotion_evidence.json`
- 核心策略晋级状态：`reports/strategy_promotion_state.json`
- 超级趋势滚动验证：`reports/supertrend_walk_forward_latest.json`
- 高级纯做市滚动验证：`reports/pmm_mister_walk_forward_latest.json`
- 资金费率套利滚动验证：`reports/funding_arb_walk_forward_latest.json`
- 最近迭代快照：`reports/ai_strategy_router_iteration_latest.json`
- 交易账本：`data/*.sqlite` 中的历史委托与成交，以及运行中 V2 实例每 5 秒写入的 `data/*_runtime.json`（余额、活动委托、当前持仓）
- 手续费口径：`data/binance_fee_profile.json` 保存币安费率来源、毛费率、40% 返佣和净费率；`conf/conf_fee_overrides.yml` 保存纸盘启动时实际生效的净费率。
- 运行态：后台读取 Docker、代码提交版本和工作区状态。局域网部署的后台为固定纸盘容器控制而挂载 Docker socket，因此只绑定 M2 的指定局域网 IP，不使用全网卡暴露；代码目录仍保持只读挂载。运行快照在 30 秒内会作为纸盘存活心跳，并明确标示该运行依据。
- 策略默认禁用，只有依次通过样本外回测、纸面运行和小额灰度的策略才能晋级。

交易记录仍是只读账本，不提供下单、撤单或真实资金划转。运行快照和 Routing 聚合接口不包含 API 密钥或凭据引用；如果实例未启动或跨系统状态冲突，页面会明确标示，不会把历史数据或单一状态源伪装成当前健康状态。

更新证据后运行 `python3 scripts/strategy_promotion_report.py` 重新生成晋级状态。该命令只计算门禁，不会启动实盘。
