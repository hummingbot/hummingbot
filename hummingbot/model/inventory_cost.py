from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Session

from hummingbot.model import HummingbotBase


class InventoryCost(HummingbotBase):
    __tablename__ = "InventoryCost"
    __table_args__ = (
        UniqueConstraint("base_asset", "quote_asset"),
    )

    id = Column(Integer, primary_key=True, nullable=False)
    base_asset = Column(String(45), nullable=False)
    quote_asset = Column(String(45), nullable=False)
    base_volume = Column(Numeric(48, 18), nullable=False)
    quote_volume = Column(Numeric(48, 18), nullable=False)

    @classmethod
    def get_record(
        cls, sql_session: Session, base_asset: str, quote_asset: str
    ) -> Optional["InventoryCost"]:
        return (
            sql_session.query(cls)
            .filter(cls.base_asset == base_asset, cls.quote_asset == quote_asset)
            .first()
        )

    @classmethod
    def add_volume(
        cls,
        sql_session: Session,
        base_asset: str,
        quote_asset: str,
        base_volume: Decimal,
        quote_volume: Decimal,
        overwrite: bool = False,
    ) -> None:
        if overwrite:
            update = {
                "base_volume": base_volume,
                "quote_volume": quote_volume,
            }
        else:
            update = {
                "base_volume": cls.base_volume + base_volume,
                "quote_volume": cls.quote_volume + quote_volume,
            }

        rows_updated: int = sql_session.query(cls).filter(
            cls.base_asset == base_asset, cls.quote_asset == quote_asset
        ).update(update)

        if not rows_updated:
            record = InventoryCost(
                base_asset=base_asset,
                quote_asset=quote_asset,
                base_volume=float(base_volume),
                quote_volume=float(quote_volume),
            )
            sql_session.add(record)
