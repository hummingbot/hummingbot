#!/bin/bash

g++ -c -g TestOrderBookEntry.cpp
g++ -c -g OrderBookEntry.cpp
g++ TestOrderBookEntry.o OrderBookEntry.o -o TestOrderBookEntry
