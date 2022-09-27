#!/bin/bash

mkdir -p /usr/src/app/gateway.level \
         /usr/src/app/transactions.level \
         /usr/src/app/db \
         /usr/src/app/certs  \
         /usr/src/app/logs \
         /usr/src/app/conf
chown -R hummingbot:hummingbot \
         /usr/src/app/gateway.level \
         /usr/src/app/transactions.level \
         /usr/src/app/db \
         /usr/src/app/certs \
         /usr/src/app/logs \
         /usr/src/app/conf

gosu hummingbot:hummingbot yarn run start
