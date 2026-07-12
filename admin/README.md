# Hummingbot AI 管理后台

这是 AI 行情路由与策略资产的只读运营面板。它读取仓库内真实的策略目录、迭代报告、代码版本状态和本机纸面容器状态，不提供实盘开仓入口。

## 本地启动

```bash
cd admin
npm ci
HUMMINGBOT_ROOT=.. npm run dev -- -H 127.0.0.1 -p 3217
```

访问 `http://127.0.0.1:3217/admin`。页面包括运营总览、策略资产库、AI 路由、风险中心和迭代中心。

## 容器启动

```bash
docker compose -f docker-compose.cloud.yml --profile admin up -d --build admin
```

管理后台只绑定 `127.0.0.1:3217`。如果需要通过公网域名访问，必须先在反向代理层增加身份认证和 TLS；不要直接暴露端口。

## 数据边界

- 策略目录：`reports/strategy_catalog.json`
- 核心策略证据：`reports/strategy_promotion_evidence.json`
- 核心策略晋级状态：`reports/strategy_promotion_state.json`
- 超级趋势滚动验证：`reports/supertrend_walk_forward_latest.json`
- 最近迭代快照：`reports/ai_strategy_router_iteration_latest.json`
- 运行态：本机 Docker、代码提交版本和工作区状态；容器部署时 Docker 状态会显示为未知，因为后台不会挂载 Docker 通信接口。
- 策略默认禁用，只有依次通过样本外回测、纸面运行和小额灰度的策略才能晋级。

更新证据后运行 `python3 scripts/strategy_promotion_report.py` 重新生成晋级状态。该命令只计算门禁，不会启动实盘。
