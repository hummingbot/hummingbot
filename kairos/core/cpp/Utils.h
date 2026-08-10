#ifndef _UTILS_H
#define _UTILS_H

#include <iterator>

template <typename T>
const T getIteratorFromReverseIterator(const std::reverse_iterator<T> rit) {
    T iterator_base = rit.base();
    iterator_base--;
    return iterator_base;
}

#endif
