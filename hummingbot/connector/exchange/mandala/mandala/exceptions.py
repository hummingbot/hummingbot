# coding=utf-8


class MandalaAPIException(Exception):

    def __init__(self, response):
        self.code = 0
        try:
            json_res = response.json()
        except ValueError:
            self.message = 'Invalid JSON error message from Mandala: {}'.format(response.text)
        else:
            self.code = json_res['code']
            self.message = json_res['msg']
        self.status_code = response.status_code
        self.response = response
        self.request = getattr(response, 'request', None)

    def __str__(self):  # pragma: no cover
        return 'APIError(code=%s): %s' % (self.code, self.message)


class MandalaRequestException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'MandalaRequestException: %s' % self.message


class MandalaOrderException(Exception):

    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return 'MandalaOrderException(code=%s): %s' % (self.code, self.message)


class MandalaOrderMinAmountException(MandalaOrderException):

    def __init__(self, value):
        message = "Amount must be a multiple of %s" % value
        super(MandalaOrderMinAmountException, self).__init__(-1013, message)


class MandalaOrderMinPriceException(MandalaOrderException):

    def __init__(self, value):
        message = "Price must be at least %s" % value
        super(MandalaOrderMinPriceException, self).__init__(-1013, message)


class MandalaOrderMinTotalException(MandalaOrderException):

    def __init__(self, value):
        message = "Total must be at least %s" % value
        super(MandalaOrderMinTotalException, self).__init__(-1013, message)


class MandalaOrderUnknownSymbolException(MandalaOrderException):

    def __init__(self, value):
        message = "Unknown symbol %s" % value
        super(MandalaOrderUnknownSymbolException, self).__init__(-1013, message)


class MandalaOrderInactiveSymbolException(MandalaOrderException):

    def __init__(self, value):
        message = "Attempting to trade an inactive symbol %s" % value
        super(MandalaOrderInactiveSymbolException, self).__init__(-1013, message)


class MandalaWithdrawException(Exception):
    def __init__(self, message):
        if message == u'参数异常':
            message = 'Withdraw to this address through the website first'
        self.message = message

    def __str__(self):
        return 'MandalaWithdrawException: %s' % self.message
