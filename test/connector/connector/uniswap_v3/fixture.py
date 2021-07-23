class Fixture:
    BALANCES = {"balances": {"ETH": 0.02, "ZRX": 20}}
    APPROVALS = {"approvals": {"ETH": 999999999, "ZRX": 999999999}}
    BUY_ORDER = {"txHash": "testing", "gasPrice": 1, "gasLimit": 1, "gasCost": 1}
    ADD_POSITION = {"txHash": "0xHbotToTheMoon", "gasPrice": 100000000}
    REMOVE_POSITION = {"txHash": "OxRemoved"}
    POSITION = {"tokenId": "0xHbotToTheMoon", "token0": "HBOT", "token1": "ETH", "fee": 0.20,
                "tickLower": 10, "tickUpper": 20, "amount0": 100, "amount1": 200}
    COLLECT_FEES = {"tokenId": "0xHbotToTheMoon", "feeAmount": 10, "feeToken": "ETH"}

    ETH_POLL_LP_ORDER = {
        "network": "kovan",
        "timestamp": 1620448579518,
        "latency": 3.907,
        "txHash": "0x6d2c4f6dca5403beec707931ff837a03dcb33fcd266fbb570e63da8020540c3c",
        "confirmed": True,
        "receipt": {
            "gasUsed": 291200,
            "blockNumber": 24726262,
            "confirmations": 191,
            "status": 1,
            "logs": [
                {
                    "transactionIndex": 6,
                    "blockNumber": 24726262,
                    "transactionHash": "0x6d2c4f6dca5403beec707931ff837a03dcb33fcd266fbb570e63da8020540c3c",
                    "address": "0x2F375e94FC336Cdec2Dc0cCB5277FE59CBf1cAe5",
                    "topics": [
                        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                        "0x0000000000000000000000002132ef54bfab1c2c7323eacda407c5cfa7d7af20",
                        "0x000000000000000000000000c4f8d1035e729e6b8645539d54e380bfd455ada5"
                    ],
                    "data": "0x00000000000000000000000000000000000000000000000000000000002dc5f6",
                    "logIndex": 11,
                    "blockHash": "0xc8f6c753876291a2e2237415acbc86b503a820a7600b976c6dc382bf593007cf"
                },
                {
                    "transactionIndex": 6,
                    "blockNumber": 24726262,
                    "transactionHash": "0x6d2c4f6dca5403beec707931ff837a03dcb33fcd266fbb570e63da8020540c3c",
                    "address": "0xC4f8D1035E729e6b8645539D54e380bfd455ada5",
                    "topics": [
                        "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde",
                        "0x000000000000000000000000c36442b4a4522e871399cd717abdd847ab11fe88",
                        "0x0000000000000000000000000000000000000000000000000000000000002ac6",
                        "0x0000000000000000000000000000000000000000000000000000000000002ada"
                    ],
                    "data": "0x000000000000000000000000c36442b4a4522e871399cd717abdd847ab11fe8800000000000000000000000000000000000000000000000000000000675fce41000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002dc5f6",
                    "logIndex": 12,
                    "blockHash": "0xc8f6c753876291a2e2237415acbc86b503a820a7600b976c6dc382bf593007cf"
                },
                {
                    "transactionIndex": 6,
                    "blockNumber": 24726262,
                    "transactionHash": "0x6d2c4f6dca5403beec707931ff837a03dcb33fcd266fbb570e63da8020540c3c",
                    "address": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
                    "topics": [
                        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                        "0x0000000000000000000000000000000000000000000000000000000000000000",
                        "0x0000000000000000000000002132ef54bfab1c2c7323eacda407c5cfa7d7af20",
                        "0x0000000000000000000000000000000000000000000000000000000000000099"
                    ],
                    "data": "0x",
                    "logIndex": 13,
                    "blockHash": "0xc8f6c753876291a2e2237415acbc86b503a820a7600b976c6dc382bf593007cf"
                },
                {
                    "transactionIndex": 6,
                    "blockNumber": 24726262,
                    "transactionHash": "0x6d2c4f6dca5403beec707931ff837a03dcb33fcd266fbb570e63da8020540c3c",
                    "address": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
                    "topics": [
                        "0x3067048beee31b25b2f1681f88dac838c8bba36af25bfb2b7cf7473a5847e35f",
                        "0x0000000000000000000000000000000000000000000000000000000000000099"
                    ],
                    "data": "0x00000000000000000000000000000000000000000000000000000000675fce41000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002dc5f6",
                    "logIndex": 14,
                    "blockHash": "0xc8f6c753876291a2e2237415acbc86b503a820a7600b976c6dc382bf593007cf"
                }
            ]
        }
    }

    ETH_RESULT_LP_ORDER = {
        "network": "kovan", "timestamp": 1620403261458, "latency": 0.002, "info": [
            {"name": "Transfer",
             "events": [{"name": "from", "type": "address", "value": "0xefb7be8631d154d4c0ad8676fec0897b2894fe8f"},
                        {"name": "to", "type": "address", "value": "0xc4f8d1035e729e6b8645539d54e380bfd455ada5"},
                        {"name": "tokenId", "type": "uint256", "value": "0"}],
             "address": "0x1528F3FCc26d13F7079325Fb78D9442607781c8C"
             },
            {"name": "Transfer", "events": [
                {"name": "from", "type": "address", "value": "0x0000000000000000000000000000000000000000"},
                {"name": "to", "type": "address", "value": "0xefb7be8631d154d4c0ad8676fec0897b2894fe8f"},
                {"name": "tokenId", "type": "uint256", "value": "123"}],
             "address": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"},
            {"name": "IncreaseLiquidity", "events": [{"name": "tokenId", "type": "uint256", "value": "123"},
                                                     {"name": "liquidity", "type": "uint128",
                                                      "value": "1039715250499808709332"},
                                                     {"name": "amount0", "type": "uint256", "value": "100"},
                                                     {"name": "amount1", "type": "uint256", "value": "200"}],
             "address": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"}]
    }

    ETH_RESULT_LP_ORDER_REMOVE = {
        "network": "kovan", "timestamp": 1620403261458, "latency": 0.002, "info": [
            {"name": "Transfer",
             "events": [{"name": "from", "type": "address", "value": "0xefb7be8631d154d4c0ad8676fec0897b2894fe8f"},
                        {"name": "to", "type": "address", "value": "0xc4f8d1035e729e6b8645539d54e380bfd455ada5"},
                        {"name": "tokenId", "type": "uint256", "value": "0"}],
             "address": "0x1528F3FCc26d13F7079325Fb78D9442607781c8C"
             },
            {"name": "Transfer", "events": [
                {"name": "from", "type": "address", "value": "0x0000000000000000000000000000000000000000"},
                {"name": "to", "type": "address", "value": "0xefb7be8631d154d4c0ad8676fec0897b2894fe8f"},
                {"name": "tokenId", "type": "uint256", "value": "123"}],
             "address": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"},
            {"name": "DecreaseLiquidity", "events": [{"name": "tokenId", "type": "uint256", "value": "123"},
                                                     {"name": "liquidity", "type": "uint128",
                                                      "value": "1039715250499808709332"},
                                                     {"name": "amount0", "type": "uint256", "value": "200"},
                                                     {"name": "amount1", "type": "uint256", "value": "0"}],
             "address": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"}]
    }
