
Ниже — детальный план полной имплементации **Vest perpetual коннектора** в Hummingbot, опираясь на:

- `perp-connector-checklist.md`
- `build.md`, `debug.md`
- существующие коннекторы (`hyperliquid_perpetual`, `derive_perpetual`, `vertex_perpetual`, `bybit_perpetual`, `binance_perpetual`)

План ориентирован на TDD и >80% coverage.

---

## 0. Общая архитектура и подход

**Архитектура (по диаграмме Hummingbot)**:

- `vest_perpetual_auth.py` — уже начат, обеспечивает подпись всех приватных REST запросов (orders, cancel, lp, withdraw).
- `vest_perpetual_constants.py` — все URL, эндпоинты, rate limits, имена каналов.
- `vest_perpetual_web_utils.py` — функции построения REST/WS URL, вспомогательный маппинг доменов (prod/dev).
- `vest_perpetual_utils.py` — fees, конфиг (`ConfigMap`), маппинг символов Vest ↔ Hummingbot.
- `vest_perpetual_api_order_book_data_source.py` — публичные данные (orderbook, trades, funding), работа и по REST, и по WS.
- `vest_perpetual_user_stream_data_source.py` — приватный WS (`account_private` через listenKey), парсинг событий ORDER/LP/TRANSFER.
- `vest_perpetual_derivative.py` — сам коннектор: `ExchangePyBase` + `PerpetualDerivativePyBase` + `PerpetualTrading`.

**Основной шаблон:**

- Для структуры и perpetual-поведения — ориентируемся на **`hyperliquid_perpetual`** (off-chain orderbook + EVM подписи).
- Для listenKey‑потока и account_private — примеры из **Binance/Bybit Perpetual** user-stream.
- Для EIP‑712 и EVM‑подписей — **`hyperliquid_auth`**, **`derive_auth`**, **`vertex_auth`**.

**Методология:**

- Чёткий TDD:
  - На каждый компонент сначала пишем/адаптируем тесты (`test_vest_perpetual_*.py`), потом пишем/меняем реализацию.
  - Все внешние вызовы (REST/WS) — строго через `aioresponses` и `NetworkMockingAssistant`.
- Цель по покрытию: >80% для всего модуля `vest_perpetual`.

---

## 1. Scaffolding и базовая интеграция

### 1.1. Создать структуру файлов

В `hummingbot/hummingbot/connector/derivative/vest_perpetual`:

- `__init__.py`
- `vest_perpetual_constants.py`
- `vest_perpetual_web_utils.py`
- `vest_perpetual_utils.py`
- `vest_perpetual_auth.py` (уже есть, слегка доработаем позже)
- `vest_perpetual_api_order_book_data_source.py`
- `vest_perpetual_user_stream_data_source.py`
- `vest_perpetual_derivative.py`
- `dummy.pxd`, `dummy.pyx` (как во всех перп-коннекторах)

В `hummingbot/test/hummingbot/connector/derivative/vest_perpetual`:

- `__init__.py`
- `test_vest_perpetual_auth.py` (уже есть, обновлён)
- `test_vest_perpetual_constants.py` (опционально, но полезно)
- `test_vest_perpetual_web_utils.py`
- `test_vest_perpetual_utils.py`
- `test_vest_perpetual_api_order_book_data_source.py`
- `test_vest_perpetual_user_stream_data_source.py`
- `test_vest_perpetual_derivative.py`

**Как наполнять:**

- В качестве основного шаблона — взять `hyperliquid_perpetual/*` и `test_hyperliquid_perpetual/*`, но:
  - выкинуть/адаптировать всё, что относится к специфичным типам Hyperliquid,
  - заменить на Vest endpoints/форматы.

---

## 2. Constants (`vest_perpetual_constants.py`)

### 2.1. Что описать

- `DEFAULT_DOMAIN = "vest_perpetual"`  
  (при необходимости — `TESTNET_DOMAIN = "vest_perpetual_testnet"`, если будем поддерживать dev-сервер как отдельный домен)
- REST base URLs:
  - Prod: `https://server-prod.hz.vestmarkets.com/v2`
  - Dev: `https://server-dev.hz.vestmarkets.com/v2`
- WS URLs:
  - Prod: `wss://ws-prod.hz.vestmarkets.com/ws-api?version=1.0`
  - Dev: `wss://ws-dev.hz.vestmarkets.com/ws-api?version=1.0`
- Query/header:
  - REST: `xrestservermm: restserver{accGroup}`
  - WS: `xwebsocketserver=restserver{accGroup}`
- Маршруты API (из VEST_API_DOCS, сопоставление с perp-connector-checklist):

  | Feature                     | Vest endpoint                         |
  |-----------------------------|---------------------------------------|
  | GET ACTIVE MARKETS          | `GET /exchangeInfo` (symbols + rules)|
  | ORDERBOOK SNAPSHOT          | `GET /depth`                          |
  | TICKERS (24h, latest)       | `GET /ticker/latest`, `GET /ticker/24hr` |
  | PING                        | `GET /exchangeInfo` или `GET /ticker/latest` (как low-info ping) |
  | GET ACCOUNT BALANCE         | `GET /account`                        |
  | GET ORDER STATUS            | `GET /orders` (по id/nonce/symbol)   |
  | GET TRADES HISTORY          | `GET /orders` + поля fill/fees       |
  | GET OPEN ORDERS             | `GET /orders` (status=NEW/PARTIALLY) |
  | CREATE ORDERS               | `POST /orders`                        |
  | CANCEL ORDER                | `POST /orders/cancel`                |
  | FUNDING INFO                | `GET /funding/history`               |
  | GET POSITIONS               | `GET /account` (поле positions)      |
  | WS orderbook channel        | `{symbol}@depth`                     |
  | WS trades                   | `{symbol}@trades`                    |
  | WS klines (для candles)     | `{symbol}@kline_{interval}`          |
  | Private WS (orders, LP, tr) | channel `"account_private"` + events `ORDER`, `LP`, `TRANSFER` |

- `RATE_LIMITS`:
  - В VEST docs прямых rate limits нет — нужно добавить разумный conservative set на основе реального опыта/ограничений (например, запросы/сек для `exchangeInfo`, `depth`, `orders`, `account`, listenKey).
  - Структурировать как у других перп-коннекторов (список `RateLimit` + при необходимости `LinkedLimitWeightPair`).

