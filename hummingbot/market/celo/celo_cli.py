import subprocess
from subprocess import CalledProcessError
from decimal import Decimal
from typing import List, Optional, Dict
from collections import namedtuple


CeloExchangeRate = namedtuple("CeloExchangeRate", "from_token from_amount to_token to_amount")
UNIT_MULTIPLIER = Decimal(1e18)
CELO_BASE = "CGLD"
CELO_QUOTE = "CUSD"
SYMBOLS_MAP = {CELO_BASE: "gold", CELO_QUOTE: "usd"}


def command(commands: List[str]) -> Optional[str]:
    try:
        output = subprocess.check_output(commands, stderr=subprocess.STDOUT, shell=False)
        output = output.decode("utf-8").strip()
        if output == "":
            output = None
        print(f"command: {commands}")
        print(f"output: {output}")
        return output
    except CalledProcessError as e:
        raise Exception(e.output.decode("utf-8").split("\n")[0])


class CeloCLI:
    UNLOCK_ERR_MSG = "Error: unlock_account has not been tried."
    address = None
    password = None
    unlocked_msg = UNLOCK_ERR_MSG

    @classmethod
    def set_account(cls, address, password):
        cls.address = address
        cls.password = password

    @classmethod
    def remove_account(cls):
        cls.address = None
        cls.password = None
        cls.unlocked_msg = cls.UNLOCK_ERR_MSG

    @classmethod
    def unlock_account(cls):
        try:
            output = command(["celocli", "account:unlock", cls.address, "--password", cls.password])
        except Exception as e:
            output = str(e)
        cls.unlocked_msg = output

    @classmethod
    def balances(cls) -> Dict[str, Decimal]:
        balances = {}
        output = command(["celocli", "account:balance", cls.address])
        lines = output.split("\n")
        for line in lines:
            if ":" not in line:
                continue
            asset, value = line.split(":")
            symbols = [k for k, v in SYMBOLS_MAP.items() if v.lower() == asset.lower().strip()]
            if symbols:
                balances[symbols[0]] = Decimal(value) / UNIT_MULTIPLIER
        return balances

    @classmethod
    def exchange_rate(cls, amount: Decimal) -> List[CeloExchangeRate]:
        amount *= UNIT_MULTIPLIER
        output = command(["celocli", "exchange:show", "--amount", str(int(amount))])
        lines = output.split("\n")
        rates = []
        for line in lines:
            if "=>" not in line:
                continue
            from_asset, to_asset = line.split("=>")
            from_amount, from_token = from_asset.strip().split(" ")
            to_amount, to_token = to_asset.strip().split(" ")
            rates.append(CeloExchangeRate(from_token.upper(), Decimal(from_amount),
                                          to_token.upper(), Decimal(to_amount)))
        return rates

    @classmethod
    def buy_cgld(cls, cusd_value: Decimal):
        cusd_value *= UNIT_MULTIPLIER
        output = command(["celocli", "exchange:dollars", "--from", cls.address, "--value", str(int(cusd_value))])
        return output

    @classmethod
    def sell_cgld(cls, cgld_value: Decimal):
        cgld_value *= UNIT_MULTIPLIER
        output = command(["celocli", "exchange:gold", "--from", cls.address, "--value", str(int(cgld_value))])
        return output
