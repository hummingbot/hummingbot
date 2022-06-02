#!/bin/bash

mkdir -p /usr/src/app/gateway.level /usr/src/app/transactions.level
chown -R hummingbot:hummingbot /usr/src/app/logs /usr/src/app/conf \
    /usr/src/app/gateway.level /usr/src/app/transactions.level

gosu hummingbot:hummingbot yarn run start
