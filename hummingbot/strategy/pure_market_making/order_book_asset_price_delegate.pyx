
cdef class OrderBookAssetPriceDelegate(AssetPriceDelegate):
    def __init__(self):
        super().__init__()

    cdef object c_get_mid_price(self):
        # cdef:
        #     MarketBase maker_market = market_info.market

        return 0
