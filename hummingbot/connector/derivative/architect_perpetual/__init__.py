"""Architect perpetual connector modules.

NOTE: This package intentionally does not import the full connector class at import time.
Some Hummingbot connector bases rely on cython-compiled extensions that are not available
in the unit-test environment used for this bounty.
"""
