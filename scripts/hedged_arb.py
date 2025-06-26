import json
import os
import time

import ccxt
from web3 import Web3

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class HedgedRoosterArb(ScriptStrategyBase):
    # HB requires this attribute even if we don't use its native connectors
    markets: dict = {}

    # ──────────────────────────────────────────
    # Initialisation
    # ──────────────────────────────────────────
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger().info("=== INIT Hedged Rooster Arb ===")

        # ──  RPC  ──────────────────────────────
        self.w3 = Web3(Web3.HTTPProvider("https://rpc.plume.org"))
        self.logger().info(f"Plume RPC connected: {self.w3.is_connected()}")

        # ──  contracts & ABIs  ─────────────────
        script_dir = os.path.dirname(__file__)
        def load(name): return json.load(open(f"{script_dir}/abis/{name}.json"))

        self.router = self.w3.eth.contract(
            address = Web3.to_checksum_address("0x35e44dc4702Fd51744001E248B49CBf9fcc51f0C"),
            abi     = load("maverick_v2_router"),
        )
        self.logger().info(f"MaverickV2 router: {self.router.address}")
        self.pool_abi      = load("maverick_v2_pool")
        self.pool_lens_abi = load("maverick_v2_pool_lens")
        self.erc20_abi     = load("erc20")

        # hard-coded pool we care about
        self.pool_addr = Web3.to_checksum_address("0x39ba3C1Dbe665452E86fde9C71FC64C78aa2445C")
        self.logger().info(f"Pool address: {self.pool_addr}")

        # tokens (pUSD, wPLUME)
        self.token_a = Web3.to_checksum_address("0xdddD73F5Df1F0DC31373357beAC77545dC5A6f3F")  # pUSD
        self.token_b = Web3.to_checksum_address("0xEa237441c92CAe6FC17Caaf9a7acB3f953be4bd1")  # wPLUME
        self.logger().info(f"pUSD:   {self.token_a}")
        self.logger().info(f"wPLUME: {self.token_b}")

        # wallet + secrets via env
        self.wallet   = Web3.to_checksum_address(os.getenv("PLUME_WALLET"))
        self.priv_key = os.getenv("PLUME_PRIV")
        self.logger().info(f"Wallet: {self.wallet}")

        # Bybit (spot)
        self.bybit = ccxt.bybit({
            "apiKey": os.getenv("BYBIT_KEY"),
            "secret": os.getenv("BYBIT_SEC"),
        })
        self.logger().info("Bybit connector initialized")

        # strategy params
        self.fv_edge    = float(os.getenv("FV_EDGE", "0.0007"))  # 0.07%
        self.pool_edge  = float(os.getenv("POOL_EDGE", "0.0040"))  # 0.40%
        self.slice_size = int(os.getenv("SLICE_SIZE", "1000"))  # 1000 PLUME per leg

        self.logger().info(
            f"Params → fv_edge={self.fv_edge} pool_edge={self.pool_edge} "
            f"size={self.slice_size} PLUME"
        )
        self.logger().info("=== INIT complete ===")

    # ──────────────────────────────────────────
    # helper: approve once per session
    # ──────────────────────────────────────────
    def approve_if_needed(self, token_addr, amount, nonce):
        erc20 = self.w3.eth.contract(address=token_addr, abi=self.erc20_abi)
        decimals = self.get_decimals(token_addr)
        current = erc20.functions.allowance(self.wallet, self.router.address).call()
        # self.logger().info(f"Current allowance for {token_addr}: {current / 10**decimals}, needed: {amount / 10**decimals}")
        if current >= amount:
            # self.logger().info("Sufficient allowance, skipping approval.")
            return nonce  # already enough
        # self.logger().info(f"Sending approval for {token_addr} to router...")
        tx = erc20.functions.approve(self.router.address, 2**256 - 1).build_transaction({
            "from":  self.wallet,
            "nonce": nonce,
            "gas":   80_000,
        })
        signed = self.w3.eth.account.sign_transaction(tx, self.priv_key)
        txh = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        self.logger().info(f"Approve tx sent: 0x{txh.hex()}")
        self.w3.eth.wait_for_transaction_receipt(txh)
        self.logger().info("Approval confirmed.")
        return nonce + 1  # we consumed one nonce

    # ──────────────────────────────────────────
    # helper: execute Maverick swap
    # ──────────────────────────────────────────
    def execute_swap(self, token_in, amount_in, token0_in):
        nonce = self.w3.eth.get_transaction_count(self.wallet)
        nonce = self.approve_if_needed(token_in, amount_in, nonce)
        decimals = self.get_decimals(token_in)
        # self.logger().info(
        #     f"Building swap: token_in={token_in}, amount_in={amount_in / 10**decimals}, token0_in={token0_in}"
        # )
        tx = self.router.functions.exactInputSingle(
            self.wallet, self.pool_addr, token0_in, amount_in, 0
        ).build_transaction({
            "from":  self.wallet,
            "nonce": nonce,
            "gas":   300_000,
        })
        signed = self.w3.eth.account.sign_transaction(tx, self.priv_key)
        txh    = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        # self.logger().info(f"Swap tx sent: 0x{txh.hex()}")

        # ✅ ADD THIS: Wait for transaction confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(txh)
        if receipt.status == 1:
            self.logger().info(f"Swap 0x{txh.hex()} confirmed in block {receipt.blockNumber}")
        else:
            self.logger().error(f"Swap 0x{txh.hex()} transaction failed!")
            raise Exception("Swap transaction failed")

    # ──────────────────────────────────────────
    # helper: get decimals for a token
    # ──────────────────────────────────────────
    def get_decimals(self, token_addr):
        if token_addr == self.token_a:  # pUSD
            return 6
        elif token_addr == self.token_b:  # wPLUME
            return 18
        else:
            # fallback, or fetch from contract if needed
            return 18

    # ──────────────────────────────────────────
    # main tick
    # ──────────────────────────────────────────
    def on_tick(self):
        try:
            # Check wPLUME balance
            wplume_contract = self.w3.eth.contract(address=self.token_b, abi=self.erc20_abi)
            balance = wplume_contract.functions.balanceOf(self.wallet).call()
            pusd_contract = self.w3.eth.contract(address=self.token_a, abi=self.erc20_abi)
            pusd_balance = pusd_contract.functions.balanceOf(self.wallet).call()
            wplume_allowance = wplume_contract.functions.allowance(self.wallet, self.router.address).call()
            pusd_allowance = pusd_contract.functions.allowance(self.wallet, self.router.address).call()
            self.logger().info(f"\n \n \n \n********************************************************************************")
            self.logger().info(f"********************************************************************************")
            self.logger().info(f"start of tick: wPLUME balance = {balance / 10**18}, pUSD balance = {pusd_balance / 10**6}")
            self.logger().info(f"********************************************************************************")

            # 1️⃣  CEX fair-value
            ticker = self.bybit.fetch_ticker("PLUME/USDT")
            # self.logger().info(f"CEX ticker: {ticker}")
            fv_bid = ticker["bid"] * (1 - self.fv_edge)
            fv_ask = ticker["ask"] * (1 + self.fv_edge)
            self.logger().info(f"CEX adjusted: bid={fv_bid}, ask={fv_ask}")

            # 2️⃣  pool price
            lens = self.w3.eth.contract(
                address=Web3.to_checksum_address("0x15B4a8cc116313b50C19BCfcE4e5fc6EC8C65793"),
                abi=self.pool_lens_abi,
            )
            pool_price_raw = lens.functions.getPoolPrice(self.pool_addr).call()
            pool_price = pool_price_raw / 10**18
            self.logger().info(f"Pool price: {pool_price}")

            # 3️⃣  decision
            buy = fv_bid > pool_price * (1 + self.pool_edge)
            sell = fv_ask < pool_price * (1 - self.pool_edge)
            # if buy:
            #     self.logger().info(f"Buy Plume opportunity! Threshold: {pool_price * (1 + self.pool_edge)}")
            # if sell:
            #     self.logger().info(f"Sell Plume opportunity! Threshold: {pool_price * (1 - self.pool_edge)}")

            # 4️⃣  Execute trades if opportunities exist
            if buy:
                decimals = self.get_decimals(self.token_a)
                amount = int(self.slice_size * pool_price  * 10**decimals)
                self.logger().info(f"BUY pool (pUSD->wPLUME) / SELL CEX (PLUME/USDT), amount={self.slice_size * pool_price}")
                self.execute_swap(self.token_a, amount, True)  # ✅ FIXED: tokenAIn=True for pUSD->wPLUME
                self.logger().info("Placing CEX sell order...")
                try:
                    cex_order = self.bybit.create_order("PLUME/USDT", "market", "sell", self.slice_size)
                    # self.logger().info(f"CEX sell order placed: {cex_order}")
                except Exception as e:
                    self.logger().error(f"CEX sell order failed: {e}")
            elif sell:
                decimals = self.get_decimals(self.token_b)
                amount = int(self.slice_size * 10**decimals)
                self.logger().info(f"SELL pool (wPLUME->pUSD) / BUY CEX (PLUME/USDT), amount={self.slice_size}")
                self.execute_swap(self.token_b, amount, False)  # ✅ FIXED: tokenAIn=False for wPLUME->pUSD
                self.logger().info("Placing CEX buy order...")
                try:
                    cex_order = self.bybit.create_order("PLUME/USDT", "market", "buy", self.slice_size)
                    # self.logger().info(f"CEX buy order placed: {cex_order}")
                except Exception as e:
                    self.logger().error(f"CEX buy order failed: {e}")
            else:
                self.logger().info("No arbitrage opportunity found - monitoring...")

            # Check wPLUME balance
            wplume_contract = self.w3.eth.contract(address=self.token_b, abi=self.erc20_abi)
            balance = wplume_contract.functions.balanceOf(self.wallet).call()
            pusd_contract = self.w3.eth.contract(address=self.token_a, abi=self.erc20_abi)
            pusd_balance = pusd_contract.functions.balanceOf(self.wallet).call()
            self.logger().info(f"end of tick: wPLUME balance: {balance / 10**18}, pUSD balance: {pusd_balance / 10**6}")
            self.logger().info(f"********************************************************************************")
            self.logger().info(f"********************************************************************************")

        except Exception as e:
            self.logger().error(f"tick-error: {e}", exc_info=True)


# register
script_strategies = [HedgedRoosterArb]
