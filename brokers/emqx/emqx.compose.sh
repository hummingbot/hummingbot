#!/usr/bin/env bash

## PORTS
#   - 1883: MQTT
#   - 18083: EMQX Management UI
#   - 1884: MQTT-SN
#   - 61613: STOMP
#   - 5683: CoAP-UDP
#   - 5684: CoAP-DTLS
##
docker-compose -f emqx.compose.yml down --remove-orphans &&
    # docker compose -f emqx.compose.yml run emqx1
    docker compose -f emqx.compose.yml up
