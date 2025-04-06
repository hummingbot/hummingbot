# Copyright (c) 2016 Roger Light <roger@atchoo.org>
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
This module provides some helper functions to allow straightforward subscribing
to topics and retrieving messages. The two functions are simple(), which
returns one or messages matching a set of topics, and callback() which allows
you to pass a callback for processing of messages.
"""
from __future__ import absolute_import

from .. import mqtt
from . import client as paho


def _on_connect_v5(client, userdata, flags, rc, properties):
    """Internal callback"""
    if rc != 0:
        raise mqtt.MQTTException(paho.connack_string(rc))

    if isinstance(userdata['topics'], list):
        for topic in userdata['topics']:
            client.subscribe(topic, userdata['qos'])
    else:
        client.subscribe(userdata['topics'], userdata['qos'])

def _on_connect(client, userdata, flags, rc):
    """Internal v5 callback"""
    _on_connect_v5(client, userdata, flags, rc, None)


def _on_message_callback(client, userdata, message):
    """Internal callback"""
    userdata['callback'](client, userdata['userdata'], message)


def _on_message_simple(client, userdata, message):
    """Internal callback"""

    if userdata['msg_count'] == 0:
        return

    # Don't process stale retained messages if 'retained' was false
    if message.retain and not userdata['retained']:
        return

    userdata['msg_count'] = userdata['msg_count'] - 1

    if userdata['messages'] is None and userdata['msg_count'] == 0:
        userdata['messages'] = message
        client.disconnect()
        return

    userdata['messages'].append(message)
    if userdata['msg_count'] == 0:
        client.disconnect()


def callback(callback, topics, qos=0, userdata=None, hostname="localhost",
             port=1883, client_id="", keepalive=60, will=None, auth=None,
             tls=None, protocol=paho.MQTTv311, transport="tcp",
             clean_session=True, proxy_args=None):
    """Subscribe to a list of topics and process them in a callback function.

    This function creates an MQTT client, connects to a broker and subscribes
    to a list of topics. Incoming messages are processed by the user provided
    callback.  This is a blocking function and will never return.

    callback : function of the form "on_message(client, userdata, message)" for
               processing the messages received.

    topics : either a string containing a single topic to subscribe to, or a
             list of topics to subscribe to.

    qos : the qos to use when subscribing. This is applied to all topics.

    userdata : passed to the callback

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

    clean_session : a boolean that determines the client type. If True,
                    the broker will remove all information about this client
                    when it disconnects. If False, the client is a persistent
                    client and subscription information and queued messages
                    will be retained when the client disconnects.
                    Defaults to True.

    proxy_args: a dictionary that will be given to the client.
    """

    if qos < 0 or qos > 2:
        raise ValueError('qos must be in the range 0-2')

    callback_userdata = {
        'callback':callback,
        'topics':topics,
        'qos':qos,
        'userdata':userdata}

    client = paho.Client(client_id=client_id, userdata=callback_userdata,
                         protocol=protocol, transport=transport,
                         clean_session=clean_session)
    client.on_message = _on_message_callback
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


def simple(topics, qos=0, msg_count=1, retained=True, hostname="localhost",
           port=1883, client_id="", keepalive=60, will=None, auth=None,
           tls=None, protocol=paho.MQTTv311, transport="tcp",
           clean_session=True, proxy_args=None):
    """Subscribe to a list of topics and return msg_count messages.

    This function creates an MQTT client, connects to a broker and subscribes
    to a list of topics. Once "msg_count" messages have been received, it
    disconnects cleanly from the broker and returns the messages.

    topics : either a string containing a single topic to subscribe to, or a
             list of topics to subscribe to.

    qos : the qos to use when subscribing. This is applied to all topics.

    msg_count : the number of messages to retrieve from the broker.
                if msg_count == 1 then a single MQTTMessage will be returned.
                if msg_count > 1 then a list of MQTTMessages will be returned.

    retained : If set to True, retained messages will be processed the same as
               non-retained messages. If set to False, retained messages will
               be ignored. This means that with retained=False and msg_count=1,
               the function will return the first message received that does
               not have the retained flag set.

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

    clean_session : a boolean that determines the client type. If True,
                    the broker will remove all information about this client
                    when it disconnects. If False, the client is a persistent
                    client and subscription information and queued messages
                    will be retained when the client disconnects.
                    Defaults to True.

    proxy_args: a dictionary that will be given to the client.
    """

    if msg_count < 1:
        raise ValueError('msg_count must be > 0')

    # Set ourselves up to return a single message if msg_count == 1, or a list
    # if > 1.
    if msg_count == 1:
        messages = None
    else:
        messages = []

    userdata = {'retained':retained, 'msg_count':msg_count, 'messages':messages}

    callback(_on_message_simple, topics, qos, userdata, hostname, port,
             client_id, keepalive, will, auth, tls, protocol, transport,
             clean_session, proxy_args)

    return userdata['messages']
