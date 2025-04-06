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


class MQTTException(Exception):
    pass


class SubscribeOptions(object):
    """The MQTT v5.0 subscribe options class.

    The options are:
        qos:                As in MQTT v3.1.1.
        noLocal:            True or False. If set to True, the subscriber will not receive its own publications.
        retainAsPublished:  True or False. If set to True, the retain flag on received publications will be as set
                            by the publisher.
        retainHandling:     RETAIN_SEND_ON_SUBSCRIBE, RETAIN_SEND_IF_NEW_SUB or RETAIN_DO_NOT_SEND
                            Controls when the broker should send retained messages:
                                - RETAIN_SEND_ON_SUBSCRIBE: on any successful subscribe request
                                - RETAIN_SEND_IF_NEW_SUB: only if the subscribe request is new
                                - RETAIN_DO_NOT_SEND: never send retained messages
    """

    # retain handling options
    RETAIN_SEND_ON_SUBSCRIBE, RETAIN_SEND_IF_NEW_SUB, RETAIN_DO_NOT_SEND = range(
        0, 3)

    def __init__(self, qos=0, noLocal=False, retainAsPublished=False, retainHandling=RETAIN_SEND_ON_SUBSCRIBE):
        """
        qos:                0, 1 or 2.  0 is the default.
        noLocal:            True or False. False is the default and corresponds to MQTT v3.1.1 behavior.
        retainAsPublished:  True or False. False is the default and corresponds to MQTT v3.1.1 behavior.
        retainHandling:     RETAIN_SEND_ON_SUBSCRIBE, RETAIN_SEND_IF_NEW_SUB or RETAIN_DO_NOT_SEND
                            RETAIN_SEND_ON_SUBSCRIBE is the default and corresponds to MQTT v3.1.1 behavior.
        """
        object.__setattr__(self, "names",
                           ["QoS", "noLocal", "retainAsPublished", "retainHandling"])
        self.QoS = qos  # bits 0,1
        self.noLocal = noLocal  # bit 2
        self.retainAsPublished = retainAsPublished  # bit 3
        self.retainHandling = retainHandling  # bits 4 and 5: 0, 1 or 2
        assert self.QoS in [0, 1, 2]
        assert self.retainHandling in [
            0, 1, 2], "Retain handling should be 0, 1 or 2"

    def __setattr__(self, name, value):
        if name not in self.names:
            raise MQTTException(
                name + " Attribute name must be one of "+str(self.names))
        object.__setattr__(self, name, value)

    def pack(self):
        assert self.QoS in [0, 1, 2]
        assert self.retainHandling in [
            0, 1, 2], "Retain handling should be 0, 1 or 2"
        noLocal = 1 if self.noLocal else 0
        retainAsPublished = 1 if self.retainAsPublished else 0
        data = [(self.retainHandling << 4) | (retainAsPublished << 3) |
                (noLocal << 2) | self.QoS]
        if sys.version_info[0] >= 3:
            buffer = bytes(data)
        else:
            buffer = bytearray(data)
        return buffer

    def unpack(self, buffer):
        b0 = buffer[0]
        self.retainHandling = ((b0 >> 4) & 0x03)
        self.retainAsPublished = True if ((b0 >> 3) & 0x01) == 1 else False
        self.noLocal = True if ((b0 >> 2) & 0x01) == 1 else False
        self.QoS = (b0 & 0x03)
        assert self.retainHandling in [
            0, 1, 2], "Retain handling should be 0, 1 or 2, not %d" % self.retainHandling
        assert self.QoS in [
            0, 1, 2], "QoS should be 0, 1 or 2, not %d" % self.QoS
        return 1

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "{QoS="+str(self.QoS)+", noLocal="+str(self.noLocal) +\
            ", retainAsPublished="+str(self.retainAsPublished) +\
            ", retainHandling="+str(self.retainHandling)+"}"

    def json(self):
        data = {
            "QoS": self.QoS,
            "noLocal": self.noLocal,
            "retainAsPublished": self.retainAsPublished,
            "retainHandling": self.retainHandling,
        }
        return data