### 2.2. TDD

- `test_vest_perpetual_constants.py`:
  - Проверить:
    - `DEFAULT_DOMAIN` и `REST_URLS/WSS_URLS` содержат нужные значения.
    - `RATE_LIMITS` включает ключевые endpoints (по именам throttler IDs).
  - Минимум — smoke-тест, что все константы объявлены и типы корректны.

---

## 3. Web Utils (`vest_perpetual_web_utils.py`)

Цели:

- Удобно строить REST/WS URL по `path_url` + `domain`.
- Инкапсулировать выбор base URL (prod/dev) и добавление query параметров (xwebsocketserver, listenKey).

### 3.1. Основные функции

По паттерну `bitget_perpetual_web_utils.py` / `hyperliquid_perpetual_web_utils.py`:

- `public_rest_url(path_url: str, domain: str = DEFAULT_DOMAIN) -> str`
- `private_rest_url(path_url: str, domain: str = DEFAULT_DOMAIN) -> str`  
  (по сути, одинаковый base URL, но удобно иметь разделение)
- `public_ws_url(domain: str = DEFAULT_DOMAIN, account_group: int = 0) -> str`
  - Добавляет `xwebsocketserver=restserver{account_group}` в query.
- `private_ws_url(listen_key: str, domain: str = DEFAULT_DOMAIN, account_group: int = 0) -> str`
  - `...?version=1.0&websocketserver=restserver{accGroup}&listenKey=<listenKey>`

### 3.2. TDD

`test_vest_perpetual_web_utils.py`:

- Проверить, что:

  - `public_rest_url("/depth")` даёт `"https://server-prod.../v2/depth"` для `DEFAULT_DOMAIN`.
  - Аналогично для dev-домена, если будет.
  - `public_ws_url(domain, account_group)` содержит:
    - `ws-*-hz.vestmarkets.com/ws-api?version=1.0`
    - query `websocketserver=restserver{account_group}`.
  - `private_ws_url(listen_key, ...)` добавляет `listenKey=...`.

---

## 4. Utils и конфиг (`vest_perpetual_utils.py`)

### 4.1. Конфиг и fees

На базе `hyperliquid_perpetual_utils.py`, `derive_perpetual_utils.py`:

- Определить `VestPerpetualConfigMap`:

  - `connector: str = "vest_perpetual"`
  - `vest_perpetual_api_key: SecretStr`
    - Описание: JWT `apiKey` из `/register`.
  - `vest_perpetual_signing_private_key: SecretStr`
    - Описание: EVM private key `signing_privkey`, **НЕ Rabby**.
  - `vest_perpetual_account_group: int`
    - Из ответа `/register` (`accGroup`).

- `DEFAULT_FEES`:
  - Взять примерные значения (taker/maker) из VEST docs (у `exchangeInfo.symbols[*].takerFee`),
  - Использовать conservative, потом можно уточнить.

- Маппинг символов:

  - Hummingbot формат: `"BTC-USDC"` / `"BTC-USDT"` или `"BTC-USDC-PERP"`; Vest: `"BTC-PERP"`, `"AAPL-USD-PERP"`.
  - Нужна пара функций:
    - `convert_to_exchange_trading_pair(trading_pair: str) -> str`  
      (например `"BTC-USDC"` → `"BTC-PERP"` для perps).
    - `convert_from_exchange_trading_pair(exchange_symbol: str) -> str`  
      (`"BTC-PERP"` → `"BTC-USDC"` или `"BTC-USDT"` — выбрать один canonical quote, например USDC).

  - Логику лучше взять из `hyperliquid_perpetual_utils`/`derive_perpetual_utils` и адаптировать под символы Vest.

### 4.2. TDD

`test_vest_perpetual_utils.py`:

- Проверить:

  - Что config map требует ровно наши ключи и они отмечены как `is_connect_key`.
  - Что функции конвертации символов работают как ожидается.
  - Что `DEFAULT_FEES` и `build_default_fees` (если будет) возвращают корректную структуру `TradeFeeSchema`.

---

## 5. Auth (`vest_perpetual_auth.py`)

Мы уже сделали основу:

- Заголовки:
  - `X-API-KEY`
  - `xrestservermm: restserver{accGroup}`
- Подпись `POST /orders` по формуле из docs:
  - `keccak(encode([...], [time, nonce, orderType, symbol, isBuy, size, limitPrice, reduceOnly]))`
  - подпись через `signing_private_key`.

### 5.1. Дальнейшее расширение

Дополнительно нужно:

- `_generate_cancel_signature(order)` для `POST /orders/cancel`:
  - По докам:

    ```python
    args = keccak(encode(
        ["uint256", "uint256", "string"],
        [time, nonce, id]
    ))
    ```

- `_generate_lp_signature(order)` для `POST /lp`:

    ```python
    ["uint256", "uint256", "string", "string"],
    [time, nonce, orderType, size]
    ```

- `_generate_withdraw_signature(order)` для `POST /transfer/withdraw`:

    ```python
    ["uint256", "uint256", "bool", "address", "address", "address", "uint256", "uint256"],
    [time, nonce, False, account, recipient, token, size, chainId]
    ```

- Обновить `rest_authenticate` так, чтобы:

  - по `path` определять тип действия (orders, cancel, lp, withdraw),
  - для каждого случая подставлять соответствующую подпись.

WS‑auth у Vest делается через listenKey в URL — `ws_authenticate` оставляем pass-through.

### 5.2. TDD

`test_vest_perpetual_auth.py`:

- Уже есть:
  - тест заголовков и добавления `signature` в `POST /orders`.
  - крипто‑тест, что подпись восстанавливается в `signingAddr`.

Добавить:

- `test_generate_cancel_signature_recovers_signing_address`
- `test_generate_lp_signature_recovers_signing_address`
- `test_generate_withdraw_signature_recovers_signing_address`
- Тесты, что `rest_authenticate` корректно подписывает `POST /orders/cancel`, `/lp`, `/transfer/withdraw`.

---

## 6. Order Book Data Source (`vest_perpetual_api_order_book_data_source.py`)

Основные задачи:

