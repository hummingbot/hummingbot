/*
   Copyright (c) 2008 - 2025, Ilan Schnell; All Rights Reserved
   bitarray is published under the PSF license.

   Author: Ilan Schnell
*/
#define BITARRAY_VERSION  "3.3.1"

#ifdef STDC_HEADERS
#  include <stddef.h>
#else
#  ifdef HAVE_SYS_TYPES_H
#    include <sys/types.h>      /* For size_t */
#  endif
#endif

/* Compatibility with Visual Studio 2013 and older which don't support
   the inline keyword in C (only in C++): use __inline instead.
   (copied from pythoncapi_compat.h) */
#if (defined(_MSC_VER) && _MSC_VER < 1900 \
     && !defined(__cplusplus) && !defined(inline))
#define inline __inline
#endif

#ifdef _MSC_VER
#include <intrin.h>    /* For _byteswap_uint64() */
#endif

/* --- definitions specific to Python --- */

/* Py_UNREACHABLE was introduced in Python 3.7 */
#ifndef Py_UNREACHABLE
#define Py_UNREACHABLE() abort()
#endif

/* --- bitarrayobject --- */

/* .ob_size is the buffer size (in bytes), not the number of elements.
   The number of elements (bits) is .nbits. */
typedef struct {
    PyObject_VAR_HEAD
    char *ob_item;              /* buffer */
    Py_ssize_t allocated;       /* allocated buffer size (in bytes) */
    Py_ssize_t nbits;           /* length of bitarray, i.e. elements */
    int endian;                 /* bit-endianness of bitarray */
    int ob_exports;             /* how many buffer exports */
    PyObject *weakreflist;      /* list of weak references */
    Py_buffer *buffer;          /* used when importing a buffer */
    int readonly;               /* buffer is readonly */
} bitarrayobject;

/* --- bit-endianness --- */
#define ENDIAN_LITTLE  0
#define ENDIAN_BIG     1

#define IS_LE(self)  ((self)->endian == ENDIAN_LITTLE)
#define IS_BE(self)  ((self)->endian == ENDIAN_BIG)

/* endianness as string */
#define ENDIAN_STR(endian)  ((endian) == ENDIAN_LITTLE ? "little" : "big")

/* number of pad bits */
#define PADBITS(self)  ((8 - (self)->nbits % 8) % 8)

/* number of bytes necessary to store given nunmber of bits */
#define BYTES(bits)  (((bits) + 7) >> 3)

/* we're not using bitmask_table here, as it is actually slower */
#define BITMASK(self, i)  (((char) 1) << ((self)->endian == ENDIAN_LITTLE ? \
                                          ((i) % 8) : (7 - (i) % 8)))

/* buffer as uint64 array */
#define WBUFF(self)  ((uint64_t *) (self)->ob_item)

/* assert that .nbits is in agreement with .ob_size */
#define assert_nbits(self)  assert(BYTES((self)->nbits) == Py_SIZE(self))

/* assert byte index is in range */
#define assert_byte_in_range(self, j)  \
    assert(self->ob_item && 0 <= (j) && (j) < Py_SIZE(self))

/* ------------ low level access to bits in bitarrayobject ------------- */

static inline int
getbit(bitarrayobject *self, Py_ssize_t i)
{
    assert_nbits(self);
    assert(0 <= i && i < self->nbits);
    return self->ob_item[i >> 3] & BITMASK(self, i) ? 1 : 0;
}

static inline void
setbit(bitarrayobject *self, Py_ssize_t i, int vi)
{
    char *cp, mask;

    assert_nbits(self);
    assert(0 <= i && i < self->nbits);
    assert(self->readonly == 0);

    mask = BITMASK(self, i);
    cp = self->ob_item + (i >> 3);
    if (vi)
        *cp |= mask;
    else
        *cp &= ~mask;
}

static const char bitmask_table[2][8] = {
    {0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80},  /* little endian */
    {0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01},  /* big endian */
};

