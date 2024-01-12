from typing import Any, Dict


def _get_order_book_diff_mock() -> Dict[str, Any]:
    order_book_diff_message = {
        "result": {
            "update": [
                {
                    "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                    "sell": [
                        {
                            "price": "2817447085"
                        },
                        {
                            "price": "2817547085"
                        },
                        {
                            "price": "2817647085"
                        },
                        {
                            "price": "2817747085",
                            "numberOfOrders": "1",
                            "volume": "833"
                        }
                    ],
                    "sequenceNumber": "1697590646276860086",
                    "previousSequenceNumber": "1697590619714643056"
                }
            ]
        }
    }
    return order_book_diff_message


def _get_order_book_snapshot_mock() -> Dict[str, Any]:
    order_book_snapshot_message = {
        "result": {
            "marketDepth": [
                {
                    "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                    "buy": [
                        {
                            "price": "2816912999",
                            "numberOfOrders": "1",
                            "volume": "330"
                        },
                        {
                            "price": "2816812999",
                            "numberOfOrders": "1",
                            "volume": "1545"
                        },
                        {
                            "price": "2816712999",
                            "numberOfOrders": "1",
                            "volume": "1795"
                        },
                        {
                            "price": "2816612999",
                            "numberOfOrders": "1",
                            "volume": "2085"
                        },
                        {
                            "price": "2816512999",
                            "numberOfOrders": "1",
                            "volume": "2422"
                        },
                        {
                            "price": "2816412999",
                            "numberOfOrders": "1",
                            "volume": "2814"
                        },
                        {
                            "price": "2816312999",
                            "numberOfOrders": "1",
                            "volume": "3270"
                        },
                        {
                            "price": "2816212999",
                            "numberOfOrders": "1",
                            "volume": "3799"
                        },
                        {
                            "price": "2816112999",
                            "numberOfOrders": "1",
                            "volume": "4393"
                        },
                        {
                            "price": "2816012999",
                            "numberOfOrders": "1",
                            "volume": "5127"
                        },
                        {
                            "price": "2815912999",
                            "numberOfOrders": "1",
                            "volume": "5956"
                        },
                        {
                            "price": "2815812999",
                            "numberOfOrders": "1",
                            "volume": "6921"
                        },
                        {
                            "price": "2815712999",
                            "numberOfOrders": "1",
                            "volume": "8041"
                        },
                        {
                            "price": "2815612999",
                            "numberOfOrders": "1",
                            "volume": "9342"
                        },
                        {
                            "price": "2815512999",
                            "numberOfOrders": "1",
                            "volume": "10854"
                        },
                        {
                            "price": "2815412999",
                            "numberOfOrders": "1",
                            "volume": "12610"
                        },
                        {
                            "price": "2815312999",
                            "numberOfOrders": "1",
                            "volume": "14651"
                        },
                        {
                            "price": "2815212999",
                            "numberOfOrders": "1",
                            "volume": "17022"
                        },
                        {
                            "price": "2815112999",
                            "numberOfOrders": "1",
                            "volume": "19777"
                        },
                        {
                            "price": "2815012999",
                            "numberOfOrders": "1",
                            "volume": "22978"
                        },
                        {
                            "price": "2814912999",
                            "numberOfOrders": "1",
                            "volume": "26697"
                        },
                        {
                            "price": "2814812999",
                            "numberOfOrders": "1",
                            "volume": "31017"
                        },
                        {
                            "price": "2814750249",
                            "numberOfOrders": "1",
                            "volume": "90"
                        },
                        {
                            "price": "2814712999",
                            "numberOfOrders": "1",
                            "volume": "36037"
                        },
                        {
                            "price": "2814612999",
                            "numberOfOrders": "1",
                            "volume": "41869"
                        },
                        {
                            "price": "2814512999",
                            "numberOfOrders": "1",
                            "volume": "48645"
                        }
                    ],
                    "sell": [
                        {
                            "price": "2817247085",
                            "numberOfOrders": "1",
                            "volume": "278"
                        },
                        {
                            "price": "2817347085",
                            "numberOfOrders": "1",
                            "volume": "1543"
                        },
                        {
                            "price": "2817447085",
                            "numberOfOrders": "1",
                            "volume": "1792"
                        },
                        {
                            "price": "2817547085",
                            "numberOfOrders": "1",
                            "volume": "2082"
                        },
                        {
                            "price": "2817647085",
                            "numberOfOrders": "1",
                            "volume": "2419"
                        },
                        {
                            "price": "2817747085",
                            "numberOfOrders": "1",
                            "volume": "2810"
                        },
                        {
                            "price": "2817947085",
                            "numberOfOrders": "1",
                            "volume": "3553"
                        },
                        {
                            "price": "2818047085",
                            "numberOfOrders": "1",
                            "volume": "4406"
                        },
                        {
                            "price": "2818147085",
                            "numberOfOrders": "1",
                            "volume": "5119"
                        },
                        {
                            "price": "2818247085",
                            "numberOfOrders": "1",
                            "volume": "5948"
                        },
                        {
                            "price": "2818347085",
                            "numberOfOrders": "1",
                            "volume": "6911"
                        },
                        {
                            "price": "2818447085",
                            "numberOfOrders": "1",
                            "volume": "8029"
                        },
                        {
                            "price": "2818547085",
                            "numberOfOrders": "1",
                            "volume": "9329"
                        },
                        {
                            "price": "2818647085",
                            "numberOfOrders": "1",
                            "volume": "10838"
                        },
                        {
                            "price": "2818747085",
                            "numberOfOrders": "1",
                            "volume": "12592"
                        },
                        {
                            "price": "2818847085",
                            "numberOfOrders": "1",
                            "volume": "14630"
                        },
                        {
                            "price": "2818947085",
                            "numberOfOrders": "1",
                            "volume": "16998"
                        },
                        {
                            "price": "2818975544",
                            "numberOfOrders": "1",
                            "volume": "10"
                        },
                        {
                            "price": "2819047085",
                            "numberOfOrders": "1",
                            "volume": "19749"
                        },
                        {
                            "price": "2819147085",
                            "numberOfOrders": "1",
                            "volume": "22945"
                        },
                        {
                            "price": "2819247085",
                            "numberOfOrders": "1",
                            "volume": "26659"
                        },
                        {
                            "price": "2819347085",
                            "numberOfOrders": "1",
                            "volume": "30973"
                        },
                        {
                            "price": "2819447085",
                            "numberOfOrders": "1",
                            "volume": "35986"
                        },
                        {
                            "price": "2819547085",
                            "numberOfOrders": "1",
                            "volume": "41809"
                        },
                        {
                            "price": "2819647085",
                            "numberOfOrders": "1",
                            "volume": "48576"
                        }
                    ],
                    "sequenceNumber": "1697590437480112072"
                }
            ]
        }
    }
    return order_book_snapshot_message


