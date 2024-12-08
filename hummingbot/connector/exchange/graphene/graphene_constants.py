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

import json
import os

# METANODE MODULES
from metanode.graphene_constants import GrapheneConstants as MetanodeGrapheneConstants
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
        domain = domain.lower().replace("_", " ")
        super().__init__(chain_name=domain if domain else None)
        self.hummingbot = HummingbotConfig
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
            self.DATABASE_FOLDER = str(os.path.dirname(os.path.abspath(__file__))) + "/database/"
            self.chain.DATABASE = self.DATABASE_FOLDER + self.chain.NAME.replace(" ", "_") + ".db"
            try:
                with open(self.DATABASE_FOLDER + self.chain.NAME.replace(" ", "_") + "_pairs.txt", "r") as handle:
                    data = json.loads(handle.read())
                    handle.close()
                self.chain.PAIRS = data[0]
                self.chain.ACCOUNT = data[1]
            except FileNotFoundError:
                pass
            self.process_pairs()
            self.core.PATH = str(os.path.dirname(os.path.abspath(__file__)))
            self.chain.TITLE = self.chain.NAME.title()
            if not hasattr(self.chain, "PREFIX"):
                self.chain.PREFIX = self.chain.CORE

    def process_pairs(self):
        self.chain.PAIRS = [i for i in self.chain.PAIRS if i not in invert_pairs(self.chain.PAIRS)]
        self.chain.INVERTED_PAIRS = invert_pairs(self.chain.PAIRS)
        self.chain.ASSETS = list(set(assets_from_pairs(self.chain.PAIRS) + [self.chain.CORE]))
        self.chain.CORE_PAIRS = [
            i
            for i in [self.chain.CORE + "-" + asset for asset in self.chain.ASSETS if asset != self.chain.CORE]
            if i not in self.chain.PAIRS and i not in self.chain.INVERTED_PAIRS
        ]
        self.chain.INVERTED_CORE_PAIRS = invert_pairs(self.chain.CORE_PAIRS)
        self.chain.ALL_PAIRS = (
            self.chain.PAIRS + self.chain.CORE_PAIRS + self.chain.INVERTED_PAIRS + self.chain.INVERTED_CORE_PAIRS
        )


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
    NODES = [
        "wss://ca.peerplays.info/",
        "wss://de.peerplays.xyz/",
        "wss://pl.peerplays.org/",
        "ws://96.46.48.98:18090",
        "wss://peerplaysblockchain.net/mainnet/api",
        "ws://witness.serverpit.com:8090",
        "ws://api.i9networks.net.br:8090",
        "wss://node.mainnet.peerblock.trade",
    ]
    PAIRS = ["BTC-PPY", "HIVE-PPY", "HBD-PPY"]
    BASES = ["BTC", "HIVE", "HBD"]
    CORE = "PPY"
    WHITELIST = []


class PeerplaysTestnetConfig:
    """
    configuration details specific to peerplays testnet
    """

    ACCOUNT = "litepresence1"
    NODES = [
        "wss://testnet.peerplays.download/api",
        "wss://testnet-ge.peerplays.download/api",
    ]
    PAIRS = ["TEST-HIVE", "TEST-HBD"]
    BASES = ["HIVE", "HBD", "ABC", "DEFG"]
    CORE = "TEST"
    WHITELIST = []


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
        "wss://eu.nodes.bitshares.ws/ws",
        "wss://cloud.xbts.io/wss",
        "wss://dex.iobanker.com/wss",
        "wss://bts.mypi.win/wss",
        "wss://node.xbts.io/wss",
        "wss://public.xbts.io/ws",
        "wss://btsws.roelandp.nl/wss",
        "wss://api-us.61bts.com/wss",
        "wss://api.dex.trading/wss",
    ]
    PAIRS = ["BTS-HONEST", "BTS-HONEST.USD", "BTS-XBTSX.USDT"]
    BASES = ["HONEST", "XBTSX", "GDEX", "BTWTY", "IOB"]
    CORE = "BTS"
    WHITELIST = []


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
    BASES = ["USD", "CNY"]
    CORE = "TEST"
    WHITELIST = []
