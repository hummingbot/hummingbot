class OrderBook:
    def __init__(self):
        self._bids = []
        self._asks = []
    def apply_snapshot(self, bids, asks, uid):
        self._bids = sorted(bids, key=lambda x: -x[0])
        self._asks = sorted(asks, key=lambda x: x[0])
    def bid_entries(self):
        for p, s in self._bids: yield type('Entry', (), {'price': p, 'amount': s})
    def ask_entries(self):
        for p, s in self._asks: yield type('Entry', (), {'price': p, 'amount': s})