def _get_trades_mock() -> Dict[str, Any]:
    trade_message = {
        "result": {
            "trades": [
                {
                    "id": "374eefc4c872845df70d5302fe3953b35004371ca42364d962e804ff063be817",  # noqa: mock
                    "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                    "price": "2816712999",
                    "size": "350",
                    "buyer": "8ec6674d038f0a19870d2ebab358cd1a7e928e0b7806dfcb791d5143bf8ffad4",  # noqa: mock
                    "seller": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                    "aggressor": 2,
                    "buyOrder": "31e89330dda9e1bcb38b46209b99f08f2a56134997568a5ab20de64049e316ff",  # noqa: mock
                    "sellOrder": "1655ccdce276c38c1df0859fb93a31ce40dc8ea5d50fbbfcb8c26eb5edc9e20b",  # noqa: mock
                    "timestamp": "1697590811501334000",
                    "type": 1,
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
                        "makerFee": "11831",
                        "infrastructureFee": "29576",
                        "liquidityFee": "5916",
                        "makerFeeVolumeDiscount": "7886",
                        "infrastructureFeeVolumeDiscount": "19717",
                        "liquidityFeeVolumeDiscount": "3943",
                        "makerFeeReferrerDiscount": "0",
                        "infrastructureFeeReferrerDiscount": "0",
                        "liquidityFeeReferrerDiscount": "0"
                    }
                },
                {
                    "id": "795024c89c76211e9acd1f1a0f06a907961c0b6ae7496e4a1b1025b677727854",  # noqa: mock
                    "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                    "price": "2816612999",
                    "size": "2085",
                    "buyer": "8ec6674d038f0a19870d2ebab358cd1a7e928e0b7806dfcb791d5143bf8ffad4",  # noqa: mock
                    "seller": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                    "aggressor": 2,
                    "buyOrder": "5f3132a31ac18a4782bbf82f871bc5ea367f84f9f31ed6bd46dbb590ec2efffb",  # noqa: mock
                    "sellOrder": "1655ccdce276c38c1df0859fb93a31ce40dc8ea5d50fbbfcb8c26eb5edc9e20b",  # noqa: mock
                    "timestamp": "1697590811501334000",
                    "type": 1,
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
                        "makerFee": "70472",
                        "infrastructureFee": "176180",
                        "liquidityFee": "35237",
                        "makerFeeVolumeDiscount": "46981",
                        "infrastructureFeeVolumeDiscount": "117452",
                        "liquidityFeeVolumeDiscount": "23490",
                        "makerFeeReferrerDiscount": "0",
                        "infrastructureFeeReferrerDiscount": "0",
                        "liquidityFeeReferrerDiscount": "0"
                    }
                },
                {
                    "id": "1c7613733465806a005e757d36cde0d4db9bb9bd2808c789a1f2ab54364c6588",  # noqa: mock
                    "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                    "price": "2816512999",
                    "size": "2422",
                    "buyer": "8ec6674d038f0a19870d2ebab358cd1a7e928e0b7806dfcb791d5143bf8ffad4",  # noqa: mock
                    "seller": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                    "aggressor": 2,
                    "buyOrder": "9d090b7c55a90fa3129e7a879e7ca335c2b3149a2c3b2d9291391847c55eaf4d",  # noqa: mock
                    "sellOrder": "1655ccdce276c38c1df0859fb93a31ce40dc8ea5d50fbbfcb8c26eb5edc9e20b",  # noqa: mock
                    "timestamp": "1697590811501334000",
                    "type": 1,
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
                        "makerFee": "81860",
                        "infrastructureFee": "204648",
                        "liquidityFee": "40930",
                        "makerFeeVolumeDiscount": "54572",
                        "infrastructureFeeVolumeDiscount": "136432",
                        "liquidityFeeVolumeDiscount": "27286",
                        "makerFeeReferrerDiscount": "0",
                        "infrastructureFeeReferrerDiscount": "0",
                        "liquidityFeeReferrerDiscount": "0"
                    }
                },
                {
                    "id": "09cd751c7771e78fe628ae39a4df481805ebc746c0ce5da989e539f8fcdb7e67",  # noqa: mock
                    "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                    "price": "2816312999",
                    "size": "2363",
                    "buyer": "8ec6674d038f0a19870d2ebab358cd1a7e928e0b7806dfcb791d5143bf8ffad4",  # noqa: mock
                    "seller": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                    "aggressor": 2,
                    "buyOrder": "aa291e8a99cf6666e7defdf74893219296d985195c672829d933ca8a67e89e36",  # noqa: mock
                    "sellOrder": "1655ccdce276c38c1df0859fb93a31ce40dc8ea5d50fbbfcb8c26eb5edc9e20b",  # noqa: mock
                    "timestamp": "1697590811501334000",
                    "type": 1,
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
                    }
                }
            ]
        }
    }
    return trade_message


