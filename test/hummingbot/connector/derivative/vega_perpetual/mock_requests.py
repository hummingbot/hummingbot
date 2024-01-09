from typing import Any, Dict


def _get_network_requests_rest_mock() -> Dict[str, Any]:
    return {
        "epoch": {
            "seq": "9919",
            "timestamps": {
                "startTime": "1697756583934387000",
                "expiryTime": "1697760183934387000",
                "endTime": "0",
                "firstBlock": "15247728",
                "lastBlock": "0"
            },
            "validators": []
        }
    }


def get_transaction_success_mock() -> Dict[str, Any]:
    succes = {
        "code": 0,
        "data": "string",
        "height": "string",
        "log": "string",
        "success": True,
        "txHash": "string"
    }
    return succes


def get_transaction_failure_mock() -> Dict[str, Any]:
    succes = {
        "code": 70,
        "data": "string",
        "height": "string",
        "log": "string",
        "success": False,
        "error": "error message",
        "txHash": "string"
    }
    return succes


def get_risk_factors_mock() -> Dict[str, Any]:
    risk_factors = {
        "riskFactor": {
            "market": "COIN_ALPHA_HBOT_MARKET_ID",
            "short": "0.0145750953816091",
            "long": "0.0143738469690337"
        }
    }
    return risk_factors


