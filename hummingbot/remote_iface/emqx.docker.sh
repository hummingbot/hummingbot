#!/usr/bin/env bash

## PORTS
#   - 1883: MQTT
#   - 18083: EMQX Management UI
#   - 1884: MQTT-SN
#   - 61613: STOMP
#   - 5683: CoAP-UDP
#   - 5684: CoAP-DTLS
##
docker run              \
    -it                 \
    --rm                \
    --name emqx         \
    -p 18083:18083      \
    -p 1883:1883        \
    emqx/emqx:latest
