#!/bin/bash

g++ -c TestOrderBookEntry.cpp
g++ -c OrderBookEntry.cpp
g++ TestOrderBookEntry.o OrderBookEntry.o -o test
