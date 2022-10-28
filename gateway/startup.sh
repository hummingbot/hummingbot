#!/bin/bash 
node dist/src/index.js $1

while [ $? != 0 ]; do
    echo "Gateway API server stopped unexpectedly. Restarting..."
    node dist/src/index.js $1;
done