/* character with n leading ones is: ones_table[endian][n] */
static const char ones_table[2][8] = {
    {0x00, 0x01, 0x03, 0x07, 0x0f, 0x1f, 0x3f, 0x7f},  /* little endian */
    {0x00, 0x80, 0xc0, 0xe0, 0xf0, 0xf8, 0xfc, 0xfe},  /* big endian */
};

/* Return last byte in buffer with pad bits zeroed out.
   If the length of the bitarray is a multiple of 8 (which includes an empty
   bitarray), 0 is returned. */
static inline char
zlc(bitarrayobject *self)       /* zlc = zeroed last char */
{
    const int r = self->nbits % 8;     /* index into mask table */

    if (r == 0)
        return 0;
    return self->ob_item[Py_SIZE(self) - 1] & ones_table[IS_BE(self)][r];
}

/* Return a uint64_t word representing the last (up to 63) remaining bits
   of the buffer.  All missing bytes (to complete the word) and padbits are
   treated as zeros.
   If the length of the bitarray is a multiple of 64 (which includes an empty
   bitarray), 0 is returned. */
static inline uint64_t
zlw(bitarrayobject *self)       /* zlw = zeroed last word */
{
    const Py_ssize_t nbits = self->nbits;
    const Py_ssize_t nw = 8 * (nbits / 64);  /* bytes in complete words */
    const int nr = (nbits % 64) / 8;         /* complete remaining bytes */
    uint64_t res = 0;

    assert(nw + nr == nbits / 8 && nw + nr <= Py_SIZE(self));
    memcpy((char *) &res, self->ob_item + nw, (size_t) nr);
    if (nbits % 8)
        *(((char *) &res) + nr) = zlc(self);

    assert(nbits % 64 || res == 0);
    return res;
}

/* unless buffer is readonly, zero out pad bits - self->nbits is unchanged */
static inline void
set_padbits(bitarrayobject *self)
{
    if (self->readonly == 0) {
        int r = self->nbits % 8;     /* index into mask table */
        if (r)
            self->ob_item[Py_SIZE(self) - 1] &= ones_table[IS_BE(self)][r];
    }
}

/* population count - number of 1's in uint64 */
static inline int
popcnt_64(uint64_t x)
{
#if (defined(__clang__) || defined(__GNUC__))
    return __builtin_popcountll(x);
#else
    /* https://en.wikipedia.org/wiki/Hamming_weight popcount64c */
    const uint64_t m1  = 0x5555555555555555;
    const uint64_t m2  = 0x3333333333333333;
    const uint64_t m4  = 0x0f0f0f0f0f0f0f0f;
    const uint64_t h01 = 0x0101010101010101;

    x -= (x >> 1) & m1;
    x = (x & m2) + ((x >> 2) & m2);
    x = (x + (x >> 4)) & m4;
    return (x * h01) >> 56;
#endif
}

static inline int
parity_64(uint64_t x)
{
#if (defined(__clang__) || defined(__GNUC__))
    return __builtin_parityll(x);
#else
    int i;
    for (i = 32; i > 0; i /= 2)
        x ^= x >> i;
    return x & 1;
#endif
}

static inline uint64_t
builtin_bswap64(uint64_t word)
{
#if (defined(__clang__) ||                                                 \
      (defined(__GNUC__)                                                   \
        && ((__GNUC__ >= 5) || (__GNUC__ == 4) && (__GNUC_MINOR__ >= 3))))
    /* __builtin_bswap64() is available since GCC 4.3 */
#  define HAVE_BUILTIN_BSWAP64  1
    return __builtin_bswap64(word);
#elif defined(_MSC_VER)
#  define HAVE_BUILTIN_BSWAP64  1
    return _byteswap_uint64(word);
#else
#  define HAVE_BUILTIN_BSWAP64  0
    Py_UNREACHABLE();
#endif
}

