from abc import ABC, abstractmethod
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
        base = params.get('base', 2)
        return [base ** i for i in range(n_levels)]


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
        else:
            raise ValueError(f"Unsupported distribution method: {method}")
