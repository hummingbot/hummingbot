---
id: PERF-003
title: _all_trade_updates_for_order no filtra userTrades por orderId
category: performance
impact: medium
effort: S
risk: low
status: done
connector: binance_perpetual
files:
  - hummingbot/connector/derivative/binance_perpetual/binance_perpetual_derivative.py:289
doc_refs:
  - https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Account-Trade-List
commits:
  - "667b94b56 (perf) filter binance_perpetual userTrades by orderId in _all_trade_updates_for_order"
created: 2026-06-10
---

## Problema
`_all_trade_updates_for_order` pide el historial de trades (`/fapi/v1/userTrades`, `ACCOUNT_TRADE_LIST_URL`)
pasando solo `{"symbol": ...}` y filtra en cliente con `if order_id == exchange_order_id`:

```python
all_fills_response = await self._api_get(
    path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
    params={"symbol": trading_pair},
    is_auth_required=True)
for trade in all_fills_response:
    if str(trade.get("orderId")) == exchange_order_id:
        ...
```

La doc oficial indica que `userTrades` acepta `orderId` (opcional, combinable con `symbol`). Sin filtros
de tiempo el endpoint devuelve **solo los últimos 7 días**, default 500 / máx 1000 trades. Para una orden
con fills fuera de las últimas 500 operaciones (símbolo muy activo) los fills se **pierden**; además se
traen y parsean cientos de trades irrelevantes. El weight es 5 con o sin `orderId`, así que filtrar no
tiene downside.

## Solución propuesta
Agregar `orderId` a los params para que Binance devuelva únicamente los trades de esa orden:

```python
params={
    "symbol": trading_pair,
    "orderId": exchange_order_id,
}
```

(`exchange_order_id` ya se obtiene arriba vía `await order.get_exchange_order_id()`.)

## Criterio de aceptación
- [x] La llamada de `_all_trade_updates_for_order` incluye `orderId`.
- [x] El bucle ya no necesita descartar trades de otras órdenes (filtro `if order_id == exchange_order_id` queda como defensa redundante).
- [x] Test que verifique que se envía `orderId` y que se parsean correctamente los fills de la orden.
- [x] No se rompe ningún test existente.

## Notas
Aplica al método de recuperación por orden (`_all_trade_updates_for_order`). El poll masivo
`_update_order_fills_from_trades` (línea ~627) sí necesita pedir por símbolo porque cubre varias órdenes a
la vez — no aplicar `orderId` ahí.

### Resolución
Se agregó `"orderId": exchange_order_id` a los params de `_all_trade_updates_for_order`
(`binance_perpetual_derivative.py:289`). El filtro client-side `if order_id == exchange_order_id`
se conservó como defensa redundante (sin scope creep). Se agregó el test
`test_all_trade_updates_for_order_filters_by_order_id` que asserta el `orderId` enviado y el
parseo de los fills. No se tocó `_update_order_fills_from_trades`. Tests del archivo del connector:
49 passed. pre-commit: passed.
