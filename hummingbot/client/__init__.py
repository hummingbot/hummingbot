import logging

import pandas as pd
import decimal


def format_decimal(n):
    """
    Convert the given float to a string without scientific notation
    """
    try:
        with decimal.localcontext() as ctx:
            ctx.prec = 7
            if isinstance(n, float):
                d = ctx.create_decimal(repr(n))
                return format(d.normalize(), 'f')
            elif isinstance(n, decimal.Decimal):
                return format(n.normalize(), 'f')
            else:
                return str(n)
    except Exception as e:
        logging.getLogger().error(str(e))


pd.options.display.float_format = lambda x: format_decimal(x)
