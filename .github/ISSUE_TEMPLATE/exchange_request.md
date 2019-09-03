---
name: Exchange connector request
about: Suggest a new exchange connector for hummingbot
title: "[New Exchange Connector]"
labels: new exchange
assignees: ''

---

## Exchange Details ✏️

- **Name of exchange**:
- **Exchange URL**:
- **Link to API docs**: 
- **Type of exchange**: [ ] Centralized [ ] Decentralized
- **Requester details**: Are you affiliated with the exchange? [ ] yes [ ] no 
  - If yes, what is your role?

## Rationale / impact ✏️
(Describe your rationale for building this exchange connector, impact for hummingbot users/community)

## Additional information ✏️
(Provide any other useful information that may be helpful to know about this exchange)

---

⚠️ ***Note: do not modify below here***

## Developer notes

This feature request entails building a new exchange connector to allow Hummingbot to connect to an exchange that is currently not supported.

### Resources
- [Exchange connector developer guide](https://docs.hummingbot.io/developers/connectors/)
- [Discord forum](https://discord.hummingbot.io)

### Deliverables
1. A complete set of exchange connector files as listed [above](#developer-notes-resources).
2. Unit tests (see [existing unit tests](https://github.com/CoinAlpha/hummingbot/tree/master/test/integration)):
  1. Exchange market test ([example](https://github.com/CoinAlpha/hummingbot/blob/master/test/integration/test_binance_market.py))
  2. Order book tracker ([example](https://github.com/CoinAlpha/hummingbot/blob/master/test/integration/test_binance_order_book_tracker.py))
  3. User stream tracker ([example](https://github.com/CoinAlpha/hummingbot/blob/master/test/integration/test_binance_user_stream_tracker.py))
3. Documentation:
  1. Code commenting (particularly for any code that is materially different from the templates/examples)
  2. Any specific instructions for the use of that exchange connector ([example](https://docs.hummingbot.io/connectors/binance/))

### Required skills
- Python
- Previous Cython experience is a plus (optional)