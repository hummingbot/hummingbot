# coding=utf-8


class TokocryptoAPIException(Exception):

    def __init__(self, response):
        self.code = 0
        try:
            json_res = response.json()
        except ValueError:
            self.message = 'Invalid JSON error message from Tokocrypto: {}'.format(response.text)
        else:
            self.code = json_res['code']
            self.message = json_res['msg']
        self.status_code = response.status_code
        self.response = response
        self.request = getattr(response, 'request', None)

    def __str__(self):  # pragma: no cover
        return 'APIError(code=%s): %s' % (self.code, self.message)


class TokocryptoRequestException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'TokocryptoRequestException: %s' % self.message


class TokocryptoOrderException(Exception):

    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return 'TokocryptoOrderException(code=%s): %s' % (self.code, self.message)


class TokocryptoOrderMinAmountException(TokocryptoOrderException):

    def __init__(self, value):
        message = "Amount must be a multiple of %s" % value
        super(TokocryptoOrderMinAmountException, self).__init__(-1013, message)


class TokocryptoOrderMinPriceException(TokocryptoOrderException):

    def __init__(self, value):
        message = "Price must be at least %s" % value
        super(TokocryptoOrderMinPriceException, self).__init__(-1013, message)


class TokocryptoOrderMinTotalException(TokocryptoOrderException):

    def __init__(self, value):
        message = "Total must be at least %s" % value
        super(TokocryptoOrderMinTotalException, self).__init__(-1013, message)


class TokocryptoOrderUnknownSymbolException(TokocryptoOrderException):

    def __init__(self, value):
        message = "Unknown symbol %s" % value
        super(TokocryptoOrderUnknownSymbolException, self).__init__(-1013, message)


class TokocryptoOrderInactiveSymbolException(TokocryptoOrderException):

    def __init__(self, value):
        message = "Attempting to trade an inactive symbol %s" % value
        super(TokocryptoOrderInactiveSymbolException, self).__init__(-1013, message)


class TokocryptoWithdrawException(Exception):
    def __init__(self, message):
        if message == u'参数异常':
            message = 'Withdraw to this address through the website first'
        self.message = message

    def __str__(self):
        return 'TokocryptoWithdrawException: %s' % self.message
