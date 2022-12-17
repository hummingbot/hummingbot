import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional

from hummingbot.connector.exchange_base import ExchangeBase
from juno.connectors import Connector
from juno.models import SavingsProduct

_log = logging.getLogger(__name__)

_BALANCE_TIMEOUT = 10.0
_PRODUCT_TIMEOUT = 30 * 60.0

_SAVINGS_ASSET_PREFIX = "LD"


class SavingsCustodian:
    """
    On Binance, a flexible savings asset is indicated with an "LD"-prefix. It stands for "Lending Daily".
    """

    def __init__(self, connectors: Dict[str, Connector], hb_connectors: Dict[str, ExchangeBase]) -> None:
        self._connectors = connectors
        self._hb_connectors = hb_connectors

    def to_savings_asset(self, asset: str) -> str:
        return asset if asset.startswith(_SAVINGS_ASSET_PREFIX) else f"{_SAVINGS_ASSET_PREFIX}{asset}"

    def from_savings_asset(self, asset: str) -> str:
        return asset[2:] if asset.startswith(_SAVINGS_ASSET_PREFIX) else asset

    async def acquire(self, connector_name: str, asset: str, amount: Decimal) -> None:
        _log.info(f"Redeeming {amount} worth of {asset} flexible savings product.")

        product = await asyncio.wait_for(
            self._wait_for_product_status_purchasing(connector_name, asset),
            timeout=_PRODUCT_TIMEOUT,
        )
        if product is None:
            _log.info(f"{asset} savings product not available; skipping.")
            return

        savings_asset = self.to_savings_asset(asset)
        savings_amount = self._hb_connectors[connector_name].get_available_balance(savings_asset)
        if savings_amount == 0:
            _log.info("Nothing to redeem; savings balance 0.")
            return

        await self._connectors[connector_name].redeem_savings_product(product.product_id, savings_amount)
        await asyncio.wait_for(
            self._wait_for_wallet_updated_with(connector_name, asset, savings_amount), timeout=_BALANCE_TIMEOUT
        )

        _log.info(f"Redeemed {savings_amount} worth of {asset} flexible savings product.")

    async def release(self, connector_name: str, asset: str, amount: Decimal) -> None:
        _log.info(f"Purchasing {amount} worth of {asset} flexible savings product.")

        product = await asyncio.wait_for(
            self._wait_for_product_status_purchasing(connector_name, asset),
            timeout=_PRODUCT_TIMEOUT,
        )
        if product is None:
            _log.info(f"{asset} savings product not available; skipping.")
            return

        savings_amount = amount

        global_available_product = product.limit - product.purchased_amount
        if amount > global_available_product:
            _log.info(f"Only {global_available_product} available globally.")
            savings_amount = global_available_product

        if amount > product.limit_per_user:
            _log.info(f"Only {product.limit_per_user} available per user.")
            savings_amount = product.limit_per_user

        if savings_amount < product.min_purchase_amount:
            _log.info(f"{savings_amount} less than minimum purchase amount {product.min_purchase_amount}; skipping.")
            return

        await self._connectors[connector_name].purchase_savings_product(product.product_id, savings_amount)
        await asyncio.wait_for(
            self._wait_for_wallet_updated_with(connector_name, self.to_savings_asset(asset), savings_amount),
            timeout=_BALANCE_TIMEOUT,
        )

        _log.info(f"Purchased {savings_amount} worth of {asset} flexible savings product.")

    async def _wait_for_wallet_updated_with(self, connector_name: str, asset: str, amount: Decimal) -> None:
        while True:
            # TODO: Ideally we listened to websocket updates instead of polling the wallet.
            available_amount = self._hb_connectors[connector_name].get_available_balance(asset)
            if available_amount >= amount:
                return
            await asyncio.sleep(100)

    async def _wait_for_product_status_purchasing(self, connector_name: str, asset: str) -> Optional[SavingsProduct]:
        # A product can be in status "PURCHASING" or "PREHEATING". "PURCHASING" is when the product
        # is available. "PREHEATING" means the product is being processed. This happens usually at
        # 23:50 - 00:10 UTC.
        # https://dev.binance.vision/t/failure-to-fast-redeem-a-flexible-savings-product-right-after-midnight-00-00-utc/5785
        while True:
            products = await self._connectors[connector_name].map_savings_products(asset=asset)

            product = products.get(asset)
            if product is None:
                return None

            if product.status == "PREHEATING":
                _log.info(f"{asset} savings product is preheating; waiting a minute before retrying.")
                await asyncio.sleep(60.0)
            elif product.status == "PURCHASING":
                return product
            else:
                raise Exception(f"Unknown {asset} savings product status {product.status}.")