def _get_market_data_mock() -> Dict[str, Any]:
    market_data_message = {
        "result": {
            "marketData": [
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
                    "market": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                    "timestamp": "1697220852016362000",
                    "openInterest": "14787",
                    "indicativePrice": "0",
                    "marketTradingMode": 1,
                    "targetStake": "477565219528200000000",
                    "suppliedStake": "200500000000000000000000",
                    "priceMonitoringBounds": [
                        {
                            "minValidPrice": "2866233",
                            "maxValidPrice": "2942770",
                            "trigger": {
                                "horizon": "900",
                                "probability": "0.90001",
                                "auctionExtension": "60"
                            },
                            "referencePrice": "2904342"
                        },
                        {
                            "minValidPrice": "2828441",
                            "maxValidPrice": "2981515",
                            "trigger": {
                                "horizon": "3600",
                                "probability": "0.90001",
                                "auctionExtension": "300"
                            },
                            "referencePrice": "2904342"
                        },
                        {
                            "minValidPrice": "2753817",
                            "maxValidPrice": "3059953",
                            "trigger": {
                                "horizon": "14400",
                                "probability": "0.90001",
                                "auctionExtension": "900"
                            },
                            "referencePrice": "2904342"
                        },
                        {
                            "minValidPrice": "2544729",
                            "maxValidPrice": "3294419",
                            "trigger": {
                                "horizon": "86400",
                                "probability": "0.90001",
                                "auctionExtension": "3600"
                            },
                            "referencePrice": "2904342"
                        }
                    ],
                    "marketValueProxy": "200500000000000000000000",
                    "liquidityProviderFeeShare": [
                        {
                            "party": "69464e35bcb8e8a2900ca0f87acaf252d50cf2ab2fc73694845a16b7c8a0dc6f",  # noqa: mock
                            "equityLikeShare": "0.002547449612323",
                            "averageEntryValuation": "4000000000000000000000",
                            "averageScore": "0.5062301996",
                            "virtualStake": "73101137619766273826463.4801562969551275"
                        },
                        {
                            "party": "fdab1c1c9db496f651d922e3b056a4736e3a3b0ee301cb20afa491f3656939d8",  # noqa: mock
                            "equityLikeShare": "0.997452550387677",
                            "averageEntryValuation": "200510791137148915481663.6585315616536924",
                            "averageScore": "0.4937698004",
                            "virtualStake": "28622711830042755512027966.0239715486758806"
                        }
                    ],
                    "productData": {
                        "perpetualData": {
                            "fundingPayment": "1596698",
                            "fundingRate": "0.0005338755797842",
                            "internalTwap": "2992364698",
                            "externalTwap": "2990768000"
                        }
                    },
                    "marketState": 5,
                    "nextMarkToMarket": "1697220853545737884",
                    "lastTradedPrice": "2904342",
                    "marketGrowth": "-0.0003756574004508"
                }
            ]
        }
    }
    return market_data_message


