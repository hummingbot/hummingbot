# distutils: language=c++

cdef extern from "<iterator>" namespace "std" nogil:
    cdef cppclass reverse_iterator[T]:
        pass

cdef extern from "cpp/Utils.h":
    cdef const T getIteratorFromReverseIterator[T](const reverse_iterator[T] rit)
