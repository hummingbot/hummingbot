# BTCvp Market Maker Bot

基于 Hummingbot 框架思路，为 Pharos 链上的 BTCvp/USDC 池子提供做市服务。

## 功能

1. **Swap 做市** — 将 BTCvp 价格锚定 BTC（1:1），通过 swap 交易维持池内价格
2. **LP 流动性管理** — 同时提供 3 组流动性，每组 ±3% 区间，单边接近 20% 时自动 rebalance

## 配置

复制 `.env.example` 为 `.env`，填入私钥和参数。

## 运行

```bash
pip install -r requirements.txt
python -m btcvp_market_maker.main
```

## 架构

```
btcvp_market_maker/
├── config.py          # 配置加载
├── price_feed.py      # BTC 价格源 (vault.vishwalab.com)
├── dex_client.py      # Uniswap V2 链上交互 (FaroSwap)
├── swap_strategy.py   # Swap 做市策略 (价格锚定)
├── lp_strategy.py     # LP 流动性管理策略
├── main.py            # 主入口
└── abi/               # 合约 ABI
```
