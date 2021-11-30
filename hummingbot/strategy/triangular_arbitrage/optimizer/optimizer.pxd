# distutils: language=c++


cdef class Optimizer():
    cdef:
        object _constraint_solver

    cdef object c_optimize(self, str sequence_type, object pri_book, object sec_book, object ter_book, object fee)
        
