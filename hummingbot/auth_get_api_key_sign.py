import time

import requests
from eth_account import Account as EthAccount
from eth_account.messages import encode_typed_data

VERIFYING_CONTRACT_PROD = "0x919386306C47b2Fe1036e3B4F7C40D22D2461a23"

PRIMARY_PRIVATE_KEY = ()

primary_account = EthAccount.from_key(PRIMARY_PRIVATE_KEY)
primary_address = primary_account.address

signing_privkey = SIGNING_PRIVKEY
signing_address = EthAccount.from_key(signing_privkey).address

expiry = int(time.time() * 1000) + 7 * 24 * 3600 * 1000  # 7 дней вперёд

domain = {
    "name": "VestRouterV2",
    "version": "0.0.1",
    "verifyingContract": VERIFYING_CONTRACT_PROD,
}
types = {
    "SignerProof": [
        {"name": "approvedSigner", "type": "address"},
        {"name": "signerExpiry", "type": "uint256"},
    ],
}
message = {
    "approvedSigner": signing_address,
    "signerExpiry": expiry,
}

proof_msg = encode_typed_data(domain, types, message)
signature = EthAccount.sign_message(proof_msg, PRIMARY_PRIVATE_KEY).signature.hex()

body = {
    "signingAddr": signing_address.lower(),
    "primaryAddr": primary_address.lower(),
    "signature": signature,
    "expiryTime": expiry,
    "networkType": 0,  # уточни, если у тебя другое значение
}

resp = requests.post(
    "https://server-prod.hz.vestmarkets.com/v2/register",
    json=body,
    timeout=10,
)

print("status:", resp.status_code)
print("response:", resp.json())