/* Return distance [0..3] to next aligned pointer.
   While on modern compilers uint64_t pointers may be misaligned, it may
   cause problems on older ones.  Moreover, it may lead to slowdown (even
   on modern compilers). */
static inline int
to_aligned(void *p)
{
    int r = ((uintptr_t) p) % 4;
    return r ? 4 - r : 0;
}

/* population count of n words starting from at uint64_t pointer w */
static inline Py_ssize_t
popcnt_words(uint64_t *w, Py_ssize_t n)
{
    Py_ssize_t cnt = 0;

    assert(n >= 0 && ((uintptr_t) w) % 4 == 0);
    while (n--)
        cnt += popcnt_64(*w++);
    return cnt;
}

/* adjust index in a manner consistent with the handling of normal slices */
static inline void
adjust_index(Py_ssize_t length, Py_ssize_t *i, Py_ssize_t step)
{
    if (*i < 0) {
        *i += length;
        if (*i < 0)
            *i = (step < 0) ? -1 : 0;
    }
    else if (*i >= length) {
        *i = (step < 0) ? length - 1 : length;
    }
}

/* same as PySlice_AdjustIndices() which was introduced in Python 3.6.1 */
static inline Py_ssize_t
adjust_indices(Py_ssize_t length, Py_ssize_t *start, Py_ssize_t *stop,
               Py_ssize_t step)
{
#if PY_VERSION_HEX >= 0x03060100
    return PySlice_AdjustIndices(length, start, stop, step);
#else
    assert(step != 0);
    adjust_index(length, start, step);
    adjust_index(length, stop, step);
    /*
      a / b does integer division.  If either a or b is negative, the result
      depends on the compiler (rounding can go toward 0 or negative infinity).
      Therefore, we are careful that both a and b are always positive.
    */
    if (step < 0) {
        if (*stop < *start)
            return (*start - *stop - 1) / (-step) + 1;
    }
    else {
        if (*start < *stop)
            return (*stop - *start - 1) / step + 1;
    }
    return 0;
#endif
}

/* adjust slice parameters such that step is always positive; produces
   simpler loops over elements when their order is irrelevant */
static inline void
adjust_step_positive(Py_ssize_t slicelength,
                     Py_ssize_t *start, Py_ssize_t *stop, Py_ssize_t *step)
{
    if (*step < 0) {
        *stop = *start + 1;
        *start = *stop + *step * (slicelength - 1) - 1;
        *step = -(*step);
    }
    assert(*start >= 0 && *stop >= 0 && *step > 0 && slicelength >= 0);
    /* slicelength == 0 implies stop <= start */
    assert(slicelength != 0 || *stop <= *start);
    /* step == 1 and slicelength != 0 implies stop - start == slicelength */
    assert(*step != 1 || slicelength == 0 || *stop - *start == slicelength);
}

/* convert Python object to C int and set value at address -
   return 1 on success, 0 on failure (and set exception) */
static inline int
conv_pybit(PyObject *value, int *vi)
{
    Py_ssize_t n;

    n = PyNumber_AsSsize_t(value, NULL);
    if (n == -1 && PyErr_Occurred())
        return 0;

    if (n >> 1) {
        PyErr_Format(PyExc_ValueError, "bit must be 0 or 1, got %zd", n);
        return 0;
    }
    *vi = (int) n;
    return 1;
}

/* Return 0 if bitarrays have equal length and bit-endianness.
   Otherwise, set exception and return -1. */
static inline int
ensure_eq_size_endian(bitarrayobject *a, bitarrayobject *b)
{
    if (a->nbits != b->nbits) {
        PyErr_SetString(PyExc_ValueError,
                        "bitarrays of equal length expected");
        return -1;
    }
    if (a->endian != b->endian) {
        PyErr_SetString(PyExc_ValueError,
                        "bitarrays of equal bit-endianness expected");
        return -1;
    }
    return 0;
}
