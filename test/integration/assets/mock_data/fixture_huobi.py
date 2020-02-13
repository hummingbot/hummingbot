class FixtureHuobi:
    GET_ACCOUNTS = {"status": "ok", "data": [{"id": 11899168, "type": "spot", "subtype": "", "state": "working"}]}
    GET_BALANCES = {"status": "ok", "data": {"id": 11899168, "type": "spot", "state": "working",
                                             "list": [{"currency": "lun", "type": "trade", "balance": "0"},
                                                      {"currency": "husd", "type": "trade", "balance": "0.0146"},
                                                      {"currency": "eth", "type": "trade", "balance": "0.226546"}
                                                      ]}}
