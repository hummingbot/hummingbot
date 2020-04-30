import subprocess
from subprocess import CalledProcessError
from decimal import Decimal


class CeloCli:
    address = None
    password = None
    unlocked_msg = "Error: unlock_account has not been tried."

    @classmethod
    def set_account(cls, address, password):
        cls.address = address
        cls.password = password

    @classmethod
    def unlock_account(cls):
        try:
            output = subprocess.check_output(f"celocli account:unlock {cls.address} --password={cls.password}",
                                             stderr=subprocess.STDOUT, shell=True)
            output = output.decode("utf-8")
            if output.strip() == "":
                output = None
        except CalledProcessError as e:
            output = e.output.decode("utf-8").split("\n")[0]
        cls.unlocked_msg = output

    @classmethod
    def balances(cls):
        balances = {"gold": Decimal("0"), "usd": Decimal("0")}
        output = subprocess.check_output(f"celocli account:balance {cls.address}",
                                         stderr=subprocess.STDOUT, shell=True)
        lines = output.decode("utf-8").strip().split("\n")
        for line in lines:
            matches = [token for token in balances if token in line]
            if matches:
                token = matches[0]
                amount_str = line.split(":")[-1]
                amount = Decimal(amount_str) / Decimal(10e18)
                balances[token] = amount
        return balances
