import math
import bitstring
from math import floor, log2
from struct import pack

from .jubjub import Point, EtecPoint, JUBJUB_L, JUBJUB_C


MAX_SEGMENT_BITS = floor(log2(JUBJUB_L))
MAX_SEGMENT_BYTES = MAX_SEGMENT_BITS // 8


def pedersen_hash_basepoint(name, i):
	"""
	Create a base point for use with the windowed pedersen hash function.
	The name and sequence numbers are used a unique identifier.
	Then HashToPoint is run on the name+seq to get the base point.
	"""
	if not isinstance(name, bytes):
		if isinstance(name, str):
			name = name.encode('ascii')
		else:
			raise TypeError("Name not bytes")
	if i < 0 or i > 0xFFFF:
		raise ValueError("Sequence number invalid")
	if len(name) > 28:
		raise ValueError("Name too long")
	data = b"%-28s%04X" % (name, i)
	return Point.from_hash(data).as_etec()


def pedersen_hash_windows(name, windows):
	# 62 is defined in the ZCash Sapling Specification, Theorem 5.4.1
	# See: https://github.com/HarryR/ethsnarks/issues/121#issuecomment-499441289
	n_windows = 62
	result = EtecPoint.infinity()
	for j, window in enumerate(windows):
		if j % n_windows == 0:
			current = pedersen_hash_basepoint(name, j//n_windows)
		j = j % n_windows
		if j != 0:
			current = current.double().double().double().double()
		segment = current * ((window & 0b11) + 1)
		if window > 0b11:
			segment = segment.neg()
		result += segment
	return result.as_point()


def pedersen_hash_bits(name, bits):
	# Split into 3 bit windows
	if isinstance(bits, bitstring.BitArray):
		bits = bits.bin
	windows = [int(bits[i:i+3][::-1], 2) for i in range(0, len(bits), 3)]
	assert len(windows) > 0

	# Hash resulting windows
	return pedersen_hash_windows(name, windows)


def pedersen_hash_bytes(name, data):
	"""
	Hashes a sequence of bits (the message) into a point.

	The message is split into 3-bit windows after padding (via append)
	to `len(data.bits) = 0 mod 3`
	"""
	assert isinstance(data, bytes)
	assert len(data) > 0

	# Decode bytes to octets of binary bits
	bits = ''.join([bin(_)[2:].rjust(8, '0') for _ in data])

	return pedersen_hash_bits(name, bits)


def pedersen_hash_scalars(name, *scalars):
	"""
	Calculates a pedersen hash of scalars in the same way that zCash
	is doing it according to: ... of their spec.
	It is looking up 3bit chunks in a 2bit table (3rd bit denotes sign).

	E.g:

		(b2, b1, b0) = (1,0,1) would look up first element and negate it.

	Row i of the lookup table contains:

		[2**4i * base, 2 * 2**4i * base, 3 * 2**4i * base, 3 * 2**4i * base]

	E.g:

		row_0 = [base, 2*base, 3*base, 4*base]
		row_1 = [16*base, 32*base, 48*base, 64*base]
		row_2 = [256*base, 512*base, 768*base, 1024*base]

	Following Theorem 5.4.1 of the zCash Sapling specification, for baby jub_jub
	we need a new base point every 62 windows. We will therefore have multiple
	tables with 62 rows each.
	"""
	windows = []
	for i, s in enumerate(scalars):
		windows += list((s >> i) & 0b111 for i in range(0,s.bit_length(),3))
	return pedersen_hash_windows(name, windows)
