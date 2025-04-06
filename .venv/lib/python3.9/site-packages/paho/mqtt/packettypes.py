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


class PacketTypes:

    """
    Packet types class.  Includes the AUTH packet for MQTT v5.0.

    Holds constants for each packet type such as PacketTypes.PUBLISH
    and packet name strings: PacketTypes.Names[PacketTypes.PUBLISH].

    """

    indexes = range(1, 16)

    # Packet types
    CONNECT, CONNACK, PUBLISH, PUBACK, PUBREC, PUBREL, \
        PUBCOMP, SUBSCRIBE, SUBACK, UNSUBSCRIBE, UNSUBACK, \
        PINGREQ, PINGRESP, DISCONNECT, AUTH = indexes

    # Dummy packet type for properties use - will delay only applies to will
    WILLMESSAGE = 99

    Names = [ "reserved", \
    "Connect", "Connack", "Publish", "Puback", "Pubrec", "Pubrel", \
    "Pubcomp", "Subscribe", "Suback", "Unsubscribe", "Unsuback", \
    "Pingreq", "Pingresp", "Disconnect", "Auth"]
