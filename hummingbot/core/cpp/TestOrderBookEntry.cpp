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
    truncateOverlapEntriesCentralised(bidsBook, asksBook);
    printf("Asks side iterator empty? %d\n", asksIterator == asksBook.end());
    printf("Bids side iterator empty? %d\n", bidsIterator == bidsBook.rend());

    printf("\n*** testEmptyOrderBooks(): Stage 3 ***\n");
    bidsBook.insert(OrderBookEntry(100.0, 4.0, 2));
    bidsBook.insert(OrderBookEntry(100.1, 2.0, 2));
    bidsBook.insert(OrderBookEntry(100.9, 1.5, 2));
    bidsBook.insert(OrderBookEntry(101.0, 0.1, 2));
    asksBook.insert(OrderBookEntry(105.0, 100, 2));
    asksBook.insert(OrderBookEntry(104.0, 50, 2));
    asksBook.insert(OrderBookEntry(103.0, 20, 3));
    asksBook.insert(OrderBookEntry(102.0, 10, 3));
    asksBook.insert(OrderBookEntry(100.91, 1, 3));
    truncateOverlapEntriesCentralised(bidsBook, asksBook);
    asksIterator = asksBook.begin();
    bidsIterator = bidsBook.rbegin();
    printf("Asks side iterator empty? %d\n", asksIterator == asksBook.end());
    printf("Bids side iterator empty? %d\n", bidsIterator == bidsBook.rend());

    printf("\n*** testEmptyOrderBooks(): Stage 4 ***\n");
    asksBook.insert(OrderBookEntry(100.89, 1.0, 4));
    asksBook.insert(OrderBookEntry(100.88, 0.8, 4));
    asksBook.insert(OrderBookEntry(100.86, 0.7, 4));
}
