# DISABLE SELECT PYLINT TESTS
# pylint: disable=bad-continuation

r"""
 ╔════════════════════════════════════════════════════╗
 ║ ╔═╗╦═╗╔═╗╔═╗╦ ╦╔═╗╔╗╔╔═╗  ╔╦╗╔═╗╔╦╗╔═╗╔╗╔╔═╗╔╦╗╔═╗ ║
 ║ ║ ╦╠╦╝╠═╣╠═╝╠═╣║╣ ║║║║╣   ║║║║╣  ║ ╠═╣║║║║ ║ ║║║╣  ║
 ║ ╚═╝╩╚═╩ ╩╩  ╩ ╩╚═╝╝╚╝╚═╝  ╩ ╩╚═╝ ╩ ╩ ╩╝╚╝╚═╝═╩╝╚═╝ ║
 ║    DECENTRALIZED EXCHANGE HUMMINGBOT CONNECTOR     ║
 ╚════════════════════════════════════════════════════╝
~
auth = GrapheneAuth
order = auth.prototype_order(pair)
order["edicts"] = {}
broker(order)
"""
# METANODE MODULES
from metanode.graphene_auth import GrapheneAuth as MetanodeGrapheneAuth

# HUMMINGBOT MODULES
from hummingbot.connector.exchange.graphene.graphene_constants import GrapheneConstants


class GrapheneAuth(MetanodeGrapheneAuth):
    """
    given a Wallet Import Format (WIF) Active (or Owner) Key
    expose buy/sell/cancel methods:
        ~ prototype_order()
        ~ broker()
    """

    def __init__(
        self,
        wif: str,
        domain: str,
    ):
        # ~ print("GrapheneAuth")
        self.wif = wif
        self.domain = domain
        self.constants = GrapheneConstants(domain)
        super().__init__(self.constants, wif)
        self.carry_prints = True
