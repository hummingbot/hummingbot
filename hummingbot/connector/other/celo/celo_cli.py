import subprocess
from subprocess import CalledProcessError
from decimal import Decimal
from typing import List, Optional, Dict
from hummingbot.connector.other.celo.celo_data_types import CeloExchangeRate, CeloBalance


UNIT_MULTIPLIER = Decimal(1e18)
CELO_BASE = "CELO"
CELO_QUOTE = "CUSD"
CELOCLI_CELO = "CELO"
CELOCLI_CUSD = "cUSD"
CELOCLI_LOCKED_CELO = "lockedCELO"


def command(commands: List[str]) -> Optional[str]:
    try:
        output = subprocess.check_output(commands, stderr=subprocess.STDOUT, shell=False)
        output = output.decode("utf-8").strip()

        # ignore lines with "libusb".
        output = "\n".join([line for line in output.split("\n") if "libusb" not in line])

        if output == "":
            output = None
        return output
    except CalledProcessError as e:
        raise Exception(error_msg_from_output(e.output))


def error_msg_from_output(output):
    lines = output.decode("utf-8").split("\n")
    err_lines = [line for line in lines if "Error" in line]
    if len(err_lines) > 0:
        err_msg = err_lines[0].replace("Error:", "").strip()
    else:
        err_msg = lines[0]
    return err_msg


class CeloCLI:
    unlocked = False
    address = None

    @classmethod
    def unlock_account(cls, address: str, password: str) -> Optional[str]:
        try:
            cls.address = address
            command(["celocli", "account:unlock", address, "--password", password])
            cls.unlocked = True
            return None
        except Exception as e:
            cls.unlocked = False
            return str(e)

    @classmethod
    def balances(cls) -> Dict[str, CeloBalance]:
        balances = {}
        output = command(["celocli", "account:balance", cls.address])
        lines = output.split("\n")
        raw_balances = {}
        data_type = [CELOCLI_CELO, CELOCLI_LOCKED_CELO, CELOCLI_CUSD, "pending"]
        for line in lines:
            if ":" in line and any(key in line for key in data_type):
                asset, value = line.split(":")
                raw_balances[asset.strip()] = Decimal(value) / UNIT_MULTIPLIER
        balances[CELO_BASE] = CeloBalance(CELO_BASE, raw_balances[CELOCLI_CELO], raw_balances[CELOCLI_LOCKED_CELO])
        balances[CELO_QUOTE] = CeloBalance(CELO_QUOTE, raw_balances[CELOCLI_CUSD], Decimal("0"))
        return balances

    @classmethod
    def exchange_rate(cls, amount: Decimal = Decimal("1")) -> List[CeloExchangeRate]:
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
            from_amount = Decimal(from_amount) / UNIT_MULTIPLIER
            to_amount = Decimal(to_amount) / UNIT_MULTIPLIER
            rates.append(CeloExchangeRate(from_token.upper(), from_amount,
                                          to_token.upper(), to_amount))
        return rates

    @classmethod
    def buy_cgld(cls, cusd_value: Decimal, min_cgld_returned: Decimal = None):
        cusd_value *= UNIT_MULTIPLIER
        args = ["celocli", "exchange:dollars", "--from", cls.address, "--value", str(int(cusd_value))]
        if min_cgld_returned is not None:
            min_cgld_returned *= UNIT_MULTIPLIER
            args += ["--forAtLeast", str(int(min_cgld_returned))]
        output = command(args)
        return cls._tx_hash_from_exchange_output(output)

    @classmethod
    def sell_cgld(cls, cgld_value: Decimal, min_cusd_returned: Decimal = None):
        cgld_value *= UNIT_MULTIPLIER
        args = ["celocli", "exchange:gold", "--from", cls.address, "--value", str(int(cgld_value))]
        if min_cusd_returned is not None:
            min_cusd_returned *= UNIT_MULTIPLIER
            args += ["--forAtLeast", str(int(min_cusd_returned))]
        output = command(args)
        return cls._tx_hash_from_exchange_output(output)

    @classmethod
    def _tx_hash_from_exchange_output(cls, output_msg):
        lines = output_msg.split("\n")
        tx_hash = ([line for line in lines if "txHash" in line][-1]).split(":")[-1].strip()
        return tx_hash

    @classmethod
    def validate_node_synced(cls) -> Optional[str]:
        output = command(["celocli", "node:synced"])
        lines = output.split("\n")
        if "true" not in [line.strip().lower() for line in lines]:
            return lines[0]
