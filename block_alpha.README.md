
# `check_arb` Command Documentation

## Notes for Assessor

This document outlines the functionality, behavior, and usage of the `check_arb` CLI command implemented for Hummingbot. The command is aligned with the task objective: to help users evaluate potential arbitrage opportunities between two or more exchanges.

---

## User Guide

### Getting Started

First, set up Hummingbot by following the instructions at [https://hummingbot.org](https://hummingbot.org).

The `check_arb` command compares the best bid and ask prices for a **single trading pair** across two or more exchanges. It calculates potential forward and reverse arbitrage spreads and can optionally include taker fees using the `--with-fees` flag.

No prior configuration or import steps are required to use this command.

### Usage Examples

```bash
check_arb binance:BTC-USDT gate_io:BTC-USDT --with-fees
check_arb binance:ETH-USDT gate_io:ETH-USDT kucoin:ETH-USDT
```

> ⚠️ All inputs must refer to the **same instrument** (e.g., BTC-USDT). The command does not currently support equivalent pairs (e.g., BTC-USDC) or reversed pairs (e.g., USDT-BTC).

---

## Interactive Input Mode

If fewer than two exchange:market pairs are provided, the user will be prompted interactively:

```bash
>>> check_arb --with-fees
Please enter the first exchange instrument pair you would like to check >>> binance:BTC-USDT
Please enter the second exchange instrument pair you would like to check >>>
```

Or:

```bash
>>> check_arb binance:BTC-USDT
Please enter the second exchange instrument pair you would like to check >>>
```

Invalid or unrecognized input will be re-prompted until valid entries are provided. There is no exit command in this prompt (consistent with other Hummingbot commands); users must terminate the process manually to cancel.

---

## Error Handling

The command provides descriptive feedback for invalid inputs:

```bash
>>> check_arb foo
[Invalid Input] Expected format 'exchange:market' → 'foo'
Hint: e.g. binance:BTC-USDT
```

```bash
>>> check_arb binancee:BTC-USDT
[Invalid Input] Unknown exchange 'binancee'
Hint: Check that the connector is installed and spelled correctly.
```

```bash
>>> check_arb binance:BTC-USDT gate_io:BTC-USDC
[Invalid Input] Arbitrage between different instruments is not supported. → {'BTC-USDC', 'BTC-USDT'}
```

```bash
>>> check_arb binance:BTCC-USDT gate_io:BTCC-USDT
Starting 'cross_exchange_arb_logger' strategy...
Instrument 'BTCC-USDT' not supported by binance.
```

---

## Expected Output

If inputs are valid, the command will start the `cross_exchange_arb_logger` strategy and begin logging:

```bash
>>> check_arb binance:BTC-USDT gate_io:BTC-USDT
'cross_exchange_arb_logger' strategy started.
Run `status` command to query the progress.
```

### CLI Log Output (Sample)

```
binance (BTC-USDT):
   Best Bid: 78,739.13 | Best Ask: 78,739.14
gate_io (BTC-USDT):
   Best Bid: 78,748.50 | Best Ask: 78,748.60
Potential forward arb: (binance bid - gate_io ask) / gate_io ask = -0.01%
Potential reverse arb: (gate_io bid - binance ask) / binance ask = +0.01%
Fees not included.
```

When the `--with-fees` flag is used, the output reflects fees in the spread:

```
binance (BTC-USDT):
   Best Bid: 78,955.98 | Best Ask: 78,955.99
gate_io (BTC-USDT):
   Best Bid: 78,960.30 | Best Ask: 78,960.40
Potential forward arb: ... = -0.30%
Potential reverse arb: ... = -0.29%
Fees included.
```

---

## Unit Tests

Unit tests were added for:

- `spread_calculation()` – to validate forward and reverse spread logic.
- `input_validation()` – to ensure correct format and instrument matching.

> Given more time, I would have explored mocking connector behavior to simulate full end-to-end strategy runs.

---

## Assumptions

- API keys appear to be required even for retrieving public data (e.g., best bid/ask), which is unexpected and adds friction for users.
- Connectors must be installed and functional for the strategy to operate.
- Only a single instrument across all exchanges is supported in this MVP version.
- The command gracefully handles malformed input, but requires manual termination if users want to exit mid-interaction.