def _get_exchange_info_rest_mock() -> Dict[str, Any]:
    exchange_info_rest_response = {
        "markets": {
            "edges": [
                {
                    "node": {
                        "id": "COIN_ALPHA_HBOT_MARKET_ID",
                        "tradableInstrument": {
                            "instrument": {
                                "id": "",
                                "code": "COINALPHA.HBOT",
                                "name": "COINALPHA.HBOT Perpetual Futures",
                                "metadata": {
                                    "tags": [
                                        "base:COINALPHA",
                                        "quote:HBOT",
                                    ]
                                },
                                "perpetual": {
                                    "settlementAsset": "HBOT_ASSET_ID",
                                    "quoteName": "HBOT",
                                    "marginFundingFactor": "0.1",
                                    "dataSourceSpecForSettlementSchedule": {
                                        "id": "bdee9d4e593489bf9f39b3392fe7756ffd85c38a7b1c88057f5f07e16c37c45d",  # noqa: mock
                                        "createdAt": "0",
                                        "updatedAt": "0",
                                        "data": {
                                            "internal": {
                                                "timeTrigger": {
                                                    "conditions": [
                                                        {
                                                            "operator": "OPERATOR_GREATER_THAN",
                                                            "value": "0"
                                                        }
                                                    ],
                                                    "triggers": [
                                                        {
                                                            "initial": "1697228865",
                                                            "every": "300"
                                                        }
                                                    ]
                                                }
                                            }
                                        },
                                        "status": "STATUS_UNSPECIFIED"
                                    },
                                }
                            },
                        },
                        "decimalPlaces": "5",
                        "fees": {
                            "factors": {
                                "makerFee": "0.0002",
                                "infrastructureFee": "0.0005",
                                "liquidityFee": "0.0001"
                            }
                        },
                        "state": "STATE_ACTIVE",
                        "positionDecimalPlaces": "4",
                        "linearSlippageFactor": "0.01",
                    },
                },
                {
                    "node": {
                        "id": "COINBETA_HBOT_MARKET_ID",
                        "tradableInstrument": {
                            "instrument": {
                                "id": "",
                                "code": "COINBETA.HBOT",
                                "name": "COINBETA.HBOT Perpetual Futures",
                                "metadata": {
                                    "tags": [
                                        "base:COINBETA",
                                        "quote:HBOT",
                                    ]
                                },
                                "perpetual": {
                                    "settlementAsset": "HBOT_ASSET_ID",
                                    "quoteName": "USD",
                                    "marginFundingFactor": "0.1",
                                    "dataSourceSpecForSettlementSchedule": {
                                        "id": "HBOT",  # noqa: mock
                                        "createdAt": "0",
                                        "updatedAt": "0",
                                        "data": {
                                            "internal": {
                                                "timeTrigger": {
                                                    "conditions": [
                                                        {
                                                            "operator": "OPERATOR_GREATER_THAN",
                                                            "value": "0"
                                                        }
                                                    ],
                                                    "triggers": [
                                                        {
                                                            "initial": "1697228865",
                                                            "every": "300"
                                                        }
                                                    ]
                                                }
                                            }
                                        },
                                        "status": "STATUS_UNSPECIFIED"
                                    },
                                }
                            },
                        },
                        "decimalPlaces": "5",
                        "fees": {
                            "factors": {
                                "makerFee": "0.0002",
                                "infrastructureFee": "0.0005",
                                "liquidityFee": "0.0001"
                            }
                        },
                        "state": "STATE_ACTIVE",
                        "positionDecimalPlaces": "4",
                        "linearSlippageFactor": "0.01",
                    }
                },
                {
                    "node": {
                        "id": "IGNORED_COIN",
                        "tradableInstrument": {
                            "instrument": {
                                "id": "",
                                "code": "COINBETA.dd",
                                "name": "COINBETA.ddd Perpetual Futures",
                                "metadata": {
                                    "tags": [
                                        "base:ignore",
                                        "quote:HBOT",
                                    ]
                                },
                                "perpetual": {
                                    "settlementAsset": "HBOT_ASSET_ID",
                                    "quoteName": "USD",
                                    "marginFundingFactor": "0.1",
                                    "dataSourceSpecForSettlementSchedule": {
                                        "id": "bdee9d4e593489bf9f39b3392fe7756ffd85c38a7b1c88057f5f07e16c37c45d",  # noqa: mock
                                        "createdAt": "0",
                                        "updatedAt": "0",
                                        "data": {
                                            "internal": {
                                                "timeTrigger": {
                                                    "conditions": [
                                                        {
                                                            "operator": "OPERATOR_GREATER_THAN",
                                                            "value": "0"
                                                        }
                                                    ],
                                                    "triggers": [
                                                        {
                                                            "initial": "1697228865",
                                                            "every": "300"
                                                        }
                                                    ]
                                                }
                                            }
                                        },
                                        "status": "STATUS_UNSPECIFIED"
                                    },
                                }
                            },
                        },
                        "decimalPlaces": "5",
                        "fees": {
                            "factors": {
                                "makerFee": "0.0002",
                                "infrastructureFee": "0.0005",
                                "liquidityFee": "0.0001"
                            }
                        },
                        "state": "STATE_INACTIVE",
                        "positionDecimalPlaces": "4",
                    }
                },
                {
                    "node": {
                        "id": "FUTURE_COIN",
                        "tradableInstrument": {
                            "instrument": {
                                "id": "",
                                "code": "FUTURE_COIN.HBOT",
                                "name": "FUTURE_COIN.HBOT Futures",
                                "metadata": {
                                    "tags": [
                                        "base:FUTURE_COIN",
                                        "quote:HBOT",
                                    ]
                                },
                                "future": {
                                    "settlementAsset": "HBOT_ASSET_ID",
                                    "quoteName": "USD",
                                    "marginFundingFactor": "0.1",
                                    "dataSourceSpecForSettlementSchedule": {
                                        "id": "HBOT",  # noqa: mock
                                        "createdAt": "0",
                                        "updatedAt": "0",
                                        "data": {
                                            "internal": {
                                                "timeTrigger": {
                                                    "conditions": [
                                                        {
                                                            "operator": "OPERATOR_GREATER_THAN",
                                                            "value": "0"
                                                        }
                                                    ],
                                                    "triggers": [
                                                        {
                                                            "initial": "1697228865",
                                                            "every": "300"
                                                        }
                                                    ]
                                                }
                                            }
                                        },
                                        "status": "STATUS_UNSPECIFIED"
                                    },
                                }
                            },
                        },
                        "decimalPlaces": "5",
                        "fees": {
                            "factors": {
                                "makerFee": "0.0002",
                                "infrastructureFee": "0.0005",
                                "liquidityFee": "0.0001"
                            }
                        },
                        "state": "STATE_ACTIVE",
                        "positionDecimalPlaces": "4",
                    }
                },
                {
                    "node": {
                        "id": "IGNORED_COIN",
                        "tradableInstrument": {
                            "instrument": {
                                "id": "",
                                "code": "COINBETA.dd",
                                "name": "COINBETA.ddd Perpetual Futures",
                                "metadata": {
                                    "tags": [
                                        "base:ignore",
                                        "quote:HBOT",
                                    ]
                                },
                                "perpetual": {
                                    "settlementAsset": "HBOT_ASSET_ID",
                                    "quoteName": "USD",
                                    "marginFundingFactor": "0.1",
                                    "dataSourceSpecForSettlementSchedule": {
                                        "id": "bdee9d4e593489bf9f39b3392fe7756ffd85c38a7b1c88057f5f07e16c37c45d",  # noqa: mock
                                        "createdAt": "0",
                                        "updatedAt": "0",
                                        "data": {
                                            "internal": {
                                                "timeTrigger": {
                                                    "conditions": [
                                                        {
                                                            "operator": "OPERATOR_GREATER_THAN",
                                                            "value": "0"
                                                        }
                                                    ],
                                                    "triggers": [
                                                        {
                                                            "initial": "1697228865",
                                                            "every": "300"
                                                        }
                                                    ]
                                                }
                                            }
                                        },
                                        "status": "STATUS_UNSPECIFIED"
                                    },
                                }
                            },
                        },
                        "decimalPlaces": "5",
                        "fees": {
                            "factors": {
                                "makerFee": "0.0002",
                                "infrastructureFee": "0.0005",
                                "liquidityFee": "0.0001"
                            }
                        },
                        "state": "STATE_INACTIVE",
                        "positionDecimalPlaces": "4",
                    }
                },
                {
                    "node": {
                        "id": "FUTURE_COIN",
                        "tradableInstrument": {
                            "instrument": {
                                "id": "",
                                "code": "FUTURE_COIN.HBOT",
                                "name": "FUTURE_COIN.HBOT Futures",
                                "metadata": {
                                    "tags": [
                                        "base:FUTURE_COIN",
                                        "quote:HBOT",
                                    ]
                                },
                                "future": {
                                    "settlementAsset": "HBOT_ASSET_ID",
                                    "quoteName": "USD",
                                    "marginFundingFactor": "0.1",
                                    "dataSourceSpecForSettlementSchedule": {
                                        "id": "bdee9d4e593489bf9f39b3392fe7756ffd85c38a7b1c88057f5f07e16c37c45d",  # noqa: mock
                                        "createdAt": "0",
                                        "updatedAt": "0",
                                        "data": {
                                            "internal": {
                                                "timeTrigger": {
                                                    "conditions": [
                                                        {
                                                            "operator": "OPERATOR_GREATER_THAN",
                                                            "value": "0"
                                                        }
                                                    ],
                                                    "triggers": [
                                                        {
                                                            "initial": "1697228865",
                                                            "every": "300"
                                                        }
                                                    ]
                                                }
                                            }
                                        },
                                        "status": "STATUS_UNSPECIFIED"
                                    },
                                }
                            },
                        },
                        "decimalPlaces": "5",
                        "fees": {
                            "factors": {
                                "makerFee": "0.0002",
                                "infrastructureFee": "0.0005",
                                "liquidityFee": "0.0001"
                            }
                        },
                        "state": "STATE_ACTIVE",
                        "positionDecimalPlaces": "4",
                    }
                }
            ]

        }
    }
    return exchange_info_rest_response