- REST:
  - `get_active_exchange_markets()` / `trading_pairs` на основе `GET /exchangeInfo`.
  - `_request_order_book_snapshot` использует `GET /depth`.
  - `get_funding_info` использует `GET /funding/history`.
- WebSocket:
  - Подписки:
    - `{symbol}@depth` — ордербук.
    - `{symbol}@trades` — trades.
    - `{symbol}@kline_...` — для candles (опционально).
  - Парсеры:
    - `_parse_order_book_diff_message`
    - `_parse_trade_message`
    - `_parse_funding_info_message` (по funding/history, если понадобятся WS‑ивенты).

### 6.1. REST детали

- `GET /exchangeInfo`:
  - `symbols[*]` → список perps, фильтруем по `status == TRADING`.
  - Отсюда же берём trading rules (minQty, stepSize, priceDecimals, sizeDecimals, leverage limits).
- `GET /depth`:
  - `bids` и `asks` как `[price, qty]`.
- `GET /funding/history`:
  - Для funding info на конкретный symbol.

### 6.2. WebSocket детали

- URL через `public_ws_url(domain, account_group)`.
- Формат подписки по докам:

  ```json
  {"method": "SUBSCRIBE", "params": ["BTC-PERP@depth", "BTC-PERP@trades"], "id": 1}
  ```

- Ответы:

  - Orderbook:
    ```json
    {
      "channel": "DOGE-PERP@depth",
      "data": {
        "bids": [["0.102000", "1234"]],
        "asks": [["0.103000", "1234"]]
      }
    }
    ```
  - Trades:
    ```json
    {
      "channel": "DOGE-PERP@trades",
      "data": {
        "id": "0x",
        "price": "0.102000",
        "qty": "1234",
        "quoteQty": "125.868000",
        "time": 1725315151174
      }
    }
    ```

- Нужны методы:
  - `_subscribe_channels`
  - `_process_websocket_messages`
  - `_channel_originating_message` (по `channel` определить тип).

### 6.3. TDD (перп-чеклист)

Согласно `perp-connector-checklist.md`, для order book data source:

- REST:
  - `test_get_new_order_book_successful`
  - `test_get_new_order_book_raises_exception`
  - `test_get_funding_info`
- WS:
  - `test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs_and_funding_info`
  - `test_listen_for_subscriptions_raises_cancel_exception`
  - `test_listen_for_subscriptions_logs_exception_details`
  - `test_subscribe_channels_raises_cancel_exception`
  - `test_subscribe_channels_raises_exception_and_logs_error`
  - `test_listen_for_trades_successful`
  - `test_listen_for_trades_cancelled_when_listening`
  - `test_listen_for_trades_logs_exception`
  - `test_listen_for_order_book_diffs_successful`
  - `test_listen_for_order_book_diffs_cancelled`
  - `test_listen_for_order_book_diffs_logs_exception`
  - `test_listen_for_order_book_snapshots_successful`
  - `test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot`
  - `test_listen_for_order_book_snapshots_log_exception`
  - `test_listen_for_funding_info_successful`
  - `test_listen_for_funding_info_cancelled_when_listening`
  - `test_listen_for_funding_info_logs_exception`

Реализацию брать по мотивам `hyperliquid_perpetual_api_order_book_data_source.py`, но адаптировать под формат Vest.

---

## 7. User Stream Data Source (`vest_perpetual_user_stream_data_source.py`)

Цель:

- Управлять listenKey и приватным WS:

  - `POST /account/listenKey`
  - `PUT /account/listenKey`
  - `DELETE /account/listenKey`

- Подключаться к WS c listenKey:

  - `wss://.../ws-api?version=1.0&websocketserver=restserver{accGroup}&listenKey=<listenKey>`

- Подписка:

  ```json
  {"method": "SUBSCRIBE", "params": ["account_private"], "id": 1}
  ```

- Обработка событий:

  ```json
  {
    "channel": "account_private",
    "data": {
      "event": "ORDER" | "LP" | "TRANSFER",
      "args": { ... payload ... }
    }
  }
  ```

### 7.1. Логика

- Методы:

  - `_get_listen_key`: вызывает `POST /account/listenKey`, парсит `listenKey`.
  - `_ping_listen_key`: `PUT /account/listenKey`.
  - `_manage_listen_key_task_loop`: периодически пингует (валидность 60 минут).
  - `_connected_websocket_assistant`: создаёт WS‑подключение через `private_ws_url(listen_key, ...)`.
  - `_subscribe_channels`: подписка на `account_private`.
  - `_process_user_stream_event`: парсинг событий ORDER/LP/TRANSFER в формат Hummingbot (orders, fills, funding payments, transfers).

### 7.2. TDD

По чеклисту:

- `test_get_listen_key_successful`
- `test_get_listen_key_log_exception`
- `test_ping_listen_key_successful`
- `test_ping_listen_key_log_exception`
- `test_manage_listen_key_task_loop_keep_alive_successful`
- `test_manage_listen_key_task_loop_keep_alive_failed`
- `test_listen_for_user_stream_get_listen_key_successful_with_user_update_event`
- `test_listen_for_user_stream_does_not_queue_empty_payload`
- `test_listen_for_user_stream_connection_failed`
- `test_listen_for_user_stream_iter_message_throws_exception`

Примеры — из `binance_perpetual` и `bybit_perpetual` user stream data source тестов.

---

## 8. Derivative Connector (`vest_perpetual_derivative.py`)

Самый большой кусок: реализация всех абстрактных методов `ExchangePyBase` и `PerpetualDerivativePyBase`, плюс обвязка вокруг Vest API.

### 8.1. Абстрактные методы Exchange/Perp баз

По `perp-connector-checklist.md`:

