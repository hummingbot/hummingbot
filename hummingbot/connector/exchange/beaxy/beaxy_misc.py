class BeaxyIOError(IOError):

    def __init__(self, msg, response, result, *args, **kwargs):
        self.response = response
        self.result = result
        super(BeaxyIOError, self).__init__(msg, *args, **kwargs)
