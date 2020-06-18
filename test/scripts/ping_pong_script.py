# def start(strategy, variables):
#     variables["ping_pong"] = 0
#
# def tick(strategy):
#     strategy.buy_levels = strategy.order_levels
#     strategy.sell_levels = strategy.order_levels
#     if variables["ping_pong"] > 0:
#         strategy.buy_levels -= variables["ping_pong"]
#         strategy.buy_levels = max(0, strategy.buy_levels)
#     elif variables["ping_pong"] < 0:
#         strategy.sell_levels -= abs(variables["ping_pong"])
#         strategy.sell_levels = max(0, strategy.sell_levels)
#
# def buy_order_completed():
#     variables["ping_pong"] += 1
#
# def sell_order_completed()
#     variables["ping_pong"] -= 1
