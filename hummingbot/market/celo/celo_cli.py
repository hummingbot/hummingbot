import subprocess
from subprocess import CalledProcessError
from decimal import Decimal
from typing import List


symbols_map = {"CGLD": "gold", "CUSD": "usd"}


def command(commands: List[str]):
    try:
        output = subprocess.check_output(commands, stderr=subprocess.STDOUT, shell=False)
        output = output.decode("utf-8").strip()
        if output == "":
            output = None
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
    def balances(cls):
        balances = {}
        output = command(["celocli", "account:balance", cls.address])
        lines = output.split("\n")
        for line in lines:
            if ":" not in line:
                continue
            asset, value = line.split(":")
            symbols = [k for k, v in symbols_map.items() if v.lower() == asset.lower().strip()]
            if symbols:
                balances[symbols[0]] = Decimal(value) / Decimal(10e18)
        return balances
