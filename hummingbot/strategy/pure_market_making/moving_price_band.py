import logging
from dataclasses import dataclass
from decimal import Decimal

mpb_logger = None


@dataclass
class MovingPriceBand:
    '''
    move price floor and ceiling to percentage of current price
    at every price_band_refresh_time

    :param price_floor_pct: set the price floor pct
    :param price_ceiling_pct: reference price to set price band
    :param price_band_refresh_time: reference price to set price band
    '''
    price_floor_pct: Decimal = -1
    price_ceiling_pct: Decimal = 1
    price_band_refresh_time: float = 86400
    enabled: bool = False
    _price_floor: Decimal = 0
    _price_ceiling: Decimal = 0
    _set_time: float = 0

    @classmethod
    def logger(cls):
        global mpb_logger
        if mpb_logger is None:
            mpb_logger = logging.getLogger(__name__)
        return mpb_logger

    @property
    def price_floor(self) -> Decimal:
        '''get price floor'''
        return self._price_floor

    @property
    def price_ceiling(self) -> Decimal:
        '''get price ceiling'''
        return self._price_ceiling

    def update(self, timestamp: float, price: Decimal) -> None:
        """
        Updates the price band.

        :param timestamp: current timestamp of the strategy/connector
        :param price: reference price to set price band
        """
        self._price_floor = (Decimal("100") + self.price_floor_pct) / Decimal("100") * price
        self._price_ceiling = (Decimal("100") + self.price_ceiling_pct) / Decimal("100") * price
        self._set_time = timestamp
        self.logger().info(
            "moving price band updated: price_floor: %s price_ceiling: %s", self._price_floor, self._price_ceiling)

    def check_and_update_price_band(self, timestamp: float, price: Decimal) -> None:
        '''
        check if the timestamp has passed the defined refresh time before updating

        :param timestamp: current timestamp of the strategy/connector
        :param price: reference price to set price band
        '''
        if timestamp >= self._set_time + self.price_band_refresh_time:
            self.update(timestamp, price)

    def check_price_floor_exceeded(self, price: Decimal) -> bool:
        '''
        check if the price has exceeded the price floor

        :param price: price to check
        '''
        return price <= self.price_floor

    def check_price_ceiling_exceeded(self, price: Decimal) -> bool:
        '''
        check if the price has exceeded the price ceiling

        :param price: price to check
        '''
        return price >= self.price_ceiling

    def switch(self, value: bool) -> None:
        '''
        switch between enabled and disabled state

        :param value: set whether to enable or disable MovingPriceBand
        '''
        self.enabled = value
