from abc import ABC, abstractmethod
from math import exp, log
from typing import List


class Distribution(ABC):
    @abstractmethod
    def distribute(self, n_levels: int, params: dict) -> List[float]:
        """
        Distribute values based on certain criteria.

        Args:
            n_levels: Number of levels or values to generate.
            params: Additional parameters required for distribution.

        Returns:
            List[float]: List of distributed values.
        """
        pass


class LinearDistribution(Distribution):
    def distribute(self, n_levels: int, params: dict) -> List[float]:
        """Generate a linear distribution between start and end."""
        start = params.get('start', 0)
        end = params.get('end', 1)
        return [start + (end - start) * i / (n_levels - 1) for i in range(n_levels)]


class ExponentialDistribution(Distribution):
    def distribute(self, n_levels: int, params: dict) -> List[float]:
        """Generate an exponential distribution."""
        a = params.get('initial_value', 1)
        b = params.get('base', 2)
        return [a * b ** i for i in range(n_levels)]


class LogarithmicDistribution(Distribution):
    def distribute(self, n_levels: int, params: dict) -> List[float]:
        """Generate a logarithmic distribution."""
        base = params.get('base', exp(1))  # exp(1) gives the natural number 'e'
        scaling_factor = params.get('scaling_factor', 1)
        initial_value = params.get('initial_value', 0.4)  # Set the default initial value to 0.4

        # Adjust the function to start from the initial_value.
        translation = initial_value - scaling_factor * log(2, base)

        # Since log(1) = 0 for any base, starting from 2 to avoid negative or zero values.
        return [scaling_factor * log(i + 2, base) + translation for i in range(n_levels)]


class GeometricDistribution(Distribution):
    def distribute(self, n_levels: int, params: dict) -> List[float]:
        """Generate a geometric distribution."""
        initial_value = params.get('initial_value', 1)
        ratio = params.get('ratio', 0.5)
        if not (0 < ratio < 1):  # Ensuring the ratio is between 0 and 1
            raise ValueError("Ratio for geometric distribution should be between 0 and 1.")

        return [initial_value * (ratio ** i) for i in range(n_levels)]


class FibonacciDistribution(Distribution):
    def distribute(self, n_levels: int, params: dict) -> List[float]:
        """Generate a fibonacci distribution."""
        fib_sequence = [1, 1]
        for i in range(2, n_levels):
            fib_sequence.append(fib_sequence[-1] + fib_sequence[-2])
        return fib_sequence[:n_levels]


class DistributionFactory:
    @staticmethod
    def create_distribution(method: str) -> Distribution:
        """
        Factory method to return a distribution instance based on method type.

        Args:
            method: The method or type of distribution.

        Returns:
            Distribution: An instance of the specified distribution.

        Raises:
            ValueError: If the method is not supported.
        """
        if method == 'linear':
            return LinearDistribution()
        elif method == 'exponential':
            return ExponentialDistribution()
        elif method == 'fibonacci':
            return FibonacciDistribution()
        elif method == 'logarithmic':
            return LogarithmicDistribution()
        elif method == 'geometric':
            return GeometricDistribution()
        else:
            raise ValueError(f"Unsupported distribution method: {method}")
