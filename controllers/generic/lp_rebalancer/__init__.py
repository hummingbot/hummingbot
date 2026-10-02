# Relative, not `from controllers.generic....`. The same tree is imported under two
# different package roots: `controllers.*` inside a bot container, and
# `bots.controllers.*` by hummingbot-api, which mounts it one level deeper. An absolute
# path pins the module to one of them and breaks under the other — and because this
# package's __init__ runs before either candidate module path can be reached, the failure
# took the whole controller down rather than one import of it.
from .lp_rebalancer import LPRebalancer, LPRebalancerConfig

__all__ = ["LPRebalancer", "LPRebalancerConfig"]
