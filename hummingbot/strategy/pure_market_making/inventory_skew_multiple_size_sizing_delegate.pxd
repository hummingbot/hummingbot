from .order_sizing_delegate cimport OrderSizingDelegate


cdef class InventorySkewMultipleSizeSizingDelegate(OrderSizingDelegate):
    cdef:
        object _order_step_size
        object _order_start_size
        int _number_of_orders
        object _inventory_target_base_percent