def _get_exchange_symbols_rest_mock() -> Dict[str, Any]:
    exchange_symbols_response = {
        "assets": {
            "edges": [
                {
                    "node": {
                        "id": "HBOT_ASSET_ID",  # noqa: mock
                        "details": {
                            "name": "HBOT",
                            "symbol": "HBOT",
                            "decimals": "18",
                            "quantum": "1",
                        },
                        "status": "STATUS_ENABLED"
                    },
                },
                {
                    "node": {
                        "id": "COINALPHA_ASSET_ID",  # noqa: mock
                        "details": {
                            "name": "COINALPHA",
                            "symbol": "COINALPHA",
                            "decimals": "18",
                            "quantum": "1",
                        },
                        "status": "STATUS_ENABLED"
                    },
                },
                {
                    "node": {
                        "id": "COINBETA_ASSET_ID",  # noqa: mock
                        "details": {
                            "name": "CONBETA",
                            "symbol": "COINBETA",
                            "decimals": "18",
                            "quantum": "1",
                        },
                        "status": "STATUS_ENABLED"
                    },
                }
            ]
        }
    }
    return exchange_symbols_response


def _get_submit_transaction_rest_response_create_order_failure_mock() -> Dict[str, Any]:
    # TODO: Do we want more?? This is already exists...
    submit_raw_transaction_rest_response = {
        "code": 13,
        "message": "Internal error",
        "details": [
            {
                "@type": "type.googleapis.com/vega.ErrorDetail",
                "code": 10000,
                "message": "tx already exists in cache",
                "inner": ""
            }
        ]
    }
    return submit_raw_transaction_rest_response


