from .order_sizing_delegate cimport OrderSizingDelegate


cdef class InventorySkewSingleSizeSizingDelegate(OrderSizingDelegate):
    cdef:
        double _order_size
        double _inventory_target_base_percent
