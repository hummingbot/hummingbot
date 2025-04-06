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

import sys

from .packettypes import PacketTypes


class ReasonCodes:
    """MQTT version 5.0 reason codes class.

    See ReasonCodes.names for a list of possible numeric values along with their
    names and the packets to which they apply.

    """

    def __init__(self, packetType, aName="Success", identifier=-1):
        """
        packetType: the type of the packet, such as PacketTypes.CONNECT that
            this reason code will be used with.  Some reason codes have different
            names for the same identifier when used a different packet type.

        aName: the String name of the reason code to be created.  Ignored
            if the identifier is set.

        identifier: an integer value of the reason code to be created.

        """

        self.packetType = packetType
        self.names = {
            0: {"Success": [PacketTypes.CONNACK, PacketTypes.PUBACK,
                            PacketTypes.PUBREC, PacketTypes.PUBREL, PacketTypes.PUBCOMP,
                            PacketTypes.UNSUBACK, PacketTypes.AUTH],
                "Normal disconnection": [PacketTypes.DISCONNECT],
                "Granted QoS 0": [PacketTypes.SUBACK]},
            1: {"Granted QoS 1": [PacketTypes.SUBACK]},
            2: {"Granted QoS 2": [PacketTypes.SUBACK]},
            4: {"Disconnect with will message": [PacketTypes.DISCONNECT]},
            16: {"No matching subscribers":
                 [PacketTypes.PUBACK, PacketTypes.PUBREC]},
            17: {"No subscription found": [PacketTypes.UNSUBACK]},
            24: {"Continue authentication": [PacketTypes.AUTH]},
            25: {"Re-authenticate": [PacketTypes.AUTH]},
            128: {"Unspecified error": [PacketTypes.CONNACK, PacketTypes.PUBACK,
                                        PacketTypes.PUBREC, PacketTypes.SUBACK, PacketTypes.UNSUBACK,
                                        PacketTypes.DISCONNECT], },
            129: {"Malformed packet":
                  [PacketTypes.CONNACK, PacketTypes.DISCONNECT]},
            130: {"Protocol error":
                  [PacketTypes.CONNACK, PacketTypes.DISCONNECT]},
            131: {"Implementation specific error": [PacketTypes.CONNACK,
                                                    PacketTypes.PUBACK, PacketTypes.PUBREC, PacketTypes.SUBACK,
                                                    PacketTypes.UNSUBACK, PacketTypes.DISCONNECT], },
            132: {"Unsupported protocol version": [PacketTypes.CONNACK]},
            133: {"Client identifier not valid": [PacketTypes.CONNACK]},
            134: {"Bad user name or password": [PacketTypes.CONNACK]},
            135: {"Not authorized": [PacketTypes.CONNACK, PacketTypes.PUBACK,
                                     PacketTypes.PUBREC, PacketTypes.SUBACK, PacketTypes.UNSUBACK,
                                     PacketTypes.DISCONNECT], },
            136: {"Server unavailable": [PacketTypes.CONNACK]},
            137: {"Server busy": [PacketTypes.CONNACK, PacketTypes.DISCONNECT]},
            138: {"Banned": [PacketTypes.CONNACK]},
            139: {"Server shutting down": [PacketTypes.DISCONNECT]},
            140: {"Bad authentication method":
                  [PacketTypes.CONNACK, PacketTypes.DISCONNECT]},
            141: {"Keep alive timeout": [PacketTypes.DISCONNECT]},
            142: {"Session taken over": [PacketTypes.DISCONNECT]},
            143: {"Topic filter invalid":
                  [PacketTypes.SUBACK, PacketTypes.UNSUBACK, PacketTypes.DISCONNECT]},
            144: {"Topic name invalid":
                  [PacketTypes.CONNACK, PacketTypes.PUBACK,
                   PacketTypes.PUBREC, PacketTypes.DISCONNECT]},
            145: {"Packet identifier in use":
                  [PacketTypes.PUBACK, PacketTypes.PUBREC,
                   PacketTypes.SUBACK, PacketTypes.UNSUBACK]},
            146: {"Packet identifier not found":
                  [PacketTypes.PUBREL, PacketTypes.PUBCOMP]},
            147: {"Receive maximum exceeded": [PacketTypes.DISCONNECT]},
            148: {"Topic alias invalid": [PacketTypes.DISCONNECT]},
            149: {"Packet too large": [PacketTypes.CONNACK, PacketTypes.DISCONNECT]},
            150: {"Message rate too high": [PacketTypes.DISCONNECT]},
            151: {"Quota exceeded": [PacketTypes.CONNACK, PacketTypes.PUBACK,
                                     PacketTypes.PUBREC, PacketTypes.SUBACK, PacketTypes.DISCONNECT], },
            152: {"Administrative action": [PacketTypes.DISCONNECT]},
            153: {"Payload format invalid":
                  [PacketTypes.PUBACK, PacketTypes.PUBREC, PacketTypes.DISCONNECT]},
            154: {"Retain not supported":
                  [PacketTypes.CONNACK, PacketTypes.DISCONNECT]},
            155: {"QoS not supported":
                  [PacketTypes.CONNACK, PacketTypes.DISCONNECT]},
            156: {"Use another server":
                  [PacketTypes.CONNACK, PacketTypes.DISCONNECT]},
            157: {"Server moved":
                  [PacketTypes.CONNACK, PacketTypes.DISCONNECT]},
            158: {"Shared subscription not supported":
                  [PacketTypes.SUBACK, PacketTypes.DISCONNECT]},
            159: {"Connection rate exceeded":
                  [PacketTypes.CONNACK, PacketTypes.DISCONNECT]},
            160: {"Maximum connect time":
                  [PacketTypes.DISCONNECT]},
            161: {"Subscription identifiers not supported":
                  [PacketTypes.SUBACK, PacketTypes.DISCONNECT]},
            162: {"Wildcard subscription not supported":
                  [PacketTypes.SUBACK, PacketTypes.DISCONNECT]},
        }
        if identifier == -1:
            if packetType == PacketTypes.DISCONNECT and aName == "Success":
                aName = "Normal disconnection"
            self.set(aName)
        else:
            self.value = identifier
            self.getName()  # check it's good

    def __getName__(self, packetType, identifier):
        """
        Get the reason code string name for a specific identifier.
        The name can vary by packet type for the same identifier, which
        is why the packet type is also required.

        Used when displaying the reason code.
        """
        assert identifier in self.names.keys(), identifier
        names = self.names[identifier]
        namelist = [name for name in names.keys() if packetType in names[name]]
        assert len(namelist) == 1
        return namelist[0]

    def getId(self, name):
        """
        Get the numeric id corresponding to a reason code name.

        Used when setting the reason code for a packetType
        check that only valid codes for the packet are set.
        """
        identifier = None
        for code in self.names.keys():
            if name in self.names[code].keys():
                if self.packetType in self.names[code][name]:
                    identifier = code
                break
        assert identifier is not None, name
        return identifier

    def set(self, name):
        self.value = self.getId(name)

    def unpack(self, buffer):
        c = buffer[0]
        if sys.version_info[0] < 3:
            c = ord(c)
        name = self.__getName__(self.packetType, c)
        self.value = self.getId(name)
        return 1

    def getName(self):
        """Returns the reason code name corresponding to the numeric value which is set.
        """
        return self.__getName__(self.packetType, self.value)

    def __eq__(self, other):
        if isinstance(other, int):
            return self.value == other
        if isinstance(other, str):
            return self.value == str(self)
        if isinstance(other, ReasonCodes):
            return self.value == other.value
        return False

    def __str__(self):
        return self.getName()

    def json(self):
        return self.getName()

    def pack(self):
        return bytearray([self.value])
