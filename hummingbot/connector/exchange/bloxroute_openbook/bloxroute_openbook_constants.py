from bxsolana_trader_proto import Project

# TOKEN_PAIR_TO_WALLET_ADDR = {
#     "INV": "8U7VYzRnwLgKMXtp5bweXoDrzmQ1rF48a8qoD3rrc3uU",
#     "SOL": "BZYcWxuhyZqWYbo6UPEEnYzrXGCe7tjcRQvZzz7cxqhq",
#     "USDC": "HmvqBfBSRjNzjzKmjvefBe9NX9y2oSyiFLn77DwaH6v9",
#     "mSOL": "SX4fHc9uL9x8VU6Ag2X8GR22bXPTwDjAcWFu7BfH2qg",
#     "FIDA": "4aDUpyixMgbPzVcNdgxnw94chyoeMHe35W3dPCtXoY37",
#     "RAY": "4aDUpyixMgbPzVcNdgxnw94chyoeMHe35W3dPCtXoY37",
#     "WETH": "F2djfvy9ujH9mS4yf8zfHh1WHhGzNYJLxEKhEFbULgDv"
# }

TOKEN_PAIR_TO_WALLET_ADDR = {
    "SOL": "FFqDwRq8B4hhFKRqx7N1M6Dg6vU699hVqeynDeYJdPj5",
    "USDC": "Hse4dWHfnExzZ6mZkfNjs8BW45YZURHsWiHzssDMNjQ8",
    "FIDA": "5QCFjVEc7qBr9JyTJQkLjDCTgLGewpCjKo5uycNPhkGu",
    "RAY": "J5a6hwutTb6wvVrgUn1Fkx6YHaqWkSERfUwsv9xRsnLa",
    "PRT": "CRc5F7tAa584dj1ayTJzY4BTtG7kEMjY8NgMH57f9vsF",
}

EXCHANGE_NAME = "bloxroute_openbook"
OPENBOOK_PROJECT = Project.P_OPENBOOK

REST_URL = "https://virginia.solana.dex.blxrbdn.com"

DEFAULT_DOMAIN = ""
MAX_ORDER_ID_LEN = 32
HBOT_ORDER_ID_PREFIX = ""

MARKET_PATH = "/api/v1/market/markets"

RATE_LIMITS = []
