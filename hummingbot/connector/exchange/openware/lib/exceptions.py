# coding=utf-8


class OpenwareAPIException(Exception):

    def __init__(self, response):
        self.code = 0
        try:
            json_res = response.json()
        except ValueError:
            self.message = 'Invalid JSON error message from Openware: {}'.format(response.text)
        else:
            self.message = response
        #     self.code = json_res['code']
        #     self.message = json_res['msg']
        self.status_code = response.status_code
        self.response = response
        self.request = getattr(response, 'request', None)

    def __str__(self):  # pragma: no cover
        return 'APIError(code=%s): %s' % (self.code, self.message)


class OpenwareRequestException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'OpenwareRequestException: %s' % self.message


class OpenwareOrderException(Exception):

    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return 'OpenwareOrderException(code=%s): %s' % (self.code, self.message)


class OpenwareOrderMinAmountException(OpenwareOrderException):

    def __init__(self, value):
        message = "Amount must be a multiple of %s" % value
        super(OpenwareOrderMinAmountException, self).__init__(-1013, message)


class OpenwareOrderMinPriceException(OpenwareOrderException):

    def __init__(self, value):
        message = "Price must be at least %s" % value
        super(OpenwareOrderMinPriceException, self).__init__(-1013, message)


class OpenwareOrderMinTotalException(OpenwareOrderException):

    def __init__(self, value):
        message = "Total must be at least %s" % value
        super(OpenwareOrderMinTotalException, self).__init__(-1013, message)


class OpenwareOrderUnknownSymbolException(OpenwareOrderException):

    def __init__(self, value):
        message = "Unknown symbol %s" % value
        super(OpenwareOrderUnknownSymbolException, self).__init__(-1013, message)


class OpenwareOrderInactiveSymbolException(OpenwareOrderException):

    def __init__(self, value):
        message = "Attempting to trade an inactive symbol %s" % value
        super(OpenwareOrderInactiveSymbolException, self).__init__(-1013, message)


class OpenwareWithdrawException(Exception):
    def __init__(self, message):
        if message == u'参数异常':
            message = 'Withdraw to this address through the website first'
        self.message = message

    def __str__(self):
        return 'OpenwareWithdrawException: %s' % self.message
