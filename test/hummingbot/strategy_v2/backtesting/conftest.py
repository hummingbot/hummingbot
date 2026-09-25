"""
Patch broken optional dependencies so backtesting tests can import
without requiring every connector's SDK to be perfectly installed.
"""
try:
    from pyinjective.proto.injective.stream.v2 import query_pb2
    if not hasattr(query_pb2, 'OrderFailuresFilter'):
        query_pb2.OrderFailuresFilter = type('OrderFailuresFilter', (), {})
except ImportError:
    pass
