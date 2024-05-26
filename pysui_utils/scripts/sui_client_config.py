# The underlying configuration class
import os

from pysui.abstracts.client_keypair import SignatureScheme
from pysui import SuiConfig, SyncClient
from dotenv import load_dotenv

load_dotenv()

network = "localnet"

# Option-1: Setup configuration with one or more known keystrings and optional web services.
cfg = SuiConfig.user_config(# Required
    rpc_url="http://0.0.0.0:44342" if network == "testnet" else "http://0.0.0.0:44340",
    #rpc_url="https://fullnode.testnet.sui.io:443",

    # Optional. First entry becomes the 'active-address'
    # List elemente must be a valid Sui base64 keystring (i.e. 'key_type_flag | private_key_seed' )
    # List can contain a dict for importing Wallet keys for example:
    # prv_keys=['AO.....',{'wallet_key': '0x.....', 'key_scheme': SignatureScheme.ED25519}]
    #   where
    #   wallet_key value is 66 char hex string
    #   key_scheme can be ED25519, SECP256K1 or SECP256R1
    prv_keys=[
        os.getenv("TESTNET_ADDR1_PRVKEY") if network == "testnet" else os.getenv("LOCALNET_ADDR1_PRVKEY"),
              # {'wallet_key': os.getenv("ADDR1_PRVKEY"), 'key_scheme': SignatureScheme.ED25519}
              ],

    # Optional, only needed for subscribing
    # ws_url="wss://fullnode.devnet.sui.io:443",
    )

# One address (and keypair), at least, should be created
# First becomes the 'active-address'
# _mnen, _address = cfg.create_new_keypair_and_address()

# Synchronous client
print(f"The address used is : {cfg.active_address}")
client = SyncClient(cfg)
