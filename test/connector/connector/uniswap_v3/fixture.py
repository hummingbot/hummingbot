class Fixture:
    BALANCES = {"balances": {"ETH": 0.02, "ZRX": 20}}
    APPROVALS = {"approvals": {"ETH": 999999999, "ZRX": 999999999}}
    BUY_ORDER = {"txHash": "testing", "gasPrice": 1, "gasLimit": 1, "gasCost": 1}
    ADD_POSITION = {"tokenId": "0xHbotToTheMoon"}
    REMOVE_POSITION = {"success": True}
    ADJUST_LIQIDITY = {"success": True}
    POSITION = {"tokenId": "0xHbotToTheMoon", "token0": "HBOT", "token1": "ETH", "fee": 0.20,
                "tickLower": 10, "tickUpper": 20, "amount0": 100, "amount1": 200}
    COLLECT_FEES = {"tokenId": "0xHbotToTheMoon", "feeAmount": 10, "feeToken": "ETH"}
