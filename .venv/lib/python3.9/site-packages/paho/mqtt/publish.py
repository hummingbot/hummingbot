# Copyright (c) 2014 Roger Light <roger@atchoo.org>
#
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v2.0
# and Eclipse Distribution License v1.0 which accompany this distribution.
#
# The Eclipse Public License is available at
#    http://www.eclipse.org/legal/epl-v10.html
# and the Eclipse Distribution License is available at
#   http://www.eclipse.org/org/documents/edl-v10.php.
#
# Contributors:
#    Roger Light - initial API and implementation

"""
This module provides some helper functions to allow straightforward publishing
of messages in a one-shot manner. In other words, they are useful for the
situation where you have a single/multiple messages you want to publish to a
broker, then disconnect and nothing else is required.
"""
from __future__ import absolute_import

import collections

try:
    from collections.abc import Iterable
except ImportError:
    from collections import Iterable

from .. import mqtt
from . import client as paho


def _do_publish(client):
    """Internal function"""

    message = client._userdata.popleft()

    if isinstance(message, dict):
        client.publish(**message)
    elif isinstance(message, (tuple, list)):
        client.publish(*message)
    else:
        raise TypeError('message must be a dict, tuple, or list')


def _on_connect(client, userdata, flags, rc):
    """Internal callback"""
    #pylint: disable=invalid-name, unused-argument

    if rc == 0:
        if len(userdata) > 0:
            _do_publish(client)
    else:
        raise mqtt.MQTTException(paho.connack_string(rc))

def _on_connect_v5(client, userdata, flags, rc, properties):
    """Internal v5 callback"""
    _on_connect(client, userdata, flags, rc)

def _on_publish(client, userdata, mid):
    """Internal callback"""
    #pylint: disable=unused-argument

    if len(userdata) == 0:
        client.disconnect()
    else:
        _do_publish(client)


def multiple(msgs, hostname="localhost", port=1883, client_id="", keepalive=60,
             will=None, auth=None, tls=None, protocol=paho.MQTTv311,
             transport="tcp", proxy_args=None):
    """Publish multiple messages to a broker, then disconnect cleanly.

    This function creates an MQTT client, connects to a broker and publishes a
    list of messages. Once the messages have been delivered, it disconnects
    cleanly from the broker.

    msgs : a list of messages to publish. Each message is either a dict or a
           tuple.

           If a dict, only the topic must be present. Default values will be
           used for any missing arguments. The dict must be of the form:

           msg = {'topic':"<topic>", 'payload':"<payload>", 'qos':<qos>,
           'retain':<retain>}
           topic must be present and may not be empty.
           If payload is "", None or not present then a zero length payload
           will be published.
           If qos is not present, the default of 0 is used.
           If retain is not present, the default of False is used.

           If a tuple, then it must be of the form:
           ("<topic>", "<payload>", qos, retain)

    hostname : a string containing the address of the broker to connect to.
               Defaults to localhost.

    port : the port to connect to the broker on. Defaults to 1883.

    client_id : the MQTT client id to use. If "" or None, the Paho library will
                generate a client id automatically.

    keepalive : the keepalive timeout value for the client. Defaults to 60
                seconds.

    will : a dict containing will parameters for the client: will = {'topic':
           "<topic>", 'payload':"<payload">, 'qos':<qos>, 'retain':<retain>}.
           Topic is required, all other parameters are optional and will
           default to None, 0 and False respectively.
           Defaults to None, which indicates no will should be used.

    auth : a dict containing authentication parameters for the client:
           auth = {'username':"<username>", 'password':"<password>"}
           Username is required, password is optional and will default to None
           if not provided.
           Defaults to None, which indicates no authentication is to be used.

    tls : a dict containing TLS configuration parameters for the client:
          dict = {'ca_certs':"<ca_certs>", 'certfile':"<certfile>",
          'keyfile':"<keyfile>", 'tls_version':"<tls_version>",
          'ciphers':"<ciphers">, 'insecure':"<bool>"}
          ca_certs is required, all other parameters are optional and will
          default to None if not provided, which results in the client using
          the default behaviour - see the paho.mqtt.client documentation.
          Alternatively, tls input can be an SSLContext object, which will be
          processed using the tls_set_context method.
          Defaults to None, which indicates that TLS should not be used.

    transport : set to "tcp" to use the default setting of transport which is
          raw TCP. Set to "websockets" to use WebSockets as the transport.
    proxy_args: a dictionary that will be given to the client.
    """

    if not isinstance(msgs, Iterable):
        raise TypeError('msgs must be an iterable')


    client = paho.Client(client_id=client_id, userdata=collections.deque(msgs),
                         protocol=protocol, transport=transport)

    client.on_publish = _on_publish
    if protocol == mqtt.client.MQTTv5:
        client.on_connect = _on_connect_v5
    else:
        client.on_connect = _on_connect

    if proxy_args is not None:
        client.proxy_set(**proxy_args)

    if auth:
        username = auth.get('username')
        if username:
            password = auth.get('password')
            client.username_pw_set(username, password)
        else:
            raise KeyError("The 'username' key was not found, this is "
                           "required for auth")

    if will is not None:
        client.will_set(**will)

    if tls is not None:
        if isinstance(tls, dict):
            insecure = tls.pop('insecure', False)
            client.tls_set(**tls)
            if insecure:
                # Must be set *after* the `client.tls_set()` call since it sets
                # up the SSL context that `client.tls_insecure_set` alters.
                client.tls_insecure_set(insecure)
        else:
            # Assume input is SSLContext object
            client.tls_set_context(tls)

    client.connect(hostname, port, keepalive)
    client.loop_forever()