def _get_market_data_rest_mock() -> Dict[str, Any]:
    market_data_rest_response = {
        "market": {
            "id": "COINALPHA.HBOT",  # noqa: mock
            "tradableInstrument": {
                "instrument": {
                    "id": "",
                    "code": "BTCUSD.PERP",
                    "name": "BTCUSD Perpetual Futures",
                    "metadata": {
                        "tags": [
                            "formerly:50657270657475616c",
                            "base:BTC",
                            "quote:USD",
                            "class:fx/crypto",
                            "perpetual",
                            "sector:crypto",
                            "auto:perpetual_btc_usd"
                        ]
                    },
                    "perpetual": {
                        "settlementAsset": "c9fe6fc24fce121b2cc72680543a886055abb560043fda394ba5376203b7527d",  # noqa: mock
                        "quoteName": "USD",
                        "marginFundingFactor": "0.1",
                        "interestRate": "0",
                        "clampLowerBound": "0",
                        "clampUpperBound": "0",
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
                        "dataSourceSpecForSettlementData": {
                            "id": "9755803fa590390c7ec6ebf196596901bccedb536898b1f4ab2d0a9c103367b3",  # noqa: mock
                            "createdAt": "0",
                            "updatedAt": "0",
                            "data": {
                                "external": {
                                    "ethOracle": {
                                        "address": "0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43",  # noqa: mock
                                        "abi": "[{\"inputs\":[],\"name\":\"latestAnswer\",\"outputs\":[{\"internalType\":\"int256\",\"name\":\"\",\"type\":\"int256\"}],\"stateMutability\":\"view\",\"type\":\"function\"}]",
                                        "method": "latestAnswer",
                                        "args": [],
                                        "trigger": {
                                            "timeTrigger": {
                                                "initial": "1697228865",
                                                "every": "30"
                                            }
                                        },
                                        "requiredConfirmations": "3",
                                        "filters": [
                                            {
                                                "key": {
                                                    "name": "btc.price",
                                                    "type": "TYPE_INTEGER",
                                                    "numberDecimalPlaces": "8"
                                                },
                                                "conditions": [
                                                    {
                                                        "operator": "OPERATOR_GREATER_THAN",
                                                        "value": "0"
                                                    }
                                                ]
                                            }
                                        ],
                                        "normalisers": [
                                            {
                                                "name": "btc.price",
                                                "expression": "$[0]"
                                            }
                                        ]
                                    }
                                }
                            },
                            "status": "STATUS_UNSPECIFIED"
                        },
                        "dataSourceSpecBinding": {
                            "settlementDataProperty": "btc.price",
                            "settlementScheduleProperty": "vegaprotocol.builtin.timetrigger"
                        }
                    }
                },
                "marginCalculator": {
                    "scalingFactors": {
                        "searchLevel": 1.1,
                        "initialMargin": 1.5,
                        "collateralRelease": 1.7
                    }
                },
                "logNormalRiskModel": {
                    "riskAversionParameter": 0.000001,
                    "tau": 0.00000380258,
                    "params": {
                        "mu": 0,
                        "r": 0,
                        "sigma": 1.5
                    }
                }
            },
            "decimalPlaces": "5",
            "fees": {
                "factors": {
                    "makerFee": "0.0002",
                    "infrastructureFee": "0.0005",
                    "liquidityFee": "0.0001"
                }
            },
            "openingAuction": {
                "duration": "70",
                "volume": "0"
            },
            "priceMonitoringSettings": {
                "parameters": {
                    "triggers": [
                        {
                            "horizon": "4320",
                            "probability": "0.99",
                            "auctionExtension": "300"
                        },
                        {
                            "horizon": "1440",
                            "probability": "0.99",
                            "auctionExtension": "180"
                        },
                        {
                            "horizon": "360",
                            "probability": "0.99",
                            "auctionExtension": "120"
                        }
                    ]
                }
            },
            "liquidityMonitoringParameters": {
                "targetStakeParameters": {
                    "timeWindow": "3600",
                    "scalingFactor": 10
                },
                "triggeringRatio": "0.9",
                "auctionExtension": "1"
            },
            "tradingMode": "TRADING_MODE_CONTINUOUS",
            "state": "STATE_ACTIVE",
            "marketTimestamps": {
                "proposed": "1697228717492432601",
                "pending": "1697228795000000000",
                "open": "1697229015913681254",
                "close": "0"
            },
            "positionDecimalPlaces": "4",
            "lpPriceRange": "",
            "linearSlippageFactor": "0.01",
            "quadraticSlippageFactor": "0",
            "liquiditySlaParams": {
                "priceRange": "0.05",
                "commitmentMinTimeFraction": "0.95",
                "performanceHysteresisEpochs": "1",
                "slaCompetitionFactor": "0.9"
            }
        }
    }
    return market_data_rest_response


