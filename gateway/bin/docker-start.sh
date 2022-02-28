#!/bin/bash

chown -R hummingbot:hummingbot /usr/src/app/logs /usr/src/app/conf

gosu hummingbot:hummingbot yarn run start
