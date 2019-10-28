# initializes and maintains a websocket connection
from hummingbot.market.hitbtc.hitbtc_auth import HitbtcAuth

class hitbtc_data_source:

    def __init__(self):
        super().__init__()

    """
    Market data

    This Public market data are available without authentication.
    """
    def get_currency(self, currency_code):
        """Get Currency."""
        return self.session.get("%s/public/currency/%s" % (self.url, currency_code)).json()

    def get_symbol(self, symbol_code):
        """Get symbol."""
        return self.session.get("%s/public/symbol/%s" % (self.url, symbol_code)).json()

    def get_ticker(self, ticker_code):
        """Get Ticker."""
        return self.session.get("%s/public/ticker/%s" % (self.url, ticker_code)).json()

    def get_trades(self, trades_code):
        """Get trades."""
        return self.session.get("%s/public/trades/%s" % (self.url, trades_code)).json()

    def get_orderbook(self, order_code):
        """Get orderbook. """
        return self.session.get("%s/public/orderbook/%s" % (self.url, order_code)).json()

    def get_candles(self, candles_code):
        """Get candles."""
        return self.session.get("%s/public/candles/%s" % (self.url, candles_code)).json()

    """
    Trading

    ***Athentication Required***
    """

    def get_tradingBalance(self):
        """Get Trading Balance"""
        return self.session.get("%s/trading/balance" % (self.url)).json()
    
    def get_activeOrder(self):
        """Get Active Order"""
        return self.session.get("%s/order" % (self.url)).json()

    def get_activeOrderByClientOrderId(self, clientOrderId):
        """Get Active Order"""
        return self.session.get("%s/order/%s" % (self.url, clientOrderId)).json()
    
    def get_trading_fee(self, symbol_code):
        """Get Trading Fee"""
        return self.session.get("%s/trading/fee/%s" % (self.url, symbol_code)).json()
    
    """
    Trading History

    ***Athentication Required***
    """

    def get_orders_history(self, symbol_code):
        """Get Orders History"""
        return self.session.get("%s/history/order/%s" % (self.url, symbol_code)).json()
    
    def get_trades_history(self, symbol_code):
        """Get trades History"""
        return self.session.get("%s/history/trades/%s" % (self.url, symbol_code)).json()
    
    def get_trade_by_order(self, order_id):
        """Get trade by order"""
        return self.session.get("%s/history/order/%s/trades" % (self.url, order_id)).json()

    """
    Account management

    ***Athentication Required***
    """

    def get_account_balance(self):
        "Get Account Balance"
        return self.session.get("%s/account/balance" % (self.url)).json()
    
    def get_address(self, currency_code):
        """Get address for deposit."""
        return self.session.get("%s/account/crypto/address/%s" % (self.url, currency_code)).json()

    def checkAddress(self, address):
        """Check if crypto address belongs to current account"""
        return self.session.get("%s/account/crypto/is-mine/%s" % (self.url, address)).json()
        
    def get_transaction(self, transaction_id):
        """Get transaction info."""
        return self.session.get("%s/account/transactions/%s" % (self.url, transaction_id)).json()    

    




