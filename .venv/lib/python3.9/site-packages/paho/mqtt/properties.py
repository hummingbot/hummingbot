"""
*******************************************************************
  Copyright (c) 2017, 2019 IBM Corp.

  All rights reserved. This program and the accompanying materials
  are made available under the terms of the Eclipse Public License v2.0
  and Eclipse Distribution License v1.0 which accompany this distribution.

  The Eclipse Public License is available at
     http://www.eclipse.org/legal/epl-v10.html
  and the Eclipse Distribution License is available at
    http://www.eclipse.org/org/documents/edl-v10.php.

  Contributors:
     Ian Craggs - initial implementation and/or documentation
*******************************************************************
"""

import struct
import sys

from .packettypes import PacketTypes


class MQTTException(Exception):
    pass


class MalformedPacket(MQTTException):
    pass


def writeInt16(length):
    # serialize a 16 bit integer to network format
    return bytearray(struct.pack("!H", length))


def readInt16(buf):
    # deserialize a 16 bit integer from network format
    return struct.unpack("!H", buf[:2])[0]


def writeInt32(length):
    # serialize a 32 bit integer to network format
    return bytearray(struct.pack("!L", length))


def readInt32(buf):
    # deserialize a 32 bit integer from network format
    return struct.unpack("!L", buf[:4])[0]


def writeUTF(data):
    # data could be a string, or bytes.  If string, encode into bytes with utf-8
    if sys.version_info[0] < 3:
        data = bytearray(data, 'utf-8')
    else:
        data = data if type(data) == type(b"") else bytes(data, "utf-8")
    return writeInt16(len(data)) + data


def readUTF(buffer, maxlen):
    if maxlen >= 2:
        length = readInt16(buffer)
    else:
        raise MalformedPacket("Not enough data to read string length")
    maxlen -= 2
    if length > maxlen:
        raise MalformedPacket("Length delimited string too long")
    buf = buffer[2:2+length].decode("utf-8")
    # look for chars which are invalid for MQTT
    for c in buf: # look for D800-DFFF in the UTF string
        ord_c = ord(c)
        if ord_c >= 0xD800 and ord_c <= 0xDFFF:
            raise MalformedPacket("[MQTT-1.5.4-1] D800-DFFF found in UTF-8 data")
        if ord_c == 0x00: # look for null in the UTF string
            raise MalformedPacket("[MQTT-1.5.4-2] Null found in UTF-8 data")
        if ord_c == 0xFEFF:
            raise MalformedPacket("[MQTT-1.5.4-3] U+FEFF in UTF-8 data")
    return buf, length+2


def writeBytes(buffer):
    return writeInt16(len(buffer)) + buffer


def readBytes(buffer):
    length = readInt16(buffer)
    return buffer[2:2+length], length+2


class VariableByteIntegers:  # Variable Byte Integer
    """
    MQTT variable byte integer helper class.  Used
    in several places in MQTT v5.0 properties.

    """

    @staticmethod
    def encode(x):
        """
          Convert an integer 0 <= x <= 268435455 into multi-byte format.
          Returns the buffer convered from the integer.
        """
        assert 0 <= x <= 268435455
        buffer = b''
        while 1:
            digit = x % 128
            x //= 128
            if x > 0:
                digit |= 0x80
            if sys.version_info[0] >= 3:
                buffer += bytes([digit])
            else:
                buffer += bytes(chr(digit))
            if x == 0:
                break
        return buffer

    @staticmethod
    def decode(buffer):
        """
          Get the value of a multi-byte integer from a buffer
          Return the value, and the number of bytes used.

          [MQTT-1.5.5-1] the encoded value MUST use the minimum number of bytes necessary to represent the value
        """
        multiplier = 1
        value = 0
        bytes = 0
        while 1:
            bytes += 1
            digit = buffer[0]
            buffer = buffer[1:]
            value += (digit & 127) * multiplier
            if digit & 128 == 0:
                break
            multiplier *= 128
        return (value, bytes)