def single(topic, payload=None, qos=0, retain=False, hostname="localhost",
           port=1883, client_id="", keepalive=60, will=None, auth=None,
           tls=None, protocol=paho.MQTTv311, transport="tcp", proxy_args=None):
    """Publish a single message to a broker, then disconnect cleanly.

    This function creates an MQTT client, connects to a broker and publishes a
    single message. Once the message has been delivered, it disconnects cleanly
    from the broker.

    topic : the only required argument must be the topic string to which the
            payload will be published.

    payload : the payload to be published. If "" or None, a zero length payload
              will be published.

    qos : the qos to use when publishing,  default to 0.

    retain : set the message to be retained (True) or not (False).

    hostname : a string containing the address of the broker to connect to.
               Defaults to localhost.

    port : the port to connect to the broker on. Defaults to 1883.

    client_id : the MQTT client id to use. If "" or None, the Paho library will
                generate a client id automatically.

    keepalive : the keepalive timeout value for the client. Defaults to 60
                seconds.

    will : a dict containing will parameters for the client: will = {'topic':
           "<topic>", 'payload':"<payload">, 'qos':<qos>, 'retain':<retain>}.
           Topic is required, all other parameters are optional and will
           default to None, 0 and False respectively.
           Defaults to None, which indicates no will should be used.

    auth : a dict containing authentication parameters for the client:
           auth = {'username':"<username>", 'password':"<password>"}
           Username is required, password is optional and will default to None
           if not provided.
           Defaults to None, which indicates no authentication is to be used.

    tls : a dict containing TLS configuration parameters for the client:
          dict = {'ca_certs':"<ca_certs>", 'certfile':"<certfile>",
          'keyfile':"<keyfile>", 'tls_version':"<tls_version>",
          'ciphers':"<ciphers">, 'insecure':"<bool>"}
          ca_certs is required, all other parameters are optional and will
          default to None if not provided, which results in the client using
          the default behaviour - see the paho.mqtt.client documentation.
          Defaults to None, which indicates that TLS should not be used.
          Alternatively, tls input can be an SSLContext object, which will be
          processed using the tls_set_context method.

    transport : set to "tcp" to use the default setting of transport which is
          raw TCP. Set to "websockets" to use WebSockets as the transport.
    proxy_args: a dictionary that will be given to the client.
    """

    msg = {'topic':topic, 'payload':payload, 'qos':qos, 'retain':retain}

    multiple([msg], hostname, port, client_id, keepalive, will, auth, tls,
             protocol, transport, proxy_args)
