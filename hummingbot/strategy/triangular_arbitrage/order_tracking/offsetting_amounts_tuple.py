from decimal import Decimal


class OffsettingAmountsTuple:
    def __init__(self, buy_amount: Decimal = Decimal(0), sell_amount: Decimal = Decimal(0)):
        self.buys = buy_amount
        self.sells = sell_amount

    def __repr__(self):
        return f"buys={self.buys}, sells={self.sells}"
