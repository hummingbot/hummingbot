import re
from decimal import Decimal

POLL_INTERVAL = 1.0
UPDATE_BALANCE_INTERVAL = 30.0
FUNDING_FEE_POLL_INTERVAL = 120

APPROVAL_ORDER_ID_PATTERN = re.compile(r"approve-(\w+)-(\w+)")
ONE_LAMPORT = Decimal('1e-9')
FIVE_THOUSAND_LAMPORTS = 5000 * ONE_LAMPORT
ONE = 1
ZERO = 0
SOL_USDC_MARKET = 'SOL/USDC'

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
DECIMAL_NaN = Decimal("nan")
DECIMAL_INFINITY = Decimal("infinity")