class Properties(object):
    """MQTT v5.0 properties class.

    See Properties.names for a list of accepted property names along with their numeric values.

    See Properties.properties for the data type of each property.

    Example of use:

        publish_properties = Properties(PacketTypes.PUBLISH)
        publish_properties.UserProperty = ("a", "2")
        publish_properties.UserProperty = ("c", "3")

    First the object is created with packet type as argument, no properties will be present at
    this point.  Then properties are added as attributes, the name of which is the string property
    name without the spaces.

    """

    def __init__(self, packetType):
        self.packetType = packetType
        self.types = ["Byte", "Two Byte Integer", "Four Byte Integer", "Variable Byte Integer",
                      "Binary Data", "UTF-8 Encoded String", "UTF-8 String Pair"]

        self.names = {
            "Payload Format Indicator": 1,
            "Message Expiry Interval": 2,
            "Content Type": 3,
            "Response Topic": 8,
            "Correlation Data": 9,
            "Subscription Identifier": 11,
            "Session Expiry Interval": 17,
            "Assigned Client Identifier": 18,
            "Server Keep Alive": 19,
            "Authentication Method": 21,
            "Authentication Data": 22,
            "Request Problem Information": 23,
            "Will Delay Interval": 24,
            "Request Response Information": 25,
            "Response Information": 26,
            "Server Reference": 28,
            "Reason String": 31,
            "Receive Maximum": 33,
            "Topic Alias Maximum": 34,
            "Topic Alias": 35,
            "Maximum QoS": 36,
            "Retain Available": 37,
            "User Property": 38,
            "Maximum Packet Size": 39,
            "Wildcard Subscription Available": 40,
            "Subscription Identifier Available": 41,
            "Shared Subscription Available": 42
        }

        self.properties = {
            # id:  type, packets
            # payload format indicator
            1: (self.types.index("Byte"), [PacketTypes.PUBLISH, PacketTypes.WILLMESSAGE]),
            2: (self.types.index("Four Byte Integer"), [PacketTypes.PUBLISH, PacketTypes.WILLMESSAGE]),
            3: (self.types.index("UTF-8 Encoded String"), [PacketTypes.PUBLISH, PacketTypes.WILLMESSAGE]),
            8: (self.types.index("UTF-8 Encoded String"), [PacketTypes.PUBLISH, PacketTypes.WILLMESSAGE]),
            9: (self.types.index("Binary Data"), [PacketTypes.PUBLISH, PacketTypes.WILLMESSAGE]),
            11: (self.types.index("Variable Byte Integer"),
                 [PacketTypes.PUBLISH, PacketTypes.SUBSCRIBE]),
            17: (self.types.index("Four Byte Integer"),
                 [PacketTypes.CONNECT, PacketTypes.CONNACK, PacketTypes.DISCONNECT]),
            18: (self.types.index("UTF-8 Encoded String"), [PacketTypes.CONNACK]),
            19: (self.types.index("Two Byte Integer"), [PacketTypes.CONNACK]),
            21: (self.types.index("UTF-8 Encoded String"),
                 [PacketTypes.CONNECT, PacketTypes.CONNACK, PacketTypes.AUTH]),
            22: (self.types.index("Binary Data"),
                 [PacketTypes.CONNECT, PacketTypes.CONNACK, PacketTypes.AUTH]),
            23: (self.types.index("Byte"),
                 [PacketTypes.CONNECT]),
            24: (self.types.index("Four Byte Integer"), [PacketTypes.WILLMESSAGE]),
            25: (self.types.index("Byte"), [PacketTypes.CONNECT]),
            26: (self.types.index("UTF-8 Encoded String"), [PacketTypes.CONNACK]),
            28: (self.types.index("UTF-8 Encoded String"),
                 [PacketTypes.CONNACK, PacketTypes.DISCONNECT]),
            31: (self.types.index("UTF-8 Encoded String"),
                 [PacketTypes.CONNACK, PacketTypes.PUBACK, PacketTypes.PUBREC,
                  PacketTypes.PUBREL, PacketTypes.PUBCOMP, PacketTypes.SUBACK,
                  PacketTypes.UNSUBACK, PacketTypes.DISCONNECT, PacketTypes.AUTH]),
            33: (self.types.index("Two Byte Integer"),
                 [PacketTypes.CONNECT, PacketTypes.CONNACK]),
            34: (self.types.index("Two Byte Integer"),
                 [PacketTypes.CONNECT, PacketTypes.CONNACK]),
            35: (self.types.index("Two Byte Integer"), [PacketTypes.PUBLISH]),
            36: (self.types.index("Byte"), [PacketTypes.CONNACK]),
            37: (self.types.index("Byte"), [PacketTypes.CONNACK]),
            38: (self.types.index("UTF-8 String Pair"),
                 [PacketTypes.CONNECT, PacketTypes.CONNACK,
                  PacketTypes.PUBLISH, PacketTypes.PUBACK,
                  PacketTypes.PUBREC, PacketTypes.PUBREL, PacketTypes.PUBCOMP,
                  PacketTypes.SUBSCRIBE, PacketTypes.SUBACK,
                  PacketTypes.UNSUBSCRIBE, PacketTypes.UNSUBACK,
                  PacketTypes.DISCONNECT, PacketTypes.AUTH, PacketTypes.WILLMESSAGE]),
            39: (self.types.index("Four Byte Integer"),
                 [PacketTypes.CONNECT, PacketTypes.CONNACK]),
            40: (self.types.index("Byte"), [PacketTypes.CONNACK]),
            41: (self.types.index("Byte"), [PacketTypes.CONNACK]),
            42: (self.types.index("Byte"), [PacketTypes.CONNACK]),
        }

    def allowsMultiple(self, compressedName):
        return self.getIdentFromName(compressedName) in [11, 38]

    def getIdentFromName(self, compressedName):
        # return the identifier corresponding to the property name
        result = -1
        for name in self.names.keys():
            if compressedName == name.replace(' ', ''):
                result = self.names[name]
                break
        return result

    def __setattr__(self, name, value):
        name = name.replace(' ', '')
        privateVars = ["packetType", "types", "names", "properties"]
        if name in privateVars:
            object.__setattr__(self, name, value)
        else:
            # the name could have spaces in, or not.  Remove spaces before assignment
            if name not in [aname.replace(' ', '') for aname in self.names.keys()]:
                raise MQTTException(
                    "Property name must be one of "+str(self.names.keys()))
            # check that this attribute applies to the packet type
            if self.packetType not in self.properties[self.getIdentFromName(name)][1]:
                raise MQTTException("Property %s does not apply to packet type %s"
                                    % (name, PacketTypes.Names[self.packetType]))

            # Check for forbidden values
            if type(value) != type([]):
                if name in ["ReceiveMaximum", "TopicAlias"] \
                        and (value < 1 or value > 65535):

                    raise MQTTException(
                        "%s property value must be in the range 1-65535" % (name))
                elif name in ["TopicAliasMaximum"] \
                        and (value < 0 or value > 65535):

                    raise MQTTException(
                        "%s property value must be in the range 0-65535" % (name))
                elif name in ["MaximumPacketSize", "SubscriptionIdentifier"] \
                        and (value < 1 or value > 268435455):

                    raise MQTTException(
                        "%s property value must be in the range 1-268435455" % (name))
                elif name in ["RequestResponseInformation", "RequestProblemInformation", "PayloadFormatIndicator"] \
                        and (value != 0 and value != 1):

                    raise MQTTException(
                        "%s property value must be 0 or 1" % (name))

            if self.allowsMultiple(name):
                if type(value) != type([]):
                    value = [value]
                if hasattr(self, name):
                    value = object.__getattribute__(self, name) + value
            object.__setattr__(self, name, value)

    def __str__(self):
        buffer = "["
        first = True
        for name in self.names.keys():
            compressedName = name.replace(' ', '')
            if hasattr(self, compressedName):
                if not first:
                    buffer += ", "
                buffer += compressedName + " : " + \
                    str(getattr(self, compressedName))
                first = False
        buffer += "]"
        return buffer

    def json(self):
        data = {}
        for name in self.names.keys():
            compressedName = name.replace(' ', '')
            if hasattr(self, compressedName):
                val = getattr(self, compressedName)
                if compressedName == 'CorrelationData' and isinstance(val, bytes):
                    data[compressedName] = val.hex()
                else:
                    data[compressedName] = val
        return data

    def isEmpty(self):
        rc = True
        for name in self.names.keys():
            compressedName = name.replace(' ', '')
            if hasattr(self, compressedName):
                rc = False
                break
        return rc

    def clear(self):
        for name in self.names.keys():
            compressedName = name.replace(' ', '')
            if hasattr(self, compressedName):
                delattr(self, compressedName)

    def writeProperty(self, identifier, type, value):
        buffer = b""
        buffer += VariableByteIntegers.encode(identifier)  # identifier
        if type == self.types.index("Byte"):  # value
            if sys.version_info[0] < 3:
                buffer += chr(value)
            else:
                buffer += bytes([value])
        elif type == self.types.index("Two Byte Integer"):
            buffer += writeInt16(value)
        elif type == self.types.index("Four Byte Integer"):
            buffer += writeInt32(value)
        elif type == self.types.index("Variable Byte Integer"):
            buffer += VariableByteIntegers.encode(value)
        elif type == self.types.index("Binary Data"):
            buffer += writeBytes(value)
        elif type == self.types.index("UTF-8 Encoded String"):
            buffer += writeUTF(value)
        elif type == self.types.index("UTF-8 String Pair"):
            buffer += writeUTF(value[0]) + writeUTF(value[1])
        return buffer

    def pack(self):
        # serialize properties into buffer for sending over network
        buffer = b""
        for name in self.names.keys():
            compressedName = name.replace(' ', '')
            if hasattr(self, compressedName):
                identifier = self.getIdentFromName(compressedName)
                attr_type = self.properties[identifier][0]
                if self.allowsMultiple(compressedName):
                    for prop in getattr(self, compressedName):
                        buffer += self.writeProperty(identifier,
                                                     attr_type, prop)
                else:
                    buffer += self.writeProperty(identifier, attr_type,
                                                 getattr(self, compressedName))
        return VariableByteIntegers.encode(len(buffer)) + buffer

    def readProperty(self, buffer, type, propslen):
        if type == self.types.index("Byte"):
            value = buffer[0]
            valuelen = 1
        elif type == self.types.index("Two Byte Integer"):
            value = readInt16(buffer)
            valuelen = 2
        elif type == self.types.index("Four Byte Integer"):
            value = readInt32(buffer)
            valuelen = 4
        elif type == self.types.index("Variable Byte Integer"):
            value, valuelen = VariableByteIntegers.decode(buffer)
        elif type == self.types.index("Binary Data"):
            value, valuelen = readBytes(buffer)
        elif type == self.types.index("UTF-8 Encoded String"):
            value, valuelen = readUTF(buffer, propslen)
        elif type == self.types.index("UTF-8 String Pair"):
            value, valuelen = readUTF(buffer, propslen)
            buffer = buffer[valuelen:]  # strip the bytes used by the value
            value1, valuelen1 = readUTF(buffer, propslen - valuelen)
            value = (value, value1)
            valuelen += valuelen1
        return value, valuelen

    def getNameFromIdent(self, identifier):
        rc = None
        for name in self.names:
            if self.names[name] == identifier:
                rc = name
        return rc

    def unpack(self, buffer):
        if sys.version_info[0] < 3:
            buffer = bytearray(buffer)
        self.clear()
        # deserialize properties into attributes from buffer received from network
        propslen, VBIlen = VariableByteIntegers.decode(buffer)
        buffer = buffer[VBIlen:]  # strip the bytes used by the VBI
        propslenleft = propslen
        while propslenleft > 0:  # properties length is 0 if there are none
            identifier, VBIlen2 = VariableByteIntegers.decode(
                buffer)  # property identifier
            buffer = buffer[VBIlen2:]  # strip the bytes used by the VBI
            propslenleft -= VBIlen2
            attr_type = self.properties[identifier][0]
            value, valuelen = self.readProperty(
                buffer, attr_type, propslenleft)
            buffer = buffer[valuelen:]  # strip the bytes used by the value
            propslenleft -= valuelen
            propname = self.getNameFromIdent(identifier)
            compressedName = propname.replace(' ', '')
            if not self.allowsMultiple(compressedName) and hasattr(self, compressedName):
                raise MQTTException(
                    "Property '%s' must not exist more than once" % property)
            setattr(self, propname, value)
        return self, propslen + VBIlen
