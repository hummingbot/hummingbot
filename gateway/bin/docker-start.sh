#!/bin/bash

mkdir -p /usr/src/app/gateway.level
chown -R hummingbot:hummingbot /usr/src/app/logs /usr/src/app/conf \
    /usr/src/app/gateway.level

gosu hummingbot:hummingbot yarn run start
