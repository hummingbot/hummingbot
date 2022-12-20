#!/bin/bash

docker-compose -f rabbitmq.compose.yml down --remove-orphans &&
    docker compose -f rabbitmq.compose.yml up
