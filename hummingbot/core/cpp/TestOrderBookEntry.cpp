//
// Created by Martin Kou on 2/14/20.
//

#include <cstdio>
#include <set>
#include "OrderBookEntry.h"

typedef std::set<OrderBookEntry> OrderBookSide;

void testEmptyOrderBooks();

int main(const int argc, const char **argv) {
    testEmptyOrderBooks();
    return 0;
}

void testEmptyOrderBooks() {
    OrderBookSide bidsBook;
    OrderBookSide asksBook;
    OrderBookSide::iterator asksIterator = asksBook.begin();
    OrderBookSide::reverse_iterator bidsIterator = bidsBook.rbegin();

    printf("*** testEmptyOrderBooks(): Stage 1 ***\n");
    printf("Asks side iterator empty? %d\n", asksIterator == asksBook.end());
    printf("Bids side iterator empty? %d\n", bidsIterator == bidsBook.rend());

    printf("\n*** testEmptyOrderBooks(): Stage 2 ***\n");
    bidsBook.insert(OrderBookEntry(100.0, 1.0, 1));
    bidsBook.insert(OrderBookEntry(99.9, 2.0, 1));
    bidsBook.insert(OrderBookEntry(99.8, 4.0, 1));
    printf("Asks side iterator empty? %d\n", asksIterator == asksBook.end());
    printf("Bids side iterator empty? %d\n", bidsIterator == bidsBook.rend());
}