- Из `ExchangePyBase`:

  - `authenticator`
  - `name`
  - `rate_limits_rules`
  - `domain`
  - `client_order_id_max_length`
  - `client_order_id_prefix`
  - `trading_rules_request_path` → `/exchangeInfo`
  - `trading_pairs_request_path` → `/exchangeInfo`
  - `check_network_request_path` → `/exchangeInfo` или `/ticker/latest`
  - `trading_pairs`
  - `is_cancel_request_in_exchange_synchronous`
  - `is_trading_required`
  - `supported_order_types`
  - `_is_request_exception_related_to_time_synchronizer` (скорее всего `False`/stub)
  - `_create_web_assistants_factory`
  - `_create_order_book_data_source`
  - `_create_user_stream_data_source`
  - `_get_fee`
  - `_place_order` (через `POST /orders`)
  - `_place_cancel` (через `POST /orders/cancel`)
  - `_format_trading_rules`
  - `_status_polling_loop_fetch_updates` (`GET /orders`)
  - `_update_trading_fees`
  - `_user_stream_event_listener` (главный цикл обработки ORDER/LP/TRANSFER)
  - `_all_trade_updates_for_order`
  - `_request_order_status`
  - `_update_balances` (`GET /account`)
  - `_initialize_trading_pair_symbols_from_exchange_info`
  - `_get_last_traded_price` (через `GET /ticker/latest`)

- Из `PerpetualDerivativePyBase`:

  - `funding_fee_poll_interval`
  - `supported_position_modes` (скорее всего только ONEWAY)
  - `get_buy_collateral_token` / `get_sell_collateral_token` (везде `USDC`)
  - `_update_positions` (по `GET /account.positions`)
  - `_set_trading_pair_leverage` (`POST /account/leverage`)
  - `_fetch_last_fee_payment` (`GET /orders` либо отдельный endpoint, если будет)

### 8.2. Ордеры, отмена, fills

- `_place_order`:

  - строим JSON body по схеме `POST /orders` (с `order` и полями `time`, `nonce`, ...).
  - `VestPerpetualAuth.rest_authenticate` добавит `signature`.
  - mapping HB → Vest:
    - side (BUY/SELL → `isBuy`)
    - order type (LIMIT/MARKET → строка)
    - time in force (GTC/FOK) → `timeInForce`
    - client order id → опционально `id`/`nonce` (можно маппить `clOrdId` через `nonce`).

- `_place_cancel`:

  - `POST /orders/cancel` с `order` (time, nonce, id).
  - Auth добавит подпись.

- `_user_stream_event_listener`:

  - Из `account_private` ORDER event:
    - NEW → `BuyOrderCreatedEvent`/`SellOrderCreatedEvent`.
    - FILLED/PARTIALLY_FILLED → `OrderFilledEvent` (+ fees, realizedPnl, funding).
    - CANCELLED → `OrderCancelledEvent`.
    - REJECTED → `OrderFailure`/`MarketOrderFailureEvent`.

- `_update_order_status`, `_update_order_fills_from_trades`:

  - fallback через `GET /orders` (с фильтрами по id/nonce/symbol/time).

### 8.3. Balances/positions/funding

- `_update_balances`:

  - `GET /account` → `balances[*].asset`, `total`, `locked`.

- `_update_positions`:

  - `GET /account` → `positions[*]`.

- Funding info:

  - REST: `GET /funding/history?symbol=...` → `FundingInfo`.
  - WS: по плану funding через публичные тикеры / history (если будем добавлять WS-события — можно парсить и их).

### 8.4. TDD — generic tests

`test_vest_perpetual_derivative.py`:

- Использовать generic test-класс как у других перп-коннекторов:

  - Реализовать методы:

    - `all_symbols_request_mock_response`
    - `latest_prices_request_mock_response`
    - `trading_rules_request_mock_response`
    - `order_creation_request_successful_mock_response`
    - `balance_request_mock_response_for_base_and_quote`
    - `expected_trading_rule`
    - и весь длинный список из чеклиста (order lifecycle, funding, leverage, position mode, funding payments).

- Большая часть тестов — копия из `test_hyperliquid_perpetual_derivative.py` с адаптацией под JSON Vest.

---

## 9. Интеграция в конфиг и регистрацию коннектора

### 9.1. Global config

В `conf_global_TEMPLATE.yml`:

- Добавить:

  - `vest_perpetual_api_key`
  - `vest_perpetual_signing_private_key`
  - `vest_perpetual_account_group`

С описаниями и безопасными промптами.

### 9.2. Регистрация коннектора

- В `hummingbot/client/hummingbot_application.py`:
  - Зарегистрировать `"vest_perpetual"` как доступный коннектор деривативов.
- Если есть центральная мапа доступных коннекторов (например, в `connector_settings`), добавить запись.

---

## 10. Тестирование и отладка (debug.md)

### 10.1. Unit tests

- Запуск целевой подсетки:

  ```bash
  pytest test/hummingbot/connector/derivative/vest_perpetual -q
  ```

- Когда всё будет зелёным — `coverage run -m pytest` и отчёт по покрытию.

### 10.2. Локальные скрипты / aioconsole

- Использовать `ignore_tests.py`‑подобные скрипты:

  - Проверка `/register` (уже сделали).
  - Проверка `POST /orders` с помощью `VestPerpetualAuth` + `aiohttp` (не в unit-тестах, а в dev-скриптах).

- Для WS:
  - Небольшой скрипт, который:
    - берёт listenKey,
    - коннектится к `account_private`,
    - печатает события ORDER/LP/TRANSFER.

---

## 11. Порядок реализации (по этапам)

1. **Constants + web_utils + utils**  
   - Написать тесты → реализовать → убедиться, что URL и символы строятся правильно.

2. **Auth**  
   - Мы сделали основу; доработать подписи для cancel/lp/withdraw.
   - Добавить соответствующие крипто-тесты (recover до `signingAddr`).

3. **Order Book Data Source**  
   - Сначала тесты (REST/WS), затем реализация.

4. **User Stream Data Source (listenKey + account_private)**  
   - Тесты для listenKey lifecycle + приём ORDER/LP/TRANSFER, затем реализация.

5. **Derivative Connector**  
   - Подключить все компоненты, реализовать все абстрактные методы из чеклиста.
   - Пройти generic перп-тесты, адаптировав моки под Vest JSON.

6. **Интеграция и документация**  
   - Конфиги, регистрация коннектора, короткий README по шагам: как получить signingAddr, как сделать `/register`, какие ключи вводить в Hummingbot.

---

Если хочешь, следующая итерация может быть:  
я сделаю детальный todo‑список именно для **order book data source** (c конкретными полями в `ExchangeInfo`, `depth`, `trades`, маппингами в `OrderBookMessage`/`TradeUpdate`), а потом — для user stream и derivative.


## User

Да, сделай детальный todo список для каждого этапа.

