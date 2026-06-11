---
id: PERF-008
title: _update_order_fills_from_trades baja todos los userTrades por símbolo en cada poll (startTime muerto)
category: performance
impact: medium
effort: S
risk: low
status: done
connector: binance_perpetual
files:
  - hummingbot/connector/derivative/binance_perpetual/binance_perpetual_derivative.py:632
  - hummingbot/connector/derivative/binance_perpetual/binance_perpetual_derivative.py:60
doc_refs:
  - https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Account-Trade-List
commits:
  - "82713b4d4 (perf) bound binance_perpetual order-fills polling with startTime"
created: 2026-06-11
---

## Problema
`_update_order_fills_from_trades` (derivative.py:632-684) corre en cada tick del status polling
(cada `UPDATE_ORDER_STATUS_MIN_INTERVAL` = 10 s mientras haya órdenes activas) y hace, por cada
símbolo con órdenes activas:

```python
self._api_get(
    path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
    params={"symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)},
    is_auth_required=True,
)
```

Sin `startTime` ni `orderId`, la doc de Account Trade List devuelve los últimos 7 días con default
500 / máx 1000 registros, a weight 5 por request. Además, `self._last_trade_history_timestamp`
(derivative.py:60) se inicializa en `__init__` y **nunca se usa**: la intención de acotar por tiempo
quedó como código muerto.

Impacto:
- Weight desperdiciado: 5 × símbolos × 6 veces/min descargando y parseando cientos de trades
  irrelevantes en cuentas activas.
- Riesgo de correctitud secundario: si un fill de una orden activa cae fuera de la ventana de los
  últimos 500 trades del símbolo (cuenta muy activa), ese fill **no se detecta** por esta vía y queda
  dependiendo del user stream o del estado final de la orden.

## Solución propuesta
Acotar la request con `startTime`:
- Mantener `self._last_trade_history_timestamp` (o un timestamp por símbolo) actualizado con el campo
  `time` del trade más reciente procesado.
- En cada poll, pasar `"startTime": <último time visto + 1>`; para el primer poll, usar el
  `creation_timestamp` de la orden activa más vieja del símbolo (en ms).

Alternativa: eliminar el atributo muerto y documentar que la vía primaria de fills es el user stream —
pero la opción con `startTime` es igual de simple y reduce carga real.

## Criterio de aceptación
- [x] Las requests a `ACCOUNT_TRADE_LIST_URL` en `_update_order_fills_from_trades` incluyen `startTime`.
- [x] No se pierden fills entre polls (test con fills en ticks consecutivos).
- [x] `_last_trade_history_timestamp` se usa o se elimina (sin estado muerto).
- [x] Sin regresiones en los tests existentes de `_update_order_fills_from_trades`.

## Notas
Verificado contra doc oficial (2026-06-11). Complementa a [[PERF-003]] (que agrega `orderId` en
`_all_trade_updates_for_order`, otra vía distinta de recuperación de fills).

Implementado reutilizando `_last_trade_history_timestamp` como un único timestamp global de poll
(no por símbolo), espejando el patrón del connector spot (`binance_exchange._fetch_account_trades`
con `_last_trades_poll_binance_timestamp`): se guarda el timestamp del poll y en el siguiente tick se
pasa `startTime = <timestamp del poll anterior> en ms`. El primer poll va sin `startTime` (atributo
en `None`), de modo que no se pierde el fill inicial; al reusar el timestamp del poll previo (no el
del trade más reciente) se garantiza solapamiento y no se pierden fills entre ticks.