def _get_latest_market_data_rest_mock() -> Dict[str, Any]:
    latest_market_data_rest_response = {
        "marketData": {
            "markPrice": "2836834817",
            "bestBidPrice": "2836834817",
            "bestBidVolume": "404",
            "bestOfferPrice": "2837602085",
            "bestOfferVolume": "1318",
            "bestStaticBidPrice": "2836834817",
            "bestStaticBidVolume": "404",
            "bestStaticOfferPrice": "2837602085",
            "bestStaticOfferVolume": "1318",
            "midPrice": "2837218451",
            "staticMidPrice": "2837218451",
            "market": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
            "timestamp": "1697591240530183000",
            "openInterest": "654289",
            "auctionEnd": "0",
            "auctionStart": "0",
            "indicativePrice": "0",
            "indicativeVolume": "0",
            "marketTradingMode": "TRADING_MODE_CONTINUOUS",
            "trigger": "AUCTION_TRIGGER_UNSPECIFIED",
            "extensionTrigger": "AUCTION_TRIGGER_UNSPECIFIED",
            "targetStake": "27284489556",
            "suppliedStake": "80000000000",
            "priceMonitoringBounds": [
                {
                    "minValidPrice": "2779934325",
                    "maxValidPrice": "2853445263",
                    "trigger": {
                        "horizon": "360",
                        "probability": "0.99",
                        "auctionExtension": "120"
                    },
                    "referencePrice": "2816486115"
                },
                {
                    "minValidPrice": "2744103176",
                    "maxValidPrice": "2891148882",
                    "trigger": {
                        "horizon": "1440",
                        "probability": "0.99",
                        "auctionExtension": "180"
                    },
                    "referencePrice": "2816811213"
                },
                {
                    "minValidPrice": "2691482292",
                    "maxValidPrice": "2946165595",
                    "trigger": {
                        "horizon": "4320",
                        "probability": "0.99",
                        "auctionExtension": "300"
                    },
                    "referencePrice": "2816379817"
                }
            ],
            "marketValueProxy": "0",
            "liquidityProviderFeeShare": [
                {
                    "party": "8ec6674d038f0a19870d2ebab358cd1a7e928e0b7806dfcb791d5143bf8ffad4",  # noqa: mock
                    "equityLikeShare": "1",
                    "averageEntryValuation": "80093027688.746276159419072",
                    "averageScore": "1",
                    "virtualStake": "83193951333.8786909308886644"
                }
            ],
            "marketState": "STATE_ACTIVE",
            "nextMarkToMarket": "1697591244756333613",
            "lastTradedPrice": "2836834817",
            "marketGrowth": "0.001189340855297",
            "productData": {
                "perpetualData": {
                    "fundingPayment": "-5176771",
                    "fundingRate": "-0.0018207404062221",
                    "internalTwap": "2838046229",
                    "externalTwap": "2843223000"
                }
            },
            "liquidityProviderSla": [
                {
                    "party": "8ec6674d038f0a19870d2ebab358cd1a7e928e0b7806dfcb791d5143bf8ffad4",  # noqa: mock
                    "currentEpochFractionOfTimeOnBook": "1",
                    "lastEpochFractionOfTimeOnBook": "1",
                    "lastEpochFeePenalty": "0",
                    "lastEpochBondPenalty": "0",
                    "hysteresisPeriodFeePenalties": [
                        "0"
                    ],
                    "requiredLiquidity": "80000000000",
                    "notionalVolumeBuys": "94281354092.5499",
                    "notionalVolumeSells": "95910548327.953"
                }
            ]
        }
    }

    return latest_market_data_rest_response


