from decimal import Decimal


class SpotCustodian:
    def to_savings_asset(self, asset: str) -> str:
        return asset

    def from_savings_asset(self, asset: str) -> str:
        return asset

    async def acquire(self, connector_name: str, asset: str, amount: Decimal) -> None:
        pass

    async def release(self, connector_name: str, asset: str, amount: Decimal) -> None:
        pass
