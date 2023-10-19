from math import exp, log
from typing import List


class Distribution:

    @classmethod
    def linear(cls, n_levels: int, start: float = 0, end: float = 1) -> List[float]:
        """
        Generate a linear distribution between start and end.

        Args:
            n_levels: Number of levels or values to generate.
            start: Starting value.
            end: Ending value.

        Returns:
            List[float]: List of linearly distributed values.
        """
        return [start + (end - start) * i / (n_levels - 1) for i in range(n_levels)]

    @classmethod
    def exponential(cls, n_levels: int, initial_value: float = 1, base: float = 2) -> List[float]:
        """
        Generate an exponential distribution.

        Args:
            n_levels: Number of levels or values to generate.
            initial_value: The value for the first level.
            base: The exponential base.

        Returns:
            List[float]: List of exponentially distributed values.
        """
        return [initial_value * base ** i for i in range(n_levels)]

    @classmethod
    def fibonacci(cls, n_levels: int) -> List[float]:
        """
        Generate a fibonacci distribution.

        Args:
            n_levels: Number of levels or values to generate.

        Returns:
            List[float]: List of Fibonacci sequence values.
        """
        fib_sequence = [1, 1]
        for i in range(2, n_levels):
            fib_sequence.append(fib_sequence[-1] + fib_sequence[-2])
        return fib_sequence[:n_levels]

    @classmethod
    def logarithmic(cls, n_levels: int, base: float = exp(1), scaling_factor: float = 1,
                    initial_value: float = 0.4) -> List[float]:
        """
        Generate a logarithmic distribution.

        Args:
            n_levels: Number of levels or values to generate.
            base: The logarithm base. Default is the natural number 'e'.
            scaling_factor: Multiplier for the logarithm value.
            initial_value: Starting value.

        Returns:
            List[float]: List of logarithmically distributed values.
        """
        translation = initial_value - scaling_factor * log(2, base)
        return [scaling_factor * log(i + 2, base) + translation for i in range(n_levels)]

    @classmethod
    def geometric(cls, n_levels: int, initial_value: float = 1, ratio: float = 0.5) -> List[float]:
        """
        Generate a geometric distribution.

        Args:
            n_levels: Number of levels or values to generate.
            initial_value: Starting value.
            ratio: The common ratio for the sequence.

        Returns:
            List[float]: List of geometrically distributed values.
        """
        if not (0 < ratio < 1):
            raise ValueError("Ratio for geometric distribution should be between 0 and 1.")
        return [initial_value * (ratio ** i) for i in range(n_levels)]
