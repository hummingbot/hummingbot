TOKEN_ADDRESS_MAP = {
    "HW2Eq3UZVSBttoUwUi/MUtE7rr2UU7/UH500byp7OAc=": {
        "symbol": "gm",
        "decimals": 6,
        "baseDenom": "ugm"
    },
    "reum7wQmk/owgvGMWMZn/6RFPV24zIKq3W6In/WwZgg=": {
        "symbol": "test_usd",
        "decimals": 18,
        "baseDenom": "wtest_usd"
    },
    "KeqcLzNx9qSH5+lcJHBB9KNW+YPrBk5dKzvPMiypahA=": {
        "symbol": "penumbra",
        "decimals": 6,
        "baseDenom": "upenumbra"
    },
    "nwPDkQq3OvLnBwGTD+nmv1Ifb2GEmFCgNHrU++9BsRE=": {
        "symbol": "gn",
        "decimals": 6,
        "baseDenom": "ugn"
    },
    "HLkKbVfA72oQaMdYFroWQ1qoSyl/KLHZiOMJhL2y9w0=": {
        "symbol": "test_eth",
        "decimals": 18,
        "baseDenom": "wtest_eth"
    },
    "o2gZdbhCH70Ry+7iBhkSeHC/PB1LZhgkn7LHC2kEhQc=": {
        "symbol": "test_btc",
        "decimals": 8,
        "baseDenom": "test_sat"
    },
    "6KBVsPINa8gWSHhfH+kAFJC4afEJA3EtuB2HyCqJUws=": {
        "symbol": "cube",
        "decimals": 0,
        "baseDenom": "cube"
    },
}

# Create token symbol map from address map

TOKEN_SYMBOL_MAP = {}

for address in TOKEN_ADDRESS_MAP:
    TOKEN_SYMBOL_MAP[TOKEN_ADDRESS_MAP[address]["symbol"]] = {
        "address": address,
        "decimals": TOKEN_ADDRESS_MAP[address]["decimals"],
        "baseDenom": TOKEN_ADDRESS_MAP[address]["baseDenom"]
    }