## Assistant


## Общая структура TODO

Ниже подробный TODO-лист по этапам, чтобы можно было идти блоками и делать всё TDD‑стилем.  
Для каждого этапа: что реализовать в коде и какие тесты/моки нужны.

---

## 1. Scaffolding и базовая интеграция

### 1.1. Структура директорий и файлов

**TODO:**

- [ ] Создать пакет `hummingbot/hummingbot/connector/derivative/vest_perpetual`:
  - [ ] `__init__.py`
  - [ ] `vest_perpetual_constants.py`
  - [ ] `vest_perpetual_web_utils.py`
  - [ ] `vest_perpetual_utils.py`
  - [ ] `vest_perpetual_auth.py` (уже есть — только доработки)
  - [ ] `vest_perpetual_api_order_book_data_source.py`
  - [ ] `vest_perpetual_user_stream_data_source.py`
  - [ ] `vest_perpetual_derivative.py`
  - [ ] `dummy.pxd`
  - [ ] `dummy.pyx`

- [ ] Создать пакет тестов `hummingbot/test/hummingbot/connector/derivative/vest_perpetual`:
  - [ ] `__init__.py`
  - [ ] `test_vest_perpetual_constants.py`
  - [ ] `test_vest_perpetual_web_utils.py`
  - [ ] `test_vest_perpetual_utils.py`
  - [ ] `test_vest_perpetual_auth.py` (есть — расширить)
  - [ ] `test_vest_perpetual_api_order_book_data_source.py`
  - [ ] `test_vest_perpetual_user_stream_data_source.py`
  - [ ] `test_vest_perpetual_derivative.py`

**Тестовая цель:**  
На этом шаге достаточно, чтобы все файлы импортировались, а пустые заглушки не ломали pytest.

---

## 2. Constants (`vest_perpetual_constants.py`)

### 2.1. Реализация

**TODO (код):**

- [ ] Объявить базовые константы:
  - [ ] `DEFAULT_DOMAIN = "vest_perpetual"`
  - [ ] При необходимости: `TESTNET_DOMAIN = "vest_perpetual_testnet"` (если хотим dev как отдельный домен, но можно просто использовать параметр конфигурации для выбора URL).
- [ ] REST base URLs:
  - [ ] `REST_URLS = { DEFAULT_DOMAIN: "https://server-prod.hz.vestmarkets.com/v2", TESTNET_DOMAIN?: "https://server-dev.hz.vestmarkets.com/v2" }`
- [ ] WS base URLs:
  - [ ] `WSS_URLS = { DEFAULT_DOMAIN: "wss://ws-prod.hz.vestmarkets.com/ws-api?version=1.0", TESTNET_DOMAIN?: "wss://ws-dev.hz.vestmarkets.com/ws-api?version=1.0" }`
- [ ] Path constants для checklist:
  - [ ] `EXCHANGE_INFO_PATH = "/exchangeInfo"`
  - [ ] `DEPTH_PATH = "/depth"`
  - [ ] `TICKER_LATEST_PATH = "/ticker/latest"`
  - [ ] `TICKER_24HR_PATH = "/ticker/24hr"`
  - [ ] `FUNDING_HISTORY_PATH = "/funding/history"`
  - [ ] `ACCOUNT_PATH = "/account"`
  - [ ] `ACCOUNT_NONCE_PATH = "/account/nonce"` (если будем использовать для nonce‑менеджмента)
  - [ ] `ACCOUNT_LEVERAGE_PATH = "/account/leverage"`
  - [ ] `ORDERS_PATH = "/orders"`
  - [ ] `ORDERS_CANCEL_PATH = "/orders/cancel"`
  - [ ] `LP_PATH = "/lp"`
  - [ ] `LP_QUERY_PATH = "/lp"`
  - [ ] `TRANSFER_WITHDRAW_PATH = "/transfer/withdraw"`
  - [ ] `TRANSFER_QUERY_PATH = "/transfer"`
  - [ ] Listen key:
    - [ ] `LISTEN_KEY_PATH = "/account/listenKey"` (для POST/PUT/DELETE).
- [ ] WS channel constants:
  - [ ] `ORDERBOOK_DEPTH_CHANNEL = "{symbol}@depth"`
  - [ ] `TRADES_CHANNEL = "{symbol}@trades"`
  - [ ] `KLINE_CHANNEL = "{symbol}@kline_{interval}"`
  - [ ] `ACCOUNT_PRIVATE_CHANNEL = "account_private"`
- [ ] Rate limits:
  - [ ] Определить список `RATE_LIMITS: List[RateLimit]`:
    - [ ] Общий лимит по базе (REST)
    - [ ] Отдельные лимиты для:
      - `EXCHANGE_INFO_PATH`
      - `DEPTH_PATH`
      - `TICKER_LATEST_PATH`, `TICKER_24HR_PATH`
      - `ACCOUNT_PATH`, `ACCOUNT_NONCE_PATH`, `ACCOUNT_LEVERAGE_PATH`
      - `ORDERS_PATH`, `ORDERS_CANCEL_PATH`
      - `LP_PATH`, `TRANSFER_WITHDRAW_PATH`
      - `LISTEN_KEY_PATH`
  - [ ] При необходимости добавить `LinkedLimitWeightPair`.

### 2.2. Тесты

**TODO (tests — `test_vest_perpetual_constants.py`):**

- [ ] `test_rest_urls_and_ws_urls_have_expected_domains`
  - Проверить, что `REST_URLS[DEFAULT_DOMAIN]` и `WSS_URLS[DEFAULT_DOMAIN]` равны ожидаемым строкам.
- [ ] `test_paths_defined_for_required_functionality`
  - Проверить, что все path константы объявлены.
- [ ] `test_rate_limits_include_key_endpoints`
  - Smoke-тест: что есть хотя бы по одному `RateLimit` для ключевых endpoints (`/exchangeInfo`, `/depth`, `/orders`, `/account`, `/account/listenKey`).

---

## 3. Web Utils (`vest_perpetual_web_utils.py`)

### 3.1. Реализация

**TODO (код):**

- [ ] Реализовать приватную функцию `_create_rest_url(path_url: str, domain: str) -> str`:
  - Выбирает правильный base URL из `REST_URLS`.
  - Конкатенирует с `path_url`.