def _get_user_trades_rest_mock() -> Dict[str, Any]:
    user_trades_rest_response = {
        "trades": {
            "edges": [
                {
                    "node": {
                        "id": "FAKE_EXCHANGE_ID",  # noqa: mock
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                        "price": "2816312999",
                        "size": "2363",
                        "buyer": "BUYER_ID",  # noqa: mock
                        "seller": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "aggressor": "SIDE_SELL",
                        "buyOrder": "FAKE_EXCHANGE_ID",  # noqa: mock
                        "sellOrder": "FAKE_EXCHANGE_ID",  # noqa: mock
                        "timestamp": "1697590811501334000",
                        "type": "TYPE_DEFAULT",
                        "buyerFee": {
                            "makerFee": "0",
                            "infrastructureFee": "0",
                            "liquidityFee": "0",
                            "makerFeeVolumeDiscount": "0",
                            "infrastructureFeeVolumeDiscount": "0",
                            "liquidityFeeVolumeDiscount": "0",
                            "makerFeeReferrerDiscount": "0",
                            "infrastructureFeeReferrerDiscount": "0",
                            "liquidityFeeReferrerDiscount": "0"
                        },
                        "sellerFee": {
                            "makerFee": "79860",
                            "infrastructureFee": "199649",
                            "liquidityFee": "39930",
                            "makerFeeVolumeDiscount": "53239",
                            "infrastructureFeeVolumeDiscount": "133099",
                            "liquidityFeeVolumeDiscount": "26620",
                            "makerFeeReferrerDiscount": "0",
                            "infrastructureFeeReferrerDiscount": "0",
                            "liquidityFeeReferrerDiscount": "0"
                        },
                        "buyerAuctionBatch": "0",
                        "sellerAuctionBatch": "0"
                    },
                    "cursor": "CURSOR"  # noqa: mock
                }
            ],
            "pageInfo": {
                "hasNextPage": True,
                "hasPreviousPage": False,
                "startCursor": "START_CURSOR",  # noqa: mock
                "endCursor": "END_CURSOR"  # noqa: mock
            }
        }
    }
    return user_trades_rest_response


def _get_user_orders_rest_mock() -> Dict[str, Any]:
    user_orders_rest_response = {
        "orders": {
            "edges": [
                {
                    "node": {
                        "id": "TEST_ORDER_ID",  # noqa: mock
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                        "partyId": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "side": "SIDE_BUY",
                        "price": "2709486559",
                        "size": "100",
                        "remaining": "0",
                        "timeInForce": "TIME_IN_FORCE_GTC",
                        "type": "TYPE_LIMIT",
                        "createdAt": "1697411392051611000",
                        "status": "STATUS_FILLED",
                        "expiresAt": "0",
                        "reference": "FAKE_CLIENT_ID",  # noqa: mock
                        "updatedAt": "1697411420685366000",
                        "version": "1",
                        "batchId": "1",
                        "peggedOrder": None,
                        "liquidityProvisionId": "",
                        "postOnly": False,
                        "reduceOnly": False
                    },
                    "cursor": "CURSOR"  # noqa: mock
                },
                {
                    "node": {
                        "id": "TEST_ORDER_ID_2",  # noqa: mock
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                        "partyId": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "side": "SIDE_SELL",
                        "price": "1000000",
                        "size": "1",
                        "remaining": "0",
                        "timeInForce": "TIME_IN_FORCE_GTC",
                        "type": "TYPE_LIMIT",
                        "createdAt": "1697411392051611000",
                        "status": "STATUS_FILLED",
                        "expiresAt": "0",
                        "reference": "FAKE_EXCHANGE_ID",  # noqa: mock
                        "updatedAt": "1697411420685366000",
                        "version": "1",
                        "batchId": "1",
                        "peggedOrder": None,
                        "liquidityProvisionId": "",
                        "postOnly": False,
                        "reduceOnly": False
                    },
                    "cursor": "CURSOR"  # noqa: mock
                },
            ],
            "pageInfo": {
                "hasNextPage": False,
                "hasPreviousPage": False,
                "startCursor": "START_CURSOR",  # noqa: mock
                "endCursor": "END_CURSOR"  # noqa: mock
            }
        }
    }
    return user_orders_rest_response


