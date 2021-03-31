# A single source of truth for constant variables related to the exchange
import os

if os.environ.get('digifinex_test') == '1':
    host = 'openapi.digifinex.vip'
else:
    host = 'openapi.digifinex.com'

EXCHANGE_NAME = "digifinex"
REST_URL = f"https://{host}/v3"
WSS_PRIVATE_URL = f"wss://{host}/ws/v1/"
WSS_PUBLIC_URL = f"wss://{host}/ws/v1/"

API_REASONS = {
    0: "Success",
    10001: "Malformed request, (E.g. not using application/json for REST)",
    10002: "Not authenticated, or key/signature incorrect",
    10003: "IP address not whitelisted",
    10004: "Missing required fields",
    10005: "Disallowed based on user tier",
    10006: "Requests have exceeded rate limits",
    10007: "Nonce value differs by more than 30 seconds from server",
    10008: "Invalid method specified",
    10009: "Invalid date range",
    20001: "Duplicated record",
    20002: "Insufficient balance",
    30003: "Invalid instrument_name specified",
    30004: "Invalid side specified",
    30005: "Invalid type specified",
    30006: "Price is lower than the minimum",
    30007: "Price is higher than the maximum",
    30008: "Quantity is lower than the minimum",
    30009: "Quantity is higher than the maximum",
    30010: "Required argument is blank or missing",
    30013: "Too many decimal places for Price",
    30014: "Too many decimal places for Quantity",
    30016: "The notional amount is less than the minimum",
    30017: "The notional amount exceeds the maximum",
}