- [ ] `_create_ws_url(domain: str) -> str`:
  - Берёт `WSS_URLS[domain]` как базу.
- [ ] `public_rest_url(path_url: str, domain: str = DEFAULT_DOMAIN) -> str`
- [ ] `private_rest_url(path_url: str, domain: str = DEFAULT_DOMAIN) -> str`  
  (скорее всего то же самое, но оставляем для совместимости)
- [ ] `public_ws_url(domain: str = DEFAULT_DOMAIN, account_group: int = 0) -> str`:
  - Добавить/обновить query параметр `websocketserver=restserver{account_group}`.
- [ ] `private_ws_url(listen_key: str, domain: str = DEFAULT_DOMAIN, account_group: int = 0) -> str`:
  - Базируется на `public_ws_url(...)`, добавляет `listenKey=<listen_key>`.

### 3.2. Тесты

**TODO (tests — `test_vest_perpetual_web_utils.py`):**

- [ ] `test_public_rest_url_builds_correctly`
  - Сравнить результат `public_rest_url(EXCHANGE_INFO_PATH)` с ожидаемой строкой.
- [ ] `test_public_ws_url_contains_websocketserver_param`
  - Проверить наличие `websocketserver=restserver0` в URL.
- [ ] `test_private_ws_url_contains_listen_key`
  - Убедиться, что `listenKey=abc123` присутствует в URL и `websocketserver` не потерялся.

---

## 4. Utils и конфиг (`vest_perpetual_utils.py`)

### 4.1. Реализация

**TODO (код):**

- [ ] Определить `VestPerpetualConfigMap(BaseConnectorConfigMap)`:
  - [ ] `connector: str = "vest_perpetual"`
  - [ ] `vest_perpetual_api_key: SecretStr` с `prompt` типа: `"Enter your Vest API key from /register"`
  - [ ] `vest_perpetual_signing_private_key: SecretStr` с `prompt`: `"Enter your Vest signing private key (API keypair, NOT your Rabby key)"`
  - [ ] `vest_perpetual_account_group: int` с `prompt`: `"Enter your Vest account group (accGroup from /register)"`
- [ ] Определить `DEFAULT_FEES` (примерно, потом можно скорректировать):
  - Taker/Maker — взять из примеров VEST или задать консервативно.
- [ ] Реализовать функции конвертации пар:
  - [ ] `convert_to_exchange_trading_pair(hb_trading_pair: str) -> str`
    - Например, `"BTC-USDC"` → `"BTC-PERP"`, `"AAPL-USDC"` → `"AAPL-USD-PERP"`.
  - [ ] `convert_from_exchange_trading_pair(exchange_symbol: str) -> str`
    - `"BTC-PERP"` → `"BTC-USDC"`, `"AAPL-USD-PERP"` → `"AAPL-USDC"`.
- [ ] При необходимости — helper для rounding size/price с учётом `sizeDecimals`, `priceDecimals`.

### 4.2. Тесты

**TODO (tests — `test_vest_perpetual_utils.py`):**

- [ ] `test_config_map_contains_expected_fields`
  - Проверить наличие и тип полей (`api_key`, `signing_private_key`, `account_group`).
- [ ] `test_convert_to_exchange_trading_pair`
  - Примеры вроде `"BTC-USDC"` и `"AAPL-USDC"`.
- [ ] `test_convert_from_exchange_trading_pair`
  - Обратные примеры `"BTC-PERP"`, `"AAPL-USD-PERP"`.
- [ ] `test_default_fees_have_expected_structure`
  - Проверка, что `DEFAULT_FEES` возвращает валидный `TradeFeeSchema`.

---

## 5. Auth (`vest_perpetual_auth.py`) — расширение

### 5.1. Реализация

Уже есть ордерная подпись; дополняем остальное.

**TODO (код):**

- [ ] Добавить `_generate_cancel_signature(order: Dict[str, Any]) -> str`:

  - Вход: `order` с полями `time`, `nonce`, `id`.
  - Хэш:

    ```python
    keccak(encode(["uint256", "uint256", "string"], [time, nonce, id]))
    ```

- [ ] `_generate_lp_signature(order)`:

  - Поля: `time`, `nonce`, `orderType`, `size`.
  - Хэш:

    ```python
    keccak(encode(["uint256", "uint256", "string", "string"], [...]))
    ```

- [ ] `_generate_withdraw_signature(order)`:

  - Поля: `time`, `nonce`, `account`, `recipient`, `token`, `size`, `chainId`.
  - Хэш:

    ```python
    keccak(encode(
      ["uint256", "uint256", "bool", "address", "address", "address", "uint256", "uint256"],
      [time, nonce, False, account, recipient, token, size, chainId]
    ))
    ```

- [ ] Расширить `rest_authenticate`:

  - По `path` и структуре `data` определять тип:
    - `POST /orders` → `_generate_orders_signature`.
    - `POST /orders/cancel` → `_generate_cancel_signature`.
    - `POST /lp` → `_generate_lp_signature`.
    - `POST /transfer/withdraw` → `_generate_withdraw_signature`.
  - Добавлять `signature` в body (как сейчас для orders).

### 5.2. Тесты

**TODO (tests — `test_vest_perpetual_auth.py`):**

- [ ] `test_generate_orders_signature_recovers_signing_address` (уже есть)
- [ ] `test_generate_cancel_signature_recovers_signing_address`
- [ ] `test_generate_lp_signature_recovers_signing_address`
- [ ] `test_generate_withdraw_signature_recovers_signing_address`
  - Для каждого кейса:
    - собрать `order` как в доках;
    - вызвать соответствующий метод;
    - пересчитать hash → `encode_defunct` → `EthAccount.recover_message(...)` и сравнить с `signingAddr`.
- [ ] `test_rest_authenticate_signs_cancel_orders`
  - RESTRequest с URL `/orders/cancel` и `order` в body → проверить наличие `signature`.
- [ ] `test_rest_authenticate_signs_lp_orders`
- [ ] `test_rest_authenticate_signs_withdraw_orders`
- [ ] `test_header_for_authentication_contains_api_key_and_restserver_header` (уже покрыто частично).

---

## 6. Order Book Data Source (`vest_perpetual_api_order_book_data_source.py`)

