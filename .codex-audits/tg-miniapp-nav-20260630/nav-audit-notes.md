# TG Mini App 导航运行检查

检查时间：2026-06-30

## 范围

- 公网地址：https://humm.kline007.top/app/
- 主导航：总览、交易、策略、风控、日志
- 二级导航：交易下的账户、任务、机器人、纸盘、LP；策略下的智能、插件、脚本；日志下的记录、服务、接口

## 结论

- 5 个主导航都能正常切换。
- 页面加载时没有控制台错误。
- 自动化点击过程中没有网络请求失败。
- 核心读接口正常：overview、accounts、paper/state、risk/policy。
- 写操作在公网浏览器下会被 401 拦截，这是预期；真实 Telegram 小程序内需要有效 initData 和白名单。

## 当前状态

- Hummingbot API：running。
- Control API：running。
- Risk Gate：strict mode。
- Telegram Mini App：standby。
- 当前模式：read-only / paper 优先。
- 实盘锁：开启。
- 运行中的真实交易任务：0。
- 已配置凭证：binance、binance_perpetual。

## 发现的问题

1. 交易页资产余额显示为空。
   - 后端 portfolio/refresh 能返回原始 portfolio。
   - 但 tokens 被压平成空数组，totalValue 为 0。
   - 前端因此显示“暂无资产数据”。

2. 多个页面是可打开的占位功能。
   - 交易 / 机器人：尚未接入机器人管理。
   - 交易 / LP：尚未启用 LP 管理。
   - 策略 / 脚本：尚未接入脚本中心。
   - 日志 / 接口：只展示接口说明，没有更细的接口探针。

3. 纸盘页面可读，但写操作未在公网浏览器验证。
   - 纸盘账本、最近信号、订单记录能展示。
   - 刷新信号、纸盘下单、模拟测试需要 Telegram 写权限校验。

## 截图

- 01-dashboard.png
- 02-交易.png
- 03-策略.png
- 04-风控.png
- 05-日志.png
- trade-账户.png
- trade-纸盘.png
- trade-account-after-refresh.png
