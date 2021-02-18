import aiohttp
from typing import List, Dict
from dataclasses import dataclass
from decimal import Decimal
from hummingbot.connector.exchange.binance.binance_utils import convert_from_exchange_trading_pair
from hummingbot.core.utils.async_utils import safe_gather

PARROT_MINER_BASE_URL = "https://papi-development.hummingbot.io/v1/mining_data/"

s_decimal_0 = Decimal("0")


@dataclass
class CampaignSummary:
    market_id: int = 0
    trading_pair: str = ""
    exchange_name: str = 0
    spread_max: Decimal = s_decimal_0
    payout_asset: str = ""
    liquidity: Decimal = s_decimal_0
    active_bots: int = 0
    reward_per_day: Decimal = s_decimal_0
    apy: Decimal = s_decimal_0


async def get_campaign_summary(exchange: str, trading_pairs: List[str] = []) -> Dict[str, CampaignSummary]:
    campaigns = await get_active_campaigns(exchange, trading_pairs)
    tasks = [get_market_snapshots(m_id) for m_id in campaigns]
    results = await safe_gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            raise result
        if result["items"]:
            snapshot = result["items"][0]
            market_id = int(snapshot["market_id"])
            campaign = campaigns[market_id]
            campaign.apy = Decimal(snapshot["annualized_return"]) / Decimal("100")
            reward = snapshot["payout_summary"]["open_volume"]["reward"]
            if campaign.payout_asset in reward["ask"]:
                campaign.reward_per_day = Decimal(str(reward["ask"][campaign.payout_asset]))
            if campaign.payout_asset in reward["bid"]:
                campaign.reward_per_day += Decimal(str(reward["bid"][campaign.payout_asset]))
            oov = snapshot["summary_stats"]["open_volume"]
            campaign.liquidity = Decimal(oov["oov_ask"]) + Decimal(oov["oov_bid"])
            campaign.active_bots = int(oov["bots"])
    return {c.trading_pair: c for c in campaigns.values()}


async def get_market_snapshots(market_id: int):
    async with aiohttp.ClientSession() as client:
        url = f"{PARROT_MINER_BASE_URL}market_snapshots/{market_id}?aggregate=1d"
        resp = await client.get(url)
        resp_json = await resp.json()
    return resp_json


async def get_active_campaigns(exchange: str, trading_pairs: List[str] = []) -> Dict[int, CampaignSummary]:
    campaigns = {}
    async with aiohttp.ClientSession() as client:
        url = f"{PARROT_MINER_BASE_URL}campaigns"
        resp = await client.get(url)
        resp_json = await resp.json()
    for campaign_retval in resp_json:
        for market in campaign_retval["markets"]:
            if market["exchange_name"] != exchange:
                continue
            t_pair = market["trading_pair"]
            if exchange == "binance":
                t_pair = convert_from_exchange_trading_pair(t_pair)
            if trading_pairs and t_pair not in trading_pairs:
                continue
            campaign = CampaignSummary()
            campaign.market_id = int(market["id"])
            campaign.trading_pair = t_pair
            campaign.exchange_name = market["exchange_name"]
            campaigns[campaign.market_id] = campaign
        for bounty_period in campaign_retval["bounty_periods"]:
            for payout_parameter in bounty_period["payout_parameters"]:
                market_id = int(payout_parameter["market_id"])
                if market_id in campaigns:
                    campaigns[market_id].spread_max = Decimal(str(payout_parameter["spread_max"])) / Decimal("100")
                    campaigns[market_id].payout_asset = payout_parameter["payout_asset"]
    return campaigns
