---
id: PERF-007
title: ORDER_URL comparte limit_id entre GET/POST/DELETE y el polling consume el cupo de órdenes
category: performance
impact: medium
effort: S
risk: low
status: done
connector: binance_perpetual
files:
  - hummingbot/connector/derivative/binance_perpetual/binance_perpetual_constants.py:108
  - hummingbot/connector/derivative/binance_perpetual/binance_perpetual_derivative.py:694
doc_refs:
  - https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api
  - https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Query-Order
commits:
  - "965dcfcd5 (perf) split binance_perpetual ORDER_URL rate limit by verb"
created: 2026-06-11
---

## Problema
El `RateLimit` de `ORDER_URL` (constants.py:108-111) linkea los tres pools para cualquier verbo:

```python
RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
          linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1),
                         LinkedLimitWeightPair(ORDERS_1MIN, weight=1),
                         LinkedLimitWeightPair(ORDERS_1SEC, weight=1)]),
```

y ese mismo `limit_id` lo usan `_place_order` (POST), `_place_cancel` (DELETE),
`_request_order_status` (GET, derivative.py:331) y `_update_order_status` (GET en batch,
derivative.py:694-705).

La doc oficial dice:
- **Query Order (GET /fapi/v1/order)**: weight 1 en IP, **no** consume el order-count
  (`X-MBX-ORDER-COUNT-*`).
- **New Order (POST /fapi/v1/order)**: weight **0 en IP**, 1 en order-count 10s y 1m.

Impacto: con N órdenes activas, cada tick de polling de status (cada 10 s) quema N unidades de
`ORDERS_1SEC` (300/10s) y `ORDERS_1MIN` (1200/min) en el throttler local, **auto-throttleando la
colocación y cancelación real de órdenes** sin que el exchange lo exija. A la inversa, los POST quedan
sobre-cargados en `REQUEST_WEIGHT`.

## Solución propuesta
Separar limit_ids por verbo, siguiendo el patrón ya usado para position mode
(`POST_POSITION_MODE_LIMIT_ID`/`GET_POSITION_MODE_LIMIT_ID`, constants.py:44-45):

- `GET{ORDER_URL}`: linked a `REQUEST_WEIGHT` weight 1 (sin order-count).
- `POST{ORDER_URL}`: linked a `ORDERS_1MIN` 1 + `ORDERS_1SEC` 1 (IP weight 0 según doc; si el throttler
  no soporta weight 0, dejar 1 como margen conservador).
- `DELETE{ORDER_URL}`: linked a `REQUEST_WEIGHT` weight 1 (verificar contra doc si cancel consume
  order-count; la página de Cancel Order no fue fetcheada en esta revisión).

Pasar `limit_id=...` explícito en `_place_order`, `_place_cancel`, `_request_order_status` y
`_update_order_status`. Mismo hallazgo que `improvements/binance/todo/PERF-002` en el connector spot.

## Criterio de aceptación
- [x] El polling de status de órdenes ya no consume `ORDERS_1MIN`/`ORDERS_1SEC` en el throttler.
- [x] POST y DELETE siguen limitados por los pools que la doc indica para cada verbo.
- [x] Tests de rate limits / derivative ajustados a los nuevos limit_ids.

## Notas
GET y POST verificados contra doc oficial (2026-06-11). DELETE (Cancel Order) verificado contra
la página oficial "Cancel Order" durante la implementación: weight 1 en IP, sin consumo de
order-count. Implementado con limit_ids dedicados `GET{ORDER_URL}` / `POST{ORDER_URL}` /
`DELETE{ORDER_URL}` y pasados explícitamente en `_place_order`, `_place_cancel`,
`_request_order_status` y `_update_order_status`. POST conserva weight 1 en `REQUEST_WEIGHT`
como margen conservador (la doc indica 0). Tests: suite del connector 107 passed (incluye el
nuevo `test_order_url_rate_limits_split_by_verb`).