def _get_funding_rate_periods_rest_mock() -> Dict[str, Any]:
    funding_rate_periods_rest_response = {
        "fundingPeriods": {
            "edges": [
                {
                    "node": {
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                        "seq": "1208",
                        "start": "1697591266000000000",
                        "internalTwap": "0",
                        "externalTwap": "0"
                    },
                    "cursor": "eyJzdGFydFRpbWUiOiIyMDIzLTEwLTE4VDAxOjA3OjQ2WiIsIm1hcmtldElEIjoiNDk0MTQwMGQ2MGY2MWM0OGZlMWQxNGQ0MzA3YWQxMTExYTI5YTliZjhkMGJiNTc4YjM4OTU4ZTYwN2YyYzIxZSIsImZ1bmRpbmdQZXJpb2RTZXEiOjEyMDh9"  # noqa: mock
                },
                {
                    "node": {
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                        "seq": "1207",
                        "start": "1697590966000000000",
                        "end": "1697591266000000000",
                        "fundingPayment": "-5257989",
                        "fundingRate": "-0.0018493058757614",
                        "internalTwap": "2837965011",
                        "externalTwap": "2843223000"
                    },
                    "cursor": "eyJzdGFydFRpbWUiOiIyMDIzLTEwLTE4VDAxOjAyOjQ2WiIsIm1hcmtldElEIjoiNDk0MTQwMGQ2MGY2MWM0OGZlMWQxNGQ0MzA3YWQxMTExYTI5YTliZjhkMGJiNTc4YjM4OTU4ZTYwN2YyYzIxZSIsImZ1bmRpbmdQZXJpb2RTZXEiOjEyMDd9"  # noqa: mock
                },
                {
                    "node": {
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
                        "seq": "1206",
                        "start": "1697590666000000000",
                        "end": "1697590966000000000",
                        "fundingPayment": "-23774251",
                        "fundingRate": "-0.0083617257598155",
                        "internalTwap": "2819448749",
                        "externalTwap": "2843223000"
                    },
                    "cursor": "eyJzdGFydFRpbWUiOiIyMDIzLTEwLTE4VDAwOjU3OjQ2WiIsIm1hcmtldElEIjoiNDk0MTQwMGQ2MGY2MWM0OGZlMWQxNGQ0MzA3YWQxMTExYTI5YTliZjhkMGJiNTc4YjM4OTU4ZTYwN2YyYzIxZSIsImZ1bmRpbmdQZXJpb2RTZXEiOjEyMDZ9"  # noqa: mock
                }
            ]
        }
    }

    return funding_rate_periods_rest_response


