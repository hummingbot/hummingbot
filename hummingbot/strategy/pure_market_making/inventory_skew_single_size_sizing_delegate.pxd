from .order_sizing_delegate cimport OrderSizingDelegate


cdef class InventorySkewSingleSizeSizingDelegate(OrderSizingDelegate):
    cdef:
        object _order_size
        object _inventory_target_base_percent