def _get_user_orders_with_code_rest_mock() -> Dict[str, Any]:
    user_orders_rest_response = {
        "code": 70,
        "orders": {
            "edges": [
                {
                    "node": {
                        "id": "TEST_ORDER_ID",  # noqa: mock
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                        "partyId": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "side": "SIDE_BUY",
                        "price": "2709486559",
                        "size": "100",
                        "remaining": "0",
                        "timeInForce": "TIME_IN_FORCE_GTC",
                        "type": "TYPE_LIMIT",
                        "createdAt": "1697411392051611000",
                        "status": "STATUS_FILLED",
                        "expiresAt": "0",
                        "reference": "FAKE_CLIENT_ID",  # noqa: mock
                        "updatedAt": "1697411420685366000",
                        "version": "1",
                        "batchId": "1",
                        "peggedOrder": None,
                        "liquidityProvisionId": "",
                        "postOnly": False,
                        "reduceOnly": False
                    },
                    "cursor": "CURSOR"  # noqa: mock
                },
                {
                    "node": {
                        "id": "TEST_ORDER_ID_2",  # noqa: mock
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                        "partyId": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "side": "SIDE_SELL",
                        "price": "1000000",
                        "size": "1",
                        "remaining": "0",
                        "timeInForce": "TIME_IN_FORCE_GTC",
                        "type": "TYPE_LIMIT",
                        "createdAt": "1697411392051611000",
                        "status": "STATUS_FILLED",
                        "expiresAt": "0",
                        "reference": "FAKE_EXCHANGE_ID",  # noqa: mock
                        "updatedAt": "1697411420685366000",
                        "version": "1",
                        "batchId": "1",
                        "peggedOrder": None,
                        "liquidityProvisionId": "",
                        "postOnly": False,
                        "reduceOnly": False
                    },
                    "cursor": "CURSOR"  # noqa: mock
                },
            ],
            "pageInfo": {
                "hasNextPage": False,
                "hasPreviousPage": False,
                "startCursor": "START_CURSOR",  # noqa: mock
                "endCursor": "END_CURSOR"  # noqa: mock
            }
        }
    }
    return user_orders_rest_response


def _get_user_balances_rest_mock() -> Dict[str, Any]:
    user_account_rest_response = {
        "accounts": {
            "edges": [
                {
                    "node": {
                        "owner": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "balance": "150000000",
                        "asset": "HBOT_ASSET_ID",  # noqa: mock
                        "marketId": "",
                        "type": "ACCOUNT_TYPE_GENERAL"
                    },
                    "cursor": "2"
                },
                {
                    "node": {
                        "owner": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "balance": "5000000000000000000000",
                        "asset": "COINALPHA_ASSET_ID",  # noqa: mock
                        "marketId": "",
                        "type": "ACCOUNT_TYPE_GENERAL"
                    },
                    "cursor": "eyJhY2NvdW50X2lkIjoiZTkyODZkOWEzOTU3MmUwZTg5ODM5ZDRmYWRlNmZhZjM3NzY3MDczNmU5YjUwMjQ2M2ZhYmM5MjVkM2JiNzViNiJ9"  # noqa: mock
                }
            ]
        }
    }
    return user_account_rest_response


