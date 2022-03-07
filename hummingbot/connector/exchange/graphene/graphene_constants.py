# DISABLE SELECT PYLINT TESTS
# pylint: disable=too-few-public-methods, bad-continuation
"""
 ╔════════════════════════════════════════════════════╗
 ║ ╔═╗╦═╗╔═╗╔═╗╦ ╦╔═╗╔╗╔╔═╗  ╔╦╗╔═╗╔╦╗╔═╗╔╗╔╔═╗╔╦╗╔═╗ ║
 ║ ║ ╦╠╦╝╠═╣╠═╝╠═╣║╣ ║║║║╣   ║║║║╣  ║ ╠═╣║║║║ ║ ║║║╣  ║
 ║ ╚═╝╩╚═╩ ╩╩  ╩ ╩╚═╝╝╚╝╚═╝  ╩ ╩╚═╝ ╩ ╩ ╩╝╚╝╚═╝═╩╝╚═╝ ║
 ║    DECENTRALIZED EXCHANGE HUMMINGBOT CONNECTOR     ║
 ╚════════════════════════════════════════════════════╝
"""

# METANODE MODULES
from metanode.graphene_constants import \
    GrapheneConstants as MetanodeGrapheneConstants
from metanode.graphene_utils import assets_from_pairs, invert_pairs, sls


class GrapheneConstants(MetanodeGrapheneConstants):
    """
    used for user configuration to override Graphene default constants, exposes:
        ~ self.chain
        ~ self.metanode
        ~ self.signing
        ~ self.core
        ~ self.hummingbot
    for the most part the user will edit self.chain
    """

    def __init__(
        self,
        domain: str = "",
    ):
        # ~ print("GrapheneConstants", domain)
        super().__init__(
            chain_name=domain.lower().replace("_", " ") if domain else None
        )
        self.hummingbot = HummingbotConfig
        domain = domain.replace("_", " ")
        if domain != "":
            # initialize config for this blockchain domain; eg. peerplays or bitshares
            self.chains["peerplays"]["config"] = PeerplaysConfig
            self.chains["bitshares"]["config"] = BitsharesConfig
            self.chains["peerplays testnet"]["config"] = PeerplaysTestnetConfig
            self.chains["bitshares testnet"]["config"] = BitsharesTestnetConfig
            self.chain = self.chains[domain.lower()]["config"]
            self.chain.NAME = domain.lower()
            self.chain.CORE = self.chains[self.chain.NAME]["core"].upper()
            self.chain.ID = self.chains[self.chain.NAME]["id"]
            self.chain.NODES = [node.lower() for node in sls(self.chain.NODES)]
            self.chain.PAIRS = [
                i for i in self.chain.PAIRS if i not in invert_pairs(self.chain.PAIRS)
            ]
            self.chain.INVERTED_PAIRS = invert_pairs(self.chain.PAIRS)
            self.chain.ASSETS = assets_from_pairs(self.chain.PAIRS)
            self.chain.CORE_PAIRS = [
                i
                for i in [
                    self.chain.CORE + "-" + asset
                    for asset in self.chain.ASSETS
                    if asset != self.chain.CORE
                ]
                if i not in self.chain.PAIRS and i not in self.chain.INVERTED_PAIRS
            ]
            self.chain.INVERTED_CORE_PAIRS = invert_pairs(self.chain.CORE_PAIRS)
            self.chain.ALL_PAIRS = (
                self.chain.PAIRS
                + self.chain.CORE_PAIRS
                + self.chain.INVERTED_PAIRS
                + self.chain.INVERTED_CORE_PAIRS
            )
            self.chain.DATABASE = (
                self.core.PATH
                + "/database/"
                + self.chain.NAME.replace(" ", "_")
                + ".db"
            )
            self.chain.TITLE = self.chain.NAME.title()
            if not hasattr(self.chain, "PREFIX"):
                self.chain.PREFIX = self.chain.CORE


class HummingbotConfig:
    """
    constants specific to this connector
    """

    SYNCHRONIZE = False
    SNAPSHOT_SLEEP = 30
    ORDER_PREFIX = ""


class PeerplaysConfig:
    """
    ╔═════════════════════════════╗
    ║     HUMMINGBOT GRAPHENE     ║
    ║ ╔═╗╔═╗╔═╗╦═╗╔═╗╦  ╔═╗╦ ╦╔═╗ ║
    ║ ╠═╝║╣ ║╣ ╠╦╝╠═╝║  ╠═╣╚╦╝╚═╗ ║
    ║ ╩  ╚═╝╚═╝╩╚═╩  ╩═╝╩ ╩ ╩ ╚═╝ ║
    ║ DEX MARKET MAKING CONNECTOR ║
    ╚═════════════════════════════╝
    configuration details specific to peerplays mainnet
    """

    ACCOUNT = ""
    NODES = ["wss://peerplaysblockchain.net/mainnet/api"]
    PAIRS = ["BTC-PPY", "HIVE-PPY", "HBD-PPY"]


class PeerplaysTestnetConfig:
    """
    configuration details specific to peerplays testnet
    """

    ACCOUNT = "litepresence1"
    NODES = ["wss://ymir.peerplays.download/api"]
    PAIRS = ["TEST-ABC", "TEST-XYZ"]


class BitsharesConfig:
    """
    ╔═════════════════════════════╗
    ║     HUMMINGBOT GRAPHENE     ║
    ║  ╔╗ ╦╔╦╗╔═╗╦ ╦╔═╗╦═╗╔═╗╔═╗  ║
    ║  ╠╩╗║ ║ ╚═╗╠═╣╠═╣╠╦╝║╣ ╚═╗  ║
    ║  ╚═╝╩ ╩ ╚═╝╩ ╩╩ ╩╩╚═╚═╝╚═╝  ║
    ║ DEX MARKET MAKING CONNECTOR ║
    ╚═════════════════════════════╝
    configuration details specific to bitshares mainnet
    """

    ACCOUNT = "litepresence1"
    NODES = [
        "wss://api.bts.mobi/wss",
        "wss://api-us.61bts.com/wss",
        "wss://cloud.xbts.io/ws",
        "wss://api.dex.trading/wss",
        "wss://eu.nodes.bitshares.ws/ws",
        "wss://api.pindd.club/ws",
        "wss://dex.iobanker.com/ws",
        "wss://public.xbts.io/ws",
        "wss://node.xbts.io/ws",
        "wss://node.market.rudex.org/ws",
        "wss://nexus01.co.uk/ws",
        "wss://api-bts.liondani.com/ws",
        "wss://api.bitshares.bhuz.info/wss",
        "wss://btsws.roelandp.nl/ws",
        "wss://hongkong.bitshares.im/ws",
        "wss://node1.deex.exchange/wss",
        "wss://api.cnvote.vip:888/wss",
        "wss://bts.open.icowallet.net/ws",
        "wss://api.weaccount.cn/ws",
        "wss://api.61bts.com",
        "wss://api.btsgo.net/ws",
        "wss://bitshares.bts123.cc:15138/wss",
        "wss://singapore.bitshares.im/wss",
    ]
    PAIRS = ["BTS-HONEST", "BTS-HONEST.USD", "BTS-XBTSX.USDT"]


class BitsharesTestnetConfig:
    """
    configuration details specific to bitshares testnet
    """

    ACCOUNT = ""
    NODES = [
        "wss://testnet.bitshares.im/ws",
        "wss://testnet.dex.trading/",
        "wss://testnet.xbts.io/ws",
        "wss://api-testnet.61bts.com/ws",
    ]
    PAIRS = ["TEST-USD", "TEST-CNY"]
