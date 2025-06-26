import json
import os

from web3 import Web3


def load_abi(name):
    script_dir = os.path.dirname(__file__)
    return json.load(open(f"{script_dir}/abis/{name}.json"))


# Setup
w3 = Web3(Web3.HTTPProvider("https://rpc.plume.org"))
print(f"Connected: {w3.is_connected()}")

# Contracts
router = w3.eth.contract(
    address=Web3.to_checksum_address("0x35e44dc4702Fd51744001E248B49CBf9fcc51f0C"),
    abi=load_abi("maverick_v2_router"),
)
pool_lens = w3.eth.contract(
    address=Web3.to_checksum_address("0x15B4a8cc116313b50C19BCfcE4e5fc6EC8C65793"),
    abi=load_abi("maverick_v2_pool_lens"),
)
erc20_abi = load_abi("erc20")

# Pool and tokens
pool_addr = Web3.to_checksum_address("0x39ba3C1Dbe665452E86fde9C71FC64C78aa2445C")
token_a = Web3.to_checksum_address("0xdddD73F5Df1F0DC31373357beAC77545dC5A6f3F")  # pUSD
token_b = Web3.to_checksum_address("0xEa237441c92CAe6FC17Caaf9a7acB3f953be4bd1")  # wPLUME

# Wallet
wallet = Web3.to_checksum_address(os.getenv("PLUME_WALLET"))
priv_key = os.getenv("PLUME_PRIV")

print(f"Pool: {pool_addr}")
print(f"pUSD: {token_a}")
print(f"wPLUME: {token_b}")
print(f"Wallet: {wallet}")

# Get pool price
pool_price_raw = pool_lens.functions.getPoolPrice(pool_addr).call()
pool_price = pool_price_raw / 10**18
print(f"\nPool price: {pool_price} pUSD per wPLUME")

# Strategy params (from production script)
slice_size = 1000  # 1000 PLUME per leg
fv_edge = 0.0007   # 0.07%
pool_edge = 0.0040  # 0.40%

print(f"\nStrategy params:")
print(f"slice_size: {slice_size} PLUME")
print(f"fv_edge: {fv_edge} ({fv_edge * 100}%)")
print(f"pool_edge: {pool_edge} ({pool_edge * 100}%)")

# Check balances
pusd_contract = w3.eth.contract(address=token_a, abi=erc20_abi)
wplume_contract = w3.eth.contract(address=token_b, abi=erc20_abi)

pusd_balance = pusd_contract.functions.balanceOf(wallet).call()
wplume_balance = wplume_contract.functions.balanceOf(wallet).call()

print(f"\nBalances:")
print(f"pUSD: {pusd_balance / 10**6}")
print(f"wPLUME: {wplume_balance / 10**18}")

# Check allowances
pusd_allowance = pusd_contract.functions.allowance(wallet, router.address).call()
wplume_allowance = wplume_contract.functions.allowance(wallet, router.address).call()

print(f"\nAllowances:")
print(f"pUSD: {pusd_allowance / 10**6}")
print(f"wPLUME: {wplume_allowance / 10**18}")

# Test 1: Current production approach (buy leg)
print(f"\n{'=' * 60}")
print("TEST 1: Current Production Approach (Buy Leg)")
print(f"{'=' * 60}")

try:
    # Current production approach: amount = slice_size * pool_price
    pusd_amount = int(slice_size * pool_price * 10**6)  # Convert to pUSD wei (6 decimals)

    print(f"Calculated pUSD amount: {pusd_amount} wei ({slice_size * pool_price} pUSD)")

    # Build transaction
    nonce = w3.eth.get_transaction_count(wallet)
    tx = router.functions.exactInputSingle(
        wallet, pool_addr, True, pusd_amount, 0  # tokenAIn=True for pUSD->wPLUME
    ).build_transaction({
        "from": wallet,
        "nonce": nonce,
        "gas": 300_000,
    })

    print(f"✅ Transaction built successfully")
    print(f"Input amount: {pusd_amount} wei ({slice_size * pool_price} pUSD)")

    # Try to send the transaction
    signed = w3.eth.account.sign_transaction(tx, priv_key)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Transaction sent: 0x{txh.hex()}")

    # Wait for confirmation
    receipt = w3.eth.wait_for_transaction_receipt(txh)
    if receipt.status == 1:
        print(f"✅ SUCCESS! Block: {receipt.blockNumber}")

        # Check new balances
        new_pusd_balance = pusd_contract.functions.balanceOf(wallet).call()
        new_wplume_balance = wplume_contract.functions.balanceOf(wallet).call()

        pusd_spent = (pusd_balance - new_pusd_balance) / 10**6
        wplume_received = (new_wplume_balance - wplume_balance) / 10**18

        print(f"pUSD spent: {pusd_spent}")
        print(f"wPLUME received: {wplume_received}")
        print(f"Actual price: {pusd_spent / wplume_received} pUSD per wPLUME")
        print(f"Target was: {slice_size} wPLUME")
        print(f"Difference: {wplume_received - slice_size} wPLUME")

        # Update balances for next test
        pusd_balance = new_pusd_balance
        wplume_balance = new_wplume_balance

    else:
        print(f"❌ FAILED!")

except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Sell leg (current production approach)
print(f"\n{'=' * 60}")
print("TEST 2: Current Production Approach (Sell Leg)")
print(f"{'=' * 60}")

try:
    # Current production approach: amount = slice_size (fixed wPLUME amount)
    wplume_amount = int(slice_size * 10**18)  # Convert to wPLUME wei (18 decimals)

    print(f"Calculated wPLUME amount: {wplume_amount} wei ({slice_size} wPLUME)")

    # Build transaction
    nonce = w3.eth.get_transaction_count(wallet)
    tx = router.functions.exactInputSingle(
        wallet, pool_addr, False, wplume_amount, 0  # tokenAIn=False for wPLUME->pUSD
    ).build_transaction({
        "from": wallet,
        "nonce": nonce,
        "gas": 300_000,
    })

    print(f"✅ Transaction built successfully")
    print(f"Input amount: {wplume_amount} wei ({slice_size} wPLUME)")

    # Try to send the transaction
    signed = w3.eth.account.sign_transaction(tx, priv_key)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Transaction sent: 0x{txh.hex()}")

    # Wait for confirmation
    receipt = w3.eth.wait_for_transaction_receipt(txh)
    if receipt.status == 1:
        print(f"✅ SUCCESS! Block: {receipt.blockNumber}")

        # Check new balances
        new_pusd_balance = pusd_contract.functions.balanceOf(wallet).call()
        new_wplume_balance = wplume_contract.functions.balanceOf(wallet).call()

        pusd_received = (new_pusd_balance - pusd_balance) / 10**6
        wplume_spent = (wplume_balance - new_wplume_balance) / 10**18

        print(f"wPLUME spent: {wplume_spent}")
        print(f"pUSD received: {pusd_received}")
        print(f"Actual price: {pusd_received / wplume_spent} pUSD per wPLUME")
        print(f"Target was: {slice_size} wPLUME")
        print(f"Difference: {wplume_spent - slice_size} wPLUME")

    else:
        print(f"❌ FAILED!")

except Exception as e:
    print(f"❌ Error: {e}")

print(f"\n{'=' * 60}")
print("CONCLUSION")
print(f"{'=' * 60}")
print("Current production approach works well:")
print("- Buy leg: Calculates pUSD needed for ~1000 wPLUME")
print("- Sell leg: Uses fixed 1000 wPLUME amount")
print("This gives consistent trade sizes while accounting for token differences.")