def _get_user_positions_rest_mock() -> Dict[str, Any]:
    user_positions_rest_mock = {
        "positions": {
            "edges": [
                {
                    "node": {
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                        "partyId": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "openVolume": "-1000",
                        "realisedPnl": "-234350",
                        "unrealisedPnl": "-101633",
                        "averageEntryPrice": "2773175483",
                        "updatedAt": "1697457646450308000",
                        "lossSocialisationAmount": "0",
                        "positionStatus": "POSITION_STATUS_UNSPECIFIED"
                    },
                    "cursor": "CURSOR"  # noqa: mock
                }
            ],
            "pageInfo": {
                "hasNextPage": False,
                "hasPreviousPage": False,
                "startCursor": "START_CURSOR",  # noqa: mock
                "endCursor": "END_CURSOR"  # noqa: mock
            }
        }
    }
    return user_positions_rest_mock


def get_funding_periods() -> Dict[str, Any]:
    funding_periods = {
        "fundingPeriods": {
            "edges": [
                {
                    "node": {
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",
                        "seq": "1650",
                        "start": "1697725966000000000",
                        "end": "1697726266000000000",
                        "fundingPayment": "-4034088",
                        "fundingRate": "-0.0014109983417459",
                        "internalTwap": "2854996912",
                        "externalTwap": "2859031000"
                    },
                    "cursor": "CURSOR"
                },
            ],
            "pageInfo": {
                "hasNextPage": True,
                "hasPreviousPage": False,
                "startCursor": "START_CURSOR",
                "endCursor": "END_CURSOR"
            }
        }
    }
    return funding_periods


def _get_user_last_funding_payment_rest_mock() -> Dict[str, Any]:
    user_last_funding_payment_rest_response = {
        "fundingPayments": {
            "edges": [
                {
                    "node": {
                        "partyId": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",
                        "fundingPeriodSeq": "1650",
                        "timestamp": "1697724166111149000",
                        "amount": "4700780"
                    },
                    "cursor": "CURSOR"
                }
            ],
            "pageInfo": {
                "hasNextPage": False,
                "hasPreviousPage": False,
                "startCursor": "START_CURSOR",
                "endCursor": "END_CURSOR"
            }
        }
    }
    return user_last_funding_payment_rest_response


def _get_user_transaction_rest_mock() -> Dict[str, Any]:
    user_transaction_response = {
        "transaction": {
            "block": "14985156",
            "index": 4,
            "hash": "9BA8358800D4E4BDA7C6E30521452164B4F0F3F3F251C669118049B0CE89D560",  # noqa: mock
            "submitter": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
            "type": "Submit Order",
            "code": 0,
            "cursor": "14985156.4",
            "command": {
                "nonce": "8063173762",
                "blockHeight": "14985154",
                "orderSubmission": {
                    "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                    "price": "2816105938",
                    "size": "410",
                    "side": "SIDE_BUY",
                    "timeInForce": "TIME_IN_FORCE_GTC",
                    "expiresAt": "0",
                    "type": "TYPE_LIMIT",
                    "reference": "FAKE_CLIENT_ID",  # noqa: mock
                    "peggedOrder": None,
                    "postOnly": False,
                    "reduceOnly": False
                }
            },
            "signature": {
                "value": "SIGNATURE",  # noqa: mock
                "algo": "vega/ed25519",
                "version": 1
            }
        }
    }
    return user_transaction_response


def _get_user_transaction_failed_rest_mock() -> Dict[str, Any]:
    user_transaction_response = {
        "transaction": {
            "block": "14985156",
            "index": 4,
            "hash": "9BA8358800D4E4BDA7C6E30521452164B4F0F3F3F251C669118049B0CE89D560",  # noqa: mock
            "submitter": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
            "type": "Submit Order",
            "code": 70,
            "error": "failed to locate order",
            "cursor": "14985156.4",
            "command": {
                "nonce": "8063173762",
                "blockHeight": "14985154",
                "orderCancellation": {
                    "orderId": "FAKE_CLIENT_ID",  # noqa: mock
                    "marketId": "COIN_ALPHA_HBOT_MARKET_ID"
                }
            },
            "signature": {
                "value": "SIGNATURE",  # noqa: mock
                "algo": "vega/ed25519",
                "version": 1
            }
        }
    }
    return user_transaction_response