def _get_order_book_snapshot_rest_mock() -> Dict[str, Any]:
    order_book_snapshot_rest_response = {
        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
        "buy": [
            {
                "price": "2836435118",
                "numberOfOrders": "1",
                "volume": "1466"
            },
            {
                "price": "2836335118",
                "numberOfOrders": "1",
                "volume": "3246"
            },
            {
                "price": "2836235118",
                "numberOfOrders": "1",
                "volume": "3771"
            },
            {
                "price": "2836135118",
                "numberOfOrders": "1",
                "volume": "4381"
            },
            {
                "price": "2836035118",
                "numberOfOrders": "1",
                "volume": "5091"
            },
            {
                "price": "2835935118",
                "numberOfOrders": "1",
                "volume": "5914"
            },
            {
                "price": "2835835118",
                "numberOfOrders": "1",
                "volume": "6872"
            },
            {
                "price": "2835735118",
                "numberOfOrders": "1",
                "volume": "7984"
            },
            {
                "price": "2835635118",
                "numberOfOrders": "1",
                "volume": "9276"
            },
            {
                "price": "2835535118",
                "numberOfOrders": "1",
                "volume": "10777"
            },
            {
                "price": "2835435118",
                "numberOfOrders": "1",
                "volume": "12521"
            },
            {
                "price": "2835335118",
                "numberOfOrders": "1",
                "volume": "14548"
            },
            {
                "price": "2835235118",
                "numberOfOrders": "1",
                "volume": "16902"
            },
            {
                "price": "2835135118",
                "numberOfOrders": "1",
                "volume": "19638"
            },
            {
                "price": "2835035118",
                "numberOfOrders": "1",
                "volume": "22816"
            },
            {
                "price": "2834935118",
                "numberOfOrders": "1",
                "volume": "26508"
            },
            {
                "price": "2834835118",
                "numberOfOrders": "1",
                "volume": "30798"
            },
            {
                "price": "2834735118",
                "numberOfOrders": "1",
                "volume": "35783"
            },
            {
                "price": "2834635118",
                "numberOfOrders": "1",
                "volume": "41573"
            },
            {
                "price": "2834535118",
                "numberOfOrders": "1",
                "volume": "48302"
            }
        ],
        "sell": [
            {
                "price": "2838002085",
                "numberOfOrders": "1",
                "volume": "1886"
            },
            {
                "price": "2838102085",
                "numberOfOrders": "1",
                "volume": "2789"
            },
            {
                "price": "2838202085",
                "numberOfOrders": "1",
                "volume": "3241"
            },
            {
                "price": "2838302085",
                "numberOfOrders": "1",
                "volume": "3765"
            },
            {
                "price": "2838402085",
                "numberOfOrders": "1",
                "volume": "4375"
            },
            {
                "price": "2838502085",
                "numberOfOrders": "1",
                "volume": "5083"
            },
            {
                "price": "2838602085",
                "numberOfOrders": "1",
                "volume": "5905"
            },
            {
                "price": "2838702085",
                "numberOfOrders": "1",
                "volume": "6861"
            },
            {
                "price": "2838802085",
                "numberOfOrders": "1",
                "volume": "7972"
            },
            {
                "price": "2838902085",
                "numberOfOrders": "1",
                "volume": "9262"
            },
            {
                "price": "2839002085",
                "numberOfOrders": "1",
                "volume": "10761"
            },
            {
                "price": "2839102085",
                "numberOfOrders": "1",
                "volume": "12502"
            },
            {
                "price": "2839202085",
                "numberOfOrders": "1",
                "volume": "14526"
            },
            {
                "price": "2839302085",
                "numberOfOrders": "1",
                "volume": "16876"
            },
            {
                "price": "2839402085",
                "numberOfOrders": "1",
                "volume": "19608"
            },
            {
                "price": "2839502085",
                "numberOfOrders": "1",
                "volume": "22781"
            },
            {
                "price": "2839602085",
                "numberOfOrders": "1",
                "volume": "26468"
            },
            {
                "price": "2839702085",
                "numberOfOrders": "1",
                "volume": "30751"
            },
            {
                "price": "2839802085",
                "numberOfOrders": "1",
                "volume": "35728"
            },
            {
                "price": "2839902085",
                "numberOfOrders": "1",
                "volume": "41510"
            },
            {
                "price": "2840002085",
                "numberOfOrders": "1",
                "volume": "48228"
            }
        ],
        "lastTrade": {
            "id": "6b325bacee0498cbb7abfa9c39bc5dc95cd045cd70bc58ad659e761d72ce7566",  # noqa: mock
            "marketId": "COIN_ALPHA_HBOT_MARKET_ID",  # noqa: mock
            "price": "2836435118",
            "size": "100",
            "buyer": "8ec6674d038f0a19870d2ebab358cd1a7e928e0b7806dfcb791d5143bf8ffad4",  # noqa: mock
            "seller": "c3870e7f9aad0401f3014c2eb602a8f2be82c972481338ca31adacd33133de96",  # noqa: mock
            "aggressor": "SIDE_SELL",
            "buyOrder": "e1322efc4ce0fdf2d64cbfd96acb553e691b74fa3350e854bd3ee2134ea27245",  # noqa: mock
            "sellOrder": "c934ac3e70770b61bbcd025bbe4e2b35bedaabf4208c55f5c017a0b29a6ad6f4",  # noqa: mock
            "timestamp": "1697591562094563000",
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
                "makerFee": "3270",
                "infrastructureFee": "8174",
                "liquidityFee": "1636",
                "makerFeeVolumeDiscount": "2246",
                "infrastructureFeeVolumeDiscount": "5616",
                "liquidityFeeVolumeDiscount": "1123",
                "makerFeeReferrerDiscount": "56",
                "infrastructureFeeReferrerDiscount": "141",
                "liquidityFeeReferrerDiscount": "28"
            },
            "buyerAuctionBatch": "0",
            "sellerAuctionBatch": "0"
        },
        "sequenceNumber": "1697591562856384102"
    }

    return order_book_snapshot_rest_response
