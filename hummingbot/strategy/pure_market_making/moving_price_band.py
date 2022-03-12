from dataclasses import dataclass
from decimal import Decimal
import time


@dataclass
class MovingPriceBand:
    '''
    move price floor and ceiling to percentage of current price
    at every price_band_refresh_time
    '''
    enabled: bool
    price_floor_pct: Decimal
    price_ceiling_pct: Decimal
    price_band_refresh_time: float
    price_floor: Decimal = 0
    price_ceiling: Decimal = 0
    _set_time: float = 0

    @property
    def current_timestamp(self) -> float:
        '''get current timestamp'''
        return time.time()

    def update(self, price: Decimal) -> None:
        '''updates price_floor and price_ceiling based on price'''
        self.price_floor = (100 + self.price_floor_pct) / 100 * price
        self.price_ceiling = (100 + self.price_ceiling_pct) / 100 * price
        self._set_time = self.current_timestamp

    def check_and_update_price_band(self, price: Decimal) -> None:
        '''
        if price_band_refresh_time has passed,
        update the price_floor and price_ceiling
        '''
        if self.current_timestamp < self._set_time + self.price_band_refresh_time:
            return
        self.update(price)
