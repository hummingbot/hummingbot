# General plan for integration testing of a connector

## Public APIs

### Order book tracker

#### Order book integrity
- Setup volume2 = volume1 * 1000
- Price to buy volume1 is less or equal than price to buy volume2
- Price to sell volume1 is greater or equal than price to sell volume2
- Best price to sell is less than best price to buy

### Get trades

#### Order book tracker receives trades and emits correct trade events

## Rate limit

### Comply with rate limit
- API allows to send public requests at allowed rate limit

### Exceed rate limit
- API does not allow to send public requests above allowed rate limit

## Get fees

## Placing market orders

### Place buy market order

### Place sell market order

## Placing limit orders

### Place buy limit order at considerable distance from best price
- Place buy limit order
- Wait until order is registered on exchange
- Read orders - the order should be seen
- Cancel order

### Place sell limit order at considerable distance from best price
- Place buy limit order
- Wait until order is registered on exchange
- Read orders - the order should be seen
- Cancel order

## Placing limit orders and watching completion events

### Place limit buy order and watch for completion
- Place a limit buy order at the best price
- If price moves, cancel and replace order
- Repeat until completion event is seen

### Place limit sell order and watch for completion
- Place a limit sell order at the best price
- If price moves, cancel and replace order
- Repeat until completion event is seen

## Placing and canceling all orders
- Place buy limit order at considerable distance from best price
- Cancel all orders immediately (before placed order is registered in exchange, but after it is sent)
- New order should not be placed or should appear as canceled

## User stream tracker
