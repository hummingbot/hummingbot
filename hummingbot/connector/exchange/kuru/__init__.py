def __getattr__(name):
    if name == "KuruExchange":
        from hummingbot.connector.exchange.kuru.kuru_exchange import KuruExchange
        return KuruExchange
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