### 6.1. Реализация

**TODO (код):**

- [ ] Класс `VestPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource)`:
  - Конструктор:
    - `trading_pairs`, `connector`, `api_factory` (web assistants).
- [ ] REST методы:
  - [ ] `_request_order_book_snapshot(trading_pair)`:
    - Конвертировать `trading_pair` → Vest symbol (`convert_to_exchange_trading_pair`).
    - `GET /depth?symbol=...&limit=N`.
    - Преобразовать в snapshot `OrderBookMessage`.
  - [ ] `get_funding_info(trading_pair)`:
    - `GET /funding/history?symbol=...&limit=1&endTime=now`.
    - Вернуть `FundingInfo`/внутреннюю структуру.
- [ ] WebSocket:
  - [ ] `_connected_websocket_assistant` — создать ассистента через `public_ws_url(domain, account_group)`.
  - [ ] `_subscribe_channels(ws, trading_pairs)`:
    - Список каналов: `{symbol}@depth`, `{symbol}@trades`.
    - Отправить `{"method": "SUBSCRIBE", "params": [...], "id": ...}`.
  - [ ] `_process_websocket_messages(ws, queue)`:
    - Читать сообщения, определять `channel`, передавать в `listen_for_*` очереди.
  - [ ] `_channel_originating_message(event_message)`:
    - По `message["channel"]` определить, это `ORDERBOOK_DIFF`, `TRADE` и т.п.
  - [ ] `_parse_trade_message(message)`:
    - По примеру trades в VEST docs.
  - [ ] `_parse_order_book_diff_message(message)`:
    - На основе `data.bids`, `data.asks`.

- [ ] Методы из чеклиста:
  - `listen_for_subscriptions`, `listen_for_trades`, `listen_for_order_book_diffs`, `listen_for_order_book_snapshots`, `listen_for_funding_info` — большинство есть в базовом классе, надо только специфичные `_parse_*` и `_subscribe_channels`.

### 6.2. Тесты (`test_vest_perpetual_api_order_book_data_source.py`)

**TODO (tests, на основе checklist):**

REST:

- [ ] `test_get_new_order_book_successful`
  - С `aioresponses` замокать `GET /depth` и проверить, что snapshot очередь получает корректный `OrderBookMessage`.
- [ ] `test_get_new_order_book_raises_exception`
  - Ошибка HTTP → исключение.
- [ ] `test_get_funding_info`
  - Мок `GET /funding/history` → `get_funding_info` возвращает правильную структуру.

WS:

- [ ] `test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs_and_funding_info`
- [ ] `test_listen_for_subscriptions_raises_cancel_exception`
- [ ] `test_listen_for_subscriptions_logs_exception_details`
- [ ] `test_subscribe_channels_raises_cancel_exception`
- [ ] `test_subscribe_channels_raises_exception_and_logs_error`
- [ ] `test_listen_for_trades_successful`
- [ ] `test_listen_for_trades_cancelled_when_listening`
- [ ] `test_listen_for_trades_logs_exception`
- [ ] `test_listen_for_order_book_diffs_successful`
- [ ] `test_listen_for_order_book_diffs_cancelled`
- [ ] `test_listen_for_order_book_diffs_logs_exception`
- [ ] `test_listen_for_order_book_snapshots_successful`
- [ ] `test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot`
- [ ] `test_listen_for_order_book_snapshots_log_exception`
- [ ] `test_listen_for_funding_info_successful`
- [ ] `test_listen_for_funding_info_cancelled_when_listening`
- [ ] `test_listen_for_funding_info_logs_exception`

Использовать `NetworkMockingAssistant` + сабсоединения по аналогии с `hyperliquid_perpetual` тестами.

---

## 7. User Stream Data Source (`vest_perpetual_user_stream_data_source.py`)

### 7.1. Реализация

**TODO (код):**

- [ ] Класс `VestPerpetualUserStreamDataSource(UserStreamTrackerDataSource)`:
  - Конструктор:
    - `auth`, `api_factory`, `domain`, `account_group`.
- [ ] ListenKey lifecycle:
  - [ ] `_get_listen_key()`:
    - `POST /account/listenKey` → parse `{"listenKey": "..."}`.
  - [ ] `_ping_listen_key(listen_key)`:
    - `PUT /account/listenKey` → renew validity.
  - [ ] `_delete_listen_key(listen_key)`:
    - `DELETE /account/listenKey`.
  - [ ] `_manage_listen_key_task_loop()`:
    - Цикл, периодически вызывает `_ping_listen_key`, в случае 400/4xx — перезапрашивает новый listenKey.
- [ ] WS connection:
  - [ ] `_get_ws_assistant()`:
    - Вызывает `_get_listen_key`.
    - Строит URL через `private_ws_url(listen_key, ...)`.
    - Возвращает `WSAssistant`.
  - [ ] `_connected_websocket_assistant()`:
    - Оборачивает `_get_ws_assistant`, хэндлит reconnect.
  - [ ] `_subscribe_channels(ws)`:
    - Отправляет `{"method": "SUBSCRIBE", "params": ["account_private"], "id": 1}`.
  - [ ] Обработка сообщений:
    - Приём сообщений с `channel == "account_private"`.
    - Разбор `data.event`:
      - `"ORDER"` → очередь событий ордеров.
      - `"LP"` → события LP (для funding/баланса/истории).
      - `"TRANSFER"` → депозиты/выводы.

- [ ] Метод `listen_for_user_stream(output_queue)`:
  - Использует базовую реализацию (`listen_for_user_stream` в родителе), переопределяя `_connected_websocket_assistant`, `_subscribe_channels`.

### 7.2. Тесты (`test_vest_perpetual_user_stream_data_source.py`)

**TODO (tests, по checklist):**

- ListenKey:

  - [ ] `test_get_listen_key_successful`
  - [ ] `test_get_listen_key_log_exception`
  - [ ] `test_ping_listen_key_successful`
  - [ ] `test_ping_listen_key_log_exception`
  - [ ] `test_manage_listen_key_task_loop_keep_alive_successful`
  - [ ] `test_manage_listen_key_task_loop_keep_alive_failed`

