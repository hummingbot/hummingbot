from decimal import Decimal
from math import exp, log
from typing import List


class Distributions:
    """
    A utility class containing methods to generate various types of numeric distributions.
    """

    @classmethod
    def linear(cls, n_levels: int, start: float = 0.0, end: float = 1.0) -> List[Decimal]:
        """
        Generate a linear sequence of spreads.

        Parameters:
        - n_levels: The number of spread levels to be generated.
        - start: The starting value of the sequence.
        - end: The ending value of the sequence.

        Returns:
        List[Decimal]: A list containing the generated linear sequence.
        """
        if n_levels == 1:
            return [Decimal(start)]

        return [Decimal(start) + (Decimal(end) - Decimal(start)) * Decimal(i) / (Decimal(n_levels) - 1) for i in range(n_levels)]

    @classmethod
    def fibonacci(cls, n_levels: int, start: float = 0.01) -> List[Decimal]:
        """
        Generate a Fibonacci sequence of spreads represented as percentages.

        The Fibonacci sequence is a series of numbers in which each number (Fibonacci number)
        is the sum of the two preceding ones. In this implementation, the sequence starts with
        the provided initial_value (represented as a percentage) and the value derived by adding
        the initial_value to itself as the first two terms. Each subsequent term is derived by
        adding the last two terms of the sequence.

        Parameters:
        - n_levels (int): The number of spread levels to be generated.
        - initial_value (float, default=0.01): The value from which the Fibonacci sequence will start,
          represented as a percentage. Default is 1%.

        Returns:
        List[Decimal]: A list containing the generated Fibonacci sequence of spreads, represented as percentages.

        Example:
        If initial_value=0.01 and n_levels=5, the sequence would represent: [1%, 2%, 3%, 5%, 8%]
        """

        if n_levels == 1:
            return [Decimal(start)]

        fib_sequence = [Decimal(start), Decimal(start) * 2]
        for i in range(2, n_levels):
            fib_sequence.append(fib_sequence[-1] + fib_sequence[-2])
        return fib_sequence[:n_levels]

    @classmethod
    def logarithmic(cls, n_levels: int, base: float = exp(1), scaling_factor: float = 1.0,
                    start: float = 0.4) -> List[Decimal]:
        """
        Generate a logarithmic sequence of spreads.

        Parameters:
        - n_levels: The number of spread levels to be generated.
        - base: The base value for the logarithm. Default is Euler's number.
        - scaling_factor: The factor to scale the logarithmic value.
        - initial_value: Initial value for translation.

        Returns:
        List[Decimal]: A list containing the generated logarithmic sequence.
        """
        translation = Decimal(start) - Decimal(scaling_factor) * Decimal(log(2, base))
        return [Decimal(scaling_factor) * Decimal(log(i + 2, base)) + translation for i in range(n_levels)]

    @classmethod
    def arithmetic(cls, n_levels: int, start: float, step: float) -> List[Decimal]:
        """
        Generate an arithmetic sequence of spreads.

        Parameters:
        - n_levels: The number of spread levels to be generated.
        - start: The starting value of the sequence.
        - increment: The constant value to be added in each iteration.

        Returns:
        List[Decimal]: A list containing the generated arithmetic sequence.
        """
        return [Decimal(start) + i * Decimal(step) for i in range(n_levels)]

    @classmethod
    def geometric(cls, n_levels: int, start: float, ratio: float) -> List[Decimal]:
        """
        Generate a geometric sequence of spreads.

        Parameters:
        - n_levels: The number of spread levels to be generated.
        - start: The starting value of the sequence.
        - ratio: The ratio to multiply the current value in each iteration. Should be greater than 1 for increasing sequence.

        Returns:
        List[Decimal]: A list containing the generated geometric sequence.
        """
        if ratio <= 1:
            raise ValueError(
                "Ratio for modified geometric distribution should be greater than 1 for increasing spreads.")

        return [Decimal(start) * Decimal(ratio) ** Decimal(i) for i in range(n_levels)]
