import numpy as np
import collections

Constraints = collections.namedtuple('Constraints', 'target first_corner second_corner bounds')


class ConstraintSolver():
    def __init__(self):
        self._ct_to_function = {
            "BBB": self.buy_buy_buy,
            "BBS": self.buy_buy_sell,
            "BSB": self.buy_sell_buy,
            "BSS": self.buy_sell_sell,
            "SBB": self.sell_buy_buy,
            "SBS": self.sell_buy_sell,
            "SSB": self.sell_sell_buy,
            "SSS": self.sell_sell_sell
        }

    def generate_constraints(self, cycle_type, first_book, second_book, third_book, fees):
        return self._ct_to_function[cycle_type](first_book, second_book, third_book, fees)

    @classmethod
    def buy_buy_buy(cls, first_book, second_book, third_book, fees):
        constraint_1 = [1 - fees] * len(first_book)
        constraint_1 += [-o.price for o in second_book]
        constraint_1 += [0] * len(third_book)

        constraint_2 = [0] * len(first_book)
        constraint_2 += [1 - fees] * len(second_book)
        constraint_2 += [-o.price for o in third_book]

        target = [-o.price for o in first_book]
        target += [0] * len(second_book)
        target += [1] * len(third_book)

        bounds_first = [[0, o.amount] for o in first_book]
        bounds_second = [[0, o.amount] for o in second_book]
        bounds_third = [[0, o.amount] for o in third_book]

        bounds = bounds_first + bounds_second + bounds_third
        return Constraints(np.array(target), np.array(constraint_1), np.array(constraint_2), np.array(bounds))

    @classmethod
    def buy_buy_sell(cls, first_book, second_book, third_book, fees):
        constraint_1 = [1 - fees] * len(first_book)
        constraint_1 += [-o.price for o in second_book]
        constraint_1 += [0] * len(third_book)

        constraint_2 = [0] * len(first_book)
        constraint_2 += [1 - fees] * len(second_book)
        constraint_2 += [-1] * len(third_book)

        target = [-o.price for o in first_book]
        target += [0] * len(second_book)
        target += [o.price for o in third_book]

        bounds_first = [[0, o.amount] for o in first_book]
        bounds_second = [[0, o.amount] for o in second_book]
        bounds_third = [[0, o.amount] for o in third_book]

        bounds = bounds_first + bounds_second + bounds_third
        return Constraints(np.array(target), np.array(constraint_1), np.array(constraint_2), np.array(bounds))

    @classmethod
    def buy_sell_buy(cls, first_book, second_book, third_book, fees):
        constraint_1 = [1 - fees] * len(first_book)
        constraint_1 += [-1] * len(second_book)
        constraint_1 += [0] * len(third_book)

        constraint_2 = [0] * len(first_book)
        constraint_2 += [-o.price * (1 - fees) for o in second_book]
        constraint_2 += [o.price for o in third_book]

        target = [-o.price for o in first_book]
        target += [0] * len(second_book)
        target += [1] * len(third_book)

        bounds_first = [[0, o.amount] for o in first_book]
        bounds_second = [[0, o.amount] for o in second_book]
        bounds_third = [[0, o.amount] for o in third_book]

        bounds = bounds_first + bounds_second + bounds_third
        return Constraints(np.array(target), np.array(constraint_1), np.array(constraint_2), np.array(bounds))

    @classmethod
    def buy_sell_sell(cls, first_book, second_book, third_book, fees):
        constraint_1 = [1 - fees] * len(first_book)
        constraint_1 += [-1] * len(second_book)
        constraint_1 += [0] * len(third_book)

        constraint_2 = [0] * len(first_book)
        constraint_2 += [-o.price * (1 - fees) for o in second_book]
        constraint_2 += [1] * len(third_book)

        target = [-o.price for o in first_book]
        target += [0] * len(second_book)
        target += [o.price for o in third_book]

        bounds_first = [[0, o.amount] for o in first_book]
        bounds_second = [[0, o.amount] for o in second_book]
        bounds_third = [[0, o.amount] for o in third_book]

        bounds = bounds_first + bounds_second + bounds_third
        return Constraints(np.array(target), np.array(constraint_1), np.array(constraint_2), np.array(bounds))

    @classmethod
    def sell_buy_buy(cls, first_book, second_book, third_book, fees):
        constraint_1 = [o.price * (1 - fees) for o in first_book]
        constraint_1 += [-o.price for o in second_book]
        constraint_1 += [0] * len(third_book)

        constraint_2 = [0] * len(first_book)
        constraint_2 += [1 - fees] * len(second_book)
        constraint_2 += [-o.price for o in third_book]

        target = [-1] * len(first_book)
        target += [0] * len(second_book)
        target += [1] * len(third_book)

        bounds_first = [[0, o.amount] for o in first_book]
        bounds_second = [[0, o.amount] for o in second_book]
        bounds_third = [[0, o.amount] for o in third_book]

        bounds = bounds_first + bounds_second + bounds_third
        return Constraints(np.array(target), np.array(constraint_1), np.array(constraint_2), np.array(bounds))

    @classmethod
    def sell_buy_sell(cls, first_book, second_book, third_book, fees):
        constraint_1 = [o.price * (1 - fees) for o in first_book]
        constraint_1 += [-o.price for o in second_book]
        constraint_1 += [0] * len(third_book)

        constraint_2 = [0] * len(first_book)
        constraint_2 += [1 - fees] * len(second_book)
        constraint_2 += [-1] * len(third_book)

        target = [-1] * len(first_book)
        target += [0] * len(second_book)
        target += [o.price for o in third_book]

        bounds_first = [[0, o.amount] for o in first_book]
        bounds_second = [[0, o.amount] for o in second_book]
        bounds_third = [[0, o.amount] for o in third_book]

        bounds = bounds_first + bounds_second + bounds_third
        return Constraints(np.array(target), np.array(constraint_1), np.array(constraint_2), np.array(bounds))

    @classmethod
    def sell_sell_buy(cls, first_book, second_book, third_book, fees):
        constraint_1 = [-o.price * (1 - fees) for o in first_book]
        constraint_1 += [1] * len(second_book)
        constraint_1 += [0] * len(third_book)

        constraint_2 = [0] * len(first_book)
        constraint_2 += [o.price * (1 - fees) for o in second_book]
        constraint_2 += [-o.price for o in third_book]

        target = [-1] * len(first_book)
        target += [0] * len(second_book)
        target += [1] * len(third_book)

        bounds_first = [[0, o.amount] for o in first_book]
        bounds_second = [[0, o.amount] for o in second_book]
        bounds_third = [[0, o.amount] for o in third_book]

        bounds = bounds_first + bounds_second + bounds_third
        return Constraints(np.array(target), np.array(constraint_1), np.array(constraint_2), np.array(bounds))

    @classmethod
    def sell_sell_sell(cls, first_book, second_book, third_book, fees):
        constraint_1 = [-o.price * (1 - fees) for o in first_book]
        constraint_1 += [1] * len(second_book)
        constraint_1 += [0] * len(third_book)

        constraint_2 = [0] * len(first_book)
        constraint_2 += [-o.price * (1 - fees) for o in second_book]
        constraint_2 += [1] * len(third_book)

        target = [-1] * len(first_book)
        target += [0] * len(second_book)
        target += [o.price for o in third_book]

        bounds_first = [[0, o.amount] for o in first_book]
        bounds_second = [[0, o.amount] for o in second_book]
        bounds_third = [[0, o.amount] for o in third_book]

        bounds = bounds_first + bounds_second + bounds_third
        return Constraints(np.array(target), np.array(constraint_1), np.array(constraint_2), np.array(bounds))
