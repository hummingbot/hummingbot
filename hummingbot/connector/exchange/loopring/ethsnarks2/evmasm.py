# Copyright (c) 2018 Jordi Baylina
# Copyright (c) 2019 Harry Roberts
# License: LGPL-3.0+
#
# Based on: https://github.com/iden3/circomlib/blob/master/src/evmasm.js

from binascii import unhexlify
from collections import defaultdict

class _opcode(object):
	extra = None
	def __init__(self, code, extra=None):
		self._code = code
		if not isinstance(extra, (bytes, bytearray)):
			assert extra is None
		self.extra = extra

	def data(self):
		extra = self.extra if self.extra is not None else b''
		return bytes([self._code]) + extra

	def __call__(self):
		return self

class LABEL(_opcode):
	_code = 0x5b
	def __init__(self, name):
		assert isinstance(name, (str, bytes, bytearray))
		self.name = name

def _encode_offset(offset):
	return bytes([offset >> 16, (offset >> 8) & 0xFF, offset & 0xFF])

class PUSHLABEL(_opcode):
	def __init__(self, target):
		self.target = target

	def data(self, offset):
		assert offset >= 0 and offset < (1<<24)
		return bytes([0x62]) + _encode_offset(offset)

class JMP(PUSHLABEL):
	_code = 0x56

	def __init__(self, target=None):
		super(JMP, self).__init__(target)

	def data(self, offset=None):
		if offset is not None:
			return super(JMP, self).data(offset) + bytes([self._code])
		return bytes([self._code])

class JMPI(JMP):
	_code = 0x57

def DUP(n):
	if n < 0 or n >= 16:
		raise ValueError("DUP must be 0 to 16")
	return _opcode(0x80 + n)

def SWAP(n):
	if n < 0 or n >= 16:
		raise ValueError("SWAP must be 0 to 16")
	return _opcode(0x8f + n)

def PUSH(data):
	if isinstance(data, int):
		if data < 0 or data >= ((1<<256)-1):
			raise ValueError("Push value out of range: %r" % (data,))
		hexdata = hex(data)[2:]
		if (len(hexdata) % 2) != 0:
			hexdata = '0' + hexdata
		data = unhexlify(hexdata)
	assert isinstance(data, (bytes, bytearray))
	return _opcode(0x5F + len(data), data)

STOP = _opcode(0x00)
ADD = _opcode(0x01)
MUL = _opcode(0x02)
SUB = _opcode(0x03)
DIV = _opcode(0x04)
SDIV = _opcode(0x05)
MOD = _opcode(0x06)
SMOD = _opcode(0x07)
ADDMOD = _opcode(0x08)
MULMOD = _opcode(0x09)

EXP = _opcode(0x0a)
SIGNEXTEND = _opcode(0x0b)
LT = _opcode(0x10)
GT = _opcode(0x11)
SLT = _opcode(0x12)
SGT = _opcode(0x13)
EQ = _opcode(0x14)
ISZERO = _opcode(0x15)
AND = _opcode(0x16)
OR = _opcode(0x17)
SHOR = _opcode(0x18)
NOT = _opcode(0x19)
BYTE = _opcode(0x1a)
KECCAK = _opcode(0x20)
SHA3 = _opcode(0x20)

ADDRESS = _opcode(0x30)
BALANCE = _opcode(0x31)
ORIGIN = _opcode(0x32)
CALLER = _opcode(0x33)
CALLVALUE = _opcode(0x34)
CALLDATALOAD = _opcode(0x35)
CALLDATASIZE = _opcode(0x36)
CALLDATACOPY = _opcode(0x37)
CODESIZE = _opcode(0x38)
CODECOPY = _opcode(0x39)
GASPRICE = _opcode(0x3a)
EXTCODESIZE = _opcode(0x3b)
EXTCODECOPY = _opcode(0x3c)
RETURNDATASIZE = _opcode(0x3d)
RETURNDATACOPY = _opcode(0x3e)

BLOCKHASH = _opcode(0x40)
COINBASE = _opcode(0x41)
TIMESTAMP = _opcode(0x42)
NUMBER = _opcode(0x43)
DIFFICULTY = _opcode(0x44)
GASLIMIT = _opcode(0x45)

POP = _opcode(0x50)
MLOAD = _opcode(0x51)
MSTORE = _opcode(0x52)
MSTORE8 = _opcode(0x53)
SLOAD = _opcode(0x54)
SSTORE = _opcode(0x55)
PC = _opcode(0x58)
MSIZE = _opcode(0x59)
GAS = _opcode(0x5a)

LOG0 = _opcode(0xa0)
LOG1 = _opcode(0xa1)
LOG2 = _opcode(0xa2)
LOG3 = _opcode(0xa3)
LOG4 = _opcode(0xa4)

CREATE = _opcode(0xf0)
CALL = _opcode(0xf1)
CALLCODE = _opcode(0xf2)
RETURN = _opcode(0xf3)
DELEGATECALL = _opcode(0xf4)
STATICCALL = _opcode(0xfa)
REVERT = _opcode(0xfd)
INVALID = _opcode(0xfe)
SELFDESTRUCT = _opcode(0xff)

class Codegen(object):
	def __init__(self, code=None):
		self.code = bytearray()
		self._labels = dict()
		self._jumps = defaultdict(list)
		if code is not None:
			self.append(code)

	def createTxData(self):
		if len(self._jumps):
			raise RuntimeError("Pending labels: " + ','.join(self._jumps.keys()))

		return type(self)([
			PUSH(len(self.code)),  # length of code being deployed
			DUP(0),
			DUP(0),
			CODESIZE,              # total length
			SUB,                   # codeOffset = (total_length - body_length)
			PUSH(0),               # memOffset
			CODECOPY,
			PUSH(0),
			RETURN
		]).code + self.code

	def append(self, *args):
		for arg in args:
			if isinstance(arg, (list, tuple)):
				# Allow x.append([opcode, opcode, ...])
				arg = self.append(*arg)
				continue
			if isinstance(arg, PUSHLABEL):
				offset = None
				if arg.target is not None:
					if arg.target not in self._labels:
						self._jumps[arg.target].append(len(self.code))
						offset = 0   # jump destination filled-in later
					else:
						offset = self._labels[arg.target]
				from binascii import hexlify
				self.code += arg.data(offset)
			elif isinstance(arg, LABEL):
				if arg.name in self._labels:
					raise RuntimeError("Cannot re-define label %r" % (arg.name,))
				self._labels[arg.name] = len(self.code)
				if arg.name in self._jumps:
					for jump in self._jumps[arg.name]:
						self.code[jump+1:jump+4] = _encode_offset(len(self.code))
					del self._jumps[arg.name]
					self.code += arg.data()
			elif isinstance(arg, _opcode):
				self.code += arg.data()
			else:
				raise RuntimeError("Unknown opcode %r" % (arg,))
