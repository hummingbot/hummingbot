import pandas as pd
import decimal

ctx = decimal.Context()
ctx.prec = 7


def float_to_str(f):
    """
    Convert the given float to a string without scientific notation
    """
    d1 = ctx.create_decimal(repr(f))
    return format(d1.normalize(), 'f')


pd.options.display.float_format = lambda x: float_to_str(x)
