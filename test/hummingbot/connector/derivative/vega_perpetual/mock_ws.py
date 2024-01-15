def ws_connect_error():
    error = {
        "error": {
            "code": 8,
            "message": "client reached max subscription allowed"
        }
    }
    return error


def ws_not_found_error():
    error = {
        "error": {
            "code": 13,
            "message": "Internal error",
            "details": [
                {
                    "@type": "type.googleapis.com/vega.ErrorDetail",
                    "code": 10000,
                    "message": "no market found for id:COINALPHA.HBOT : malformed request"
                }
            ]
        }
    }
    return error


def ws_invalid_data():
    error = {
        "a": {
            "d": 13,
            "m": "Internal error",
            "details": [
                {
                    "@type": "type.googleapis.com/vega.ErrorDetail",
                    "code": 10000,
                    "message": "no market found for id:COINALPHA.HBOT : malformed request"
                }
            ]
        }
    }
    return error


def position_update_status():
    positions = {
        "result": {
            "snapshot": {
                "positions": [
                    {
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",
                        "partyId": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "realisedPnl": "49335",
                        "unrealisedPnl": "0",
                        "averageEntryPrice": "6599258",
                        "updatedAt": "1692267679432096000",
                        "lossSocialisationAmount": "26347",
                        "positionStatus": 100
                    },
                ],
                "lastPage": True
            }
        }
    }
    return positions


def position_update():
    positions = {
        "result": {
            "snapshot": {
                "positions": [
                    {
                        "marketId": "COIN_ALPHA_HBOT_MARKET_ID",
                        "partyId": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "realisedPnl": "49335",
                        "unrealisedPnl": "0",
                        "averageEntryPrice": "6599258",
                        "updatedAt": "1692267679432096000",
                        "lossSocialisationAmount": "26347",
                        "positionStatus": 2
                    },
                ],
                "lastPage": True
            }
        }
    }
    return positions


def trades_update():
    trades = {
        "result": {
            "trades": [
                {
                    "id": "TRADE.ID",
                    "marketId": "COIN_ALPHA_HBOT_MARKET_ID",
                    "price": "2684424478",
                    "size": "300",
                    "buyer": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                    "seller": "SELLER",
                    "aggressor": 2,
                    "buyOrder": "ORDER.ID_BUYER",
                    "sellOrder": "ORDER.ID_SELLER",
                    "timestamp": "1697318737486288000",
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
                        "makerFee": "9329",
                        "infrastructureFee": "23319",
                        "liquidityFee": "4665",
                        "makerFeeVolumeDiscount": "6410",
                        "infrastructureFeeVolumeDiscount": "16026",
                        "liquidityFeeVolumeDiscount": "3205",
                        "makerFeeReferrerDiscount": "80",
                        "infrastructureFeeReferrerDiscount": "201",
                        "liquidityFeeReferrerDiscount": "40"
                    }
                }
            ]
        }
    }
    return trades


def order_book_diff():
    diff = {
        "result": {
            "update": [
                {
                    "marketId": "COINALPHA.HBOT",
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
    return diff


def funding_info():
    funding_info = {
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
                    "market": "COINALPHA.HBOT",
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
                            "party": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                            "equityLikeShare": "0.002547449612323",
                            "averageEntryValuation": "4000000000000000000000",
                            "averageScore": "0.5062301996",
                            "virtualStake": "73101137619766273826463.4801562969551275"
                        },
                        {
                            "party": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                            "equityLikeShare": "0.997452550387677",
                            "averageEntryValuation": "200510791137148915481663.6585315616536924",
                            "averageScore": "0.4937698004",
                            "virtualStake": "28622711830042755512027966.0239715486758806"
                        }
                    ],
                    "marketState": 5,
                    "nextMarkToMarket": "1697220853545737884",
                    "lastTradedPrice": "2904342",
                    "marketGrowth": "-0.0003756574004508"
                }
            ]
        }
    }
    return funding_info


def order_book_snapshot():
    snapshot = {
        "result": {
            "marketDepth": [
                {
                    "marketId": "COINALPHA.HBOT",
                    "buy": [
                        {
                            "price": "2963660914",
                            "numberOfOrders": "1",
                            "volume": "1138"
                        }
                    ],
                    "sell": [
                        {
                            "price": "2964827881",
                            "numberOfOrders": "1",
                            "volume": "1709"
                        }
                    ],
                    "sequenceNumber": "1697837812441603063"
                }
            ]
        }
    }
    return snapshot


def orders_update():
    orders = {
        "result": {
            "updates": {
                "orders": [
                    {
                        "id": "ID",
                        "marketId": "COINALPHA.HBOT",
                        "partyId": "f882e93e63ea662b9ddee6b61de17345d441ade06475788561e6d470bebc9ece",  # noqa: mock
                        "side": 1,
                        "price": "2963260914",
                        "size": "100",
                        "remaining": "100",
                        "timeInForce": 1,
                        "type": 1,
                        "createdAt": "1697838030349919000",
                        "status": 1,
                        "version": "1",
                        "batchId": "1"
                    }
                ]
            }
        }
    }
    return orders


# NOTE: Balances...
def account_update():
    account = {
        "result": {
            "updates": {
                "accounts": [
                    {
                        "owner": "OWNER",
                        "balance": "1000000000000000000",
                        "asset": "HBOT_ASSET_ID",
                        "type": 4
                    }
                ]
            }
        }
    }
    return account


def account_snapshot_update():
    account = {
        "result": {
            "snapshot": {
                "accounts": [
                    {
                        "owner": "OWNER",
                        "balance": "3500000000000000000000",
                        "asset": "COINALPHA_ASSET_ID",
                        "type": 4
                    },
                    {
                        "owner": "OWNER",
                        "balance": "1000000000000000000",
                        "asset": "HBOT_ASSET_ID",
                        "type": 4
                    },
                ],
                "lastPage": True
            }
        }
    }
    return account
