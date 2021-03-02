import aiohttp
import asyncio
from typing import List, Dict
from dataclasses import dataclass
from decimal import Decimal
import logging
from hummingbot.connector.exchange.binance.binance_utils import convert_from_exchange_trading_pair
from hummingbot.core.utils.async_utils import safe_gather

PARROT_MINER_BASE_URL = "https://papi.hummingbot.io/v1/mining_data/"

s_decimal_0 = Decimal("0")


@dataclass
class CampaignSummary:
    market_id: int = 0
    trading_pair: str = ""
    exchange_name: str = ""
    spread_max: Decimal = s_decimal_0
    payout_asset: str = ""
    liquidity: Decimal = s_decimal_0
    liquidity_usd: Decimal = s_decimal_0
    active_bots: int = 0
    reward_per_wk: Decimal = s_decimal_0
    apy: Decimal = s_decimal_0


async def get_campaign_summary(exchange: str, trading_pairs: List[str] = []) -> Dict[str, CampaignSummary]:
    results = {}
    try:
        campaigns = await get_active_campaigns(exchange, trading_pairs)
        tasks = [get_market_snapshots(m_id) for m_id in campaigns]
        snapshots = await safe_gather(*tasks, return_exceptions=True)
        for snapshot in snapshots:
            if isinstance(snapshot, Exception):
                raise snapshot
            if snapshot["items"]:
                snapshot = snapshot["items"][0]
                market_id = int(snapshot["market_id"])
                campaign = campaigns[market_id]
                campaign.apy = Decimal(snapshot["annualized_return"])
                oov = snapshot["summary_stats"]["open_volume"]
                campaign.liquidity = Decimal(oov["oov_eligible_ask"]) + Decimal(oov["oov_eligible_bid"])
                campaign.liquidity_usd = campaign.liquidity * Decimal(oov["base_asset_usd_rate"])
                campaign.active_bots = int(oov["bots"])
        results = {c.trading_pair: c for c in campaigns.values()}
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.getLogger(__name__).error("Unexpected error while requesting data from Hummingbot API.", exc_info=True)
    return results


async def get_market_snapshots(market_id: int):
    async with aiohttp.ClientSession() as client:
        url = f"{PARROT_MINER_BASE_URL}market_snapshots/{market_id}?aggregate=1m"
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
            # So far we have only 2 exchanges for mining Binance and Kucoin, Kucoin doesn't require conversion.
            # In the future we should create a general approach for this, e.g. move all convert trading pair fn to
            # utils.py and import the function dynamically in hummingbot/client/settings.py
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
            for payout in bounty_period["payout_parameters"]:
                market_id = int(payout["market_id"])
                if market_id in campaigns:
                    campaigns[market_id].reward_per_wk = Decimal(str(payout["bid_budget"])) + \
                        Decimal(str(payout["ask_budget"]))
                    campaigns[market_id].spread_max = Decimal(str(payout["spread_max"])) / Decimal("100")
                    campaigns[market_id].payout_asset = payout["payout_asset"]
    return campaigns
