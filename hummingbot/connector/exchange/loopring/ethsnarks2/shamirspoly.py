# Copyright (c) 2018 HarryR
# License: LGPL-3.0+

from .field import FQ


def shamirs_poly(x, a):
    assert isinstance(a, (list,tuple))
    assert len(a) >= 2
    assert isinstance(x, FQ)

    result = a[0]
    x_pow_i = x

    for i, a_i in list(enumerate(a))[1:]:
        assert isinstance(a_i, FQ)
        ai_mul_xi = a_i * x_pow_i
        result = result + ai_mul_xi
        x_pow_i *= x

    return result


def lagrange(points, x):
    # Borrowed from: https://gist.github.com/melpomene/2482930
    total = 0
    n = len(points)
    for i in range(n):
        xi, yi = points[i]
        assert isinstance(xi, FQ)
        assert isinstance(yi, FQ)
        def g(i, n):
            tot_mul = 1
            for j in range(n):
                if i == j:
                    continue
                xj, yj = points[j]
                tot_mul = tot_mul * ( (x - xj) // (xi - xj) )
            return tot_mul
        coefficient = g(i, n)
        total = total + (yi * coefficient)
    return total


def inverse_lagrange(points, y):
    x = 0
    for i, (x_i, y_i) in enumerate(points):
        for j, (x_j, y_j) in enumerate(points):
            if j != i:
                x_i = x_i * (y - y_j) / (y_i - y_j)
        x += x_i 
    return x