- User stream:

  - [ ] `test_listen_for_user_stream_get_listen_key_successful_with_user_update_event`
    - Мок WS-сообщения `ORDER` → попадание в output_queue.
  - [ ] `test_listen_for_user_stream_does_not_queue_empty_payload`
  - [ ] `test_listen_for_user_stream_connection_failed`
  - [ ] `test_listen_for_user_stream_iter_message_throws_exception`

---

## 8. Derivative Connector (`vest_perpetual_derivative.py`)

### 8.1. Реализация

**TODO (код):**

- [ ] Класс `VestPerpetualDerivative(ExchangePyBase, PerpetualDerivativePyBase)`:
  - Конструктор:
    - Параметры: `client_config_map`, `vest_perpetual_api_key`, `vest_perpetual_signing_private_key`, `vest_perpetual_account_group`, `trading_pairs`, `domain`.
    - Инициализация:
      - `self._auth = VestPerpetualAuth(...)`
      - `_web_assistants_factory = build_api_factory(...)` через `vest_perpetual_web_utils`.
  - Реализация абстрактных свойств/методов:
    - [ ] `authenticator` → вернуть `self._auth`
    - [ ] `name` → `"vest_perpetual"`
    - [ ] `rate_limits_rules` → вернуть `CONSTANTS.RATE_LIMITS`
    - [ ] `domain` → вернуть текущий домен.
    - [ ] `client_order_id_max_length`, `client_order_id_prefix` (решить формат, например `VEST-` + hex).
    - [ ] `trading_rules_request_path` → `EXCHANGE_INFO_PATH`
    - [ ] `trading_pairs_request_path` → `EXCHANGE_INFO_PATH`
    - [ ] `check_network_request_path` → `TICKER_LATEST_PATH` или `EXCHANGE_INFO_PATH`
    - [ ] `trading_pairs` → property, возвращает список поддерживаемых пар.
    - [ ] `is_cancel_request_in_exchange_synchronous` → задать в соответствии с поведением Vest (скорее всего `False` и полагаться на WS).
    - [ ] `is_trading_required` → `True`
    - [ ] `supported_order_types` → `[MARKET, LIMIT]` и т.п.
    - [ ] `_create_web_assistants_factory`
    - [ ] `_create_order_book_data_source`
    - [ ] `_create_user_stream_data_source`
    - [ ] `_get_fee`
    - [ ] `_place_order`
    - [ ] `_place_cancel`
    - [ ] `_format_trading_rules`
    - [ ] `_status_polling_loop_fetch_updates`
    - [ ] `_update_trading_fees`
    - [ ] `_user_stream_event_listener`
    - [ ] `_all_trade_updates_for_order`
    - [ ] `_request_order_status`
    - [ ] `_update_balances`
    - [ ] `_initialize_trading_pair_symbols_from_exchange_info`
    - [ ] `_get_last_traded_price`

- Из `PerpetualDerivativePyBase`:

  - [ ] `funding_fee_poll_interval` (например, 60 сек)
  - [ ] `supported_position_modes` (скорее всего только `ONEWAY`)
  - [ ] `get_buy_collateral_token` / `get_sell_collateral_token` (всегда `"USDC"`)
  - [ ] `_update_positions` (через `GET /account`)
  - [ ] `_set_trading_pair_leverage` (через `POST /account/leverage`)
  - [ ] `_fetch_last_fee_payment` (на основе `GET /orders` или отдельного endpoint, если появится)

### 8.2. Тесты (`test_vest_perpetual_derivative.py`)

**TODO (tests, по checklist, используя Generic Test Class):**

- Реализовать методы-моки для generic тестов:

  - [ ] `all_symbols_request_mock_response`
  - [ ] `latest_prices_request_mock_response`
  - [ ] `trading_rules_request_mock_response`
  - [ ] `trading_rules_request_erroneous_mock_response`
  - [ ] `order_creation_request_successful_mock_response`
  - [ ] `balance_request_mock_response_for_base_and_quote`
  - [ ] `balance_request_mock_response_only_base`
  - [ ] `expected_trading_rule`
  - [ ] `expected_latest_price`
  - [ ] и весь остальной список из `perp-connector-checklist.md` (cancel, fills, funding, position mode, leverage и т.д.)

- Generic тесты покрывают:
  - Создание/отмена ордеров.
  - Обновление статусов по HTTP.
  - Обработку WS‑ивентов order/fill.
  - Funding info, funding payments.
  - Позиции, смену leverage, position mode.

---

## 9. Config и регистрация коннектора

### 9.1. Global config

**TODO:**

- [ ] В `conf_global_TEMPLATE.yml`:
  - Добавить:
    - `vest_perpetual_api_key` с описанием.
    - `vest_perpetual_signing_private_key` с описанием и предупреждением «НЕ Rabby».
    - `vest_perpetual_account_group`.

### 9.2. Регистрация в Hummingbot

**TODO:**

- [ ] Добавить коннектор в реестр деривативов:
  - В `hummingbot/client/hummingbot_application.py` и/или `connector_settings`:
    - Регистрация `"vest_perpetual"` с соответствующим классом.
- [ ] При необходимости — добавить в UI список поддерживаемых коннекторов.

---

## 10. Тестирование и отладка

### 10.1. Автоматические тесты

**TODO:**

- [ ] Настроить запуск:

  ```bash
  pytest test/hummingbot/connector/derivative/vest_perpetual -q
  ```

- [ ] Проверка покрытия:

  ```bash
  coverage run -m pytest
  coverage report
  ```

- [ ] Добиться >80% coverage по модулю `vest_perpetual`.

### 10.2. Локальные e2e-скрипты (debug)

**TODO (вне unit-тестов, чисто для разработки):**

- [ ] Скрипт для `/register` (у тебя уже есть `ignore_tests.py` — можно довести до аккуратного util).
- [ ] Скрипт `test_post_order.py`:
  - Использует `VestPerpetualAuth`, реальные `apiKey`/`signingPriv`, и `aiohttp` для отправки `POST /orders`.
- [ ] Скрипт `test_private_ws.py`:
  - Получает listenKey.
  - Подключается к `account_private`.
  - Печатает ORDER/LP/TRANSFER события.

---

Если хочешь, следующим шагом можно выбрать конкретный блок (например, **constants + web_utils**) и я распишу уже конкретные сигнатуры функций и примерные структуры mock‑ответов для тестов.
