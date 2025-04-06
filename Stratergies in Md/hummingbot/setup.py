from setuptools import setup, find_packages

setup(
    name="adaptive_market_making",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.20.0",
        "pandas>=1.3.0",
        "scipy>=1.7.0",
        "matplotlib>=3.4.0",
        "scikit-learn>=0.24.0",
        "pydantic>=1.8.0",
        "ta>=0.7.0",
        "PyYAML>=6.0.0",
        "joblib>=1.1.0",
        "ccxt>=2.0.0",
        "statsmodels>=0.13.0",
    ],
    extras_require={
        "ml": [
            "tensorflow>=2.8.0",
            "torch>=1.10.0",
            "tensorboard>=2.8.0",
        ],
    },
    author="Trading Strategy Developer",
    author_email="developer@example.com",
    description="Adaptive Market Making Strategy for Hummingbot",
    keywords="hummingbot, trading, crypto, market-making, strategy",
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
) 