def _get_user_transactions_rest_mock() -> Dict[str, Any]:
    user_transactions_rest_response = {
        "transaction":
            {
                "block": "14985156",
                "index": 4,
                "hash": "9BA8358800D4E4BDA7C6E30521452164B4F0F3F3F251C669118049B0CE89D560",  # noqa: mock
                "submitter": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                "type": "Submit Order",
                "code": 0,
                "cursor": "14985156.4",
                "command": {
                    "nonce": "8063173762",
                    "blockHeight": "14985154",
                    "orderSubmission": {
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                        "price": "2816105938",
                        "size": "410",
                        "side": "SIDE_BUY",
                        "timeInForce": "TIME_IN_FORCE_GTC",
                        "expiresAt": "0",
                        "type": "TYPE_LIMIT",
                        "reference": "FAKE_CLIENT_ID",  # noqa: mock
                        "peggedOrder": None,
                        "postOnly": False,
                        "reduceOnly": False
                    }
                },
                "signature": {
                    "value": "SIGNATURE",  # noqa: mock
                    "algo": "vega/ed25519",
                    "version": 1
                }
            }
    }
    return user_transactions_rest_response


def _get_user_order_rest_mock() -> Dict[str, Any]:
    order_by_id_response = {
        "order": {
            "id": "ORDER_ID",  # noqa: mock
            "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
            "partyId": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
            "side": "SIDE_SELL",
            "price": "2862122881",
            "size": "1000",
            "remaining": "1000",
            "timeInForce": "TIME_IN_FORCE_GTC",
            "type": "TYPE_LIMIT",
            "createdAt": "1697737027853033000",
            "status": "STATUS_ACTIVE",
            "expiresAt": "0",
            "reference": "FAKE_CLIENT_ID",
            "updatedAt": "0",
            "version": "1",
            "batchId": "1",
            "peggedOrder": None,
            "liquidityProvisionId": "",
            "postOnly": False,
            "reduceOnly": False
        }
    }
    return order_by_id_response


def _get_order_by_id_rest_failure_mock() -> Dict[str, Any]:
    order_by_id_rest_failure_response = {
        "code": 5,
        "message": "Not Found",
        "details": []
    }

    return order_by_id_rest_failure_response


def _get_raw_signed_transaction() -> bytes:
    return "CocBCMjPgdQkEITWkgfKPnkKQDQ5NDE0MDBkNjBmNjFjNDhmZTFkMTRkNDMwN2FkMTExMWEyOWE5YmY4ZDBiYjU3OGIzODk1OGU2MDdmMmMyMWUSCjI4MTU5MjcwNzkY6AcgASgBOAFCIEJCUFRDNjA3ZWI1ZTg4ZTM5ZTU5OWRhM2U1YjBiZTNhEpMBCoABN2YxOTQ3NmYwNDk2MmM1OGY1MjE4ZWI3ZWUzNzkwOWViODkxMzRmYzE4MzcyODhlMzlhNzk5NzIzNmU4MWRlYzNlY2Q2NzIyNGUxZTBmZjliMmE2ZDlmZTk4OGRiNWUzN2Y3MGJjYmEwYzVhNzQ4MGIxMTVjZDc3Mzg3ZTA5MGISDHZlZ2EvZWQyNTUxORgB0j5AZjg4MmU5M2U2M2VhNjYyYjlkZGVlNmI2MWRlMTczNDVkNDQxYWRlMDY0NzU3ODg1NjFlNmQ0NzBiZWJjOWVjZYB9A8K7ASYKIDdkMTQzMDJmNDMyNTQ5NjVhNzllZjljYjBlMGEyOTU0EKSmAg==".encode("utf-8")  # noqa: mock


def _get_last_trade():
    last_trade = {
        "marketData":
            {
                "markPrice": "2904342",
                "bestBidPrice": "2904340",
                "bestBidVolume": "173",
                "bestOfferPrice": "2904342",
                "bestOfferVolume": "173",
                "bestStaticBidPrice": "2901437",
                "bestStaticBidVolume": "523",
                "bestStaticOfferPrice": "2907245",
                "bestStaticOfferVolume": "500",
                "midPrice": "2904341",
                "staticMidPrice": "2904341",
                "market": "COIN_ALPHA.HBOT",
                "timestamp": "1697220852016362000",
                "openInterest": "14787",
                "indicativePrice": "0",
                "marketTradingMode": 1,
                "targetStake": "477565219528200000000",
                "suppliedStake": "200500000000000000000000",

                "lastTradedPrice": "2904342",
            }
    }

    return last_trade
