import struct

ALL_BYTES = tuple(struct.pack("B", i) for i in range(256))
