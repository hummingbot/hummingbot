---
id: CORR-006
title: Diff depth sin validación de secuencia U/u/pu ni resync ante gaps
category: correctness
impact: high
effort: M
risk: medium
connector: binance_perpetual
files:
  - hummingbot/connector/derivative/binance_perpetual/binance_perpetual_api_order_book_data_source.py:208
  - hummingbot/connector/derivative/binance_perpetual/binance_perpetual_api_order_book_data_source.py:236
doc_refs:
  - https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly
status: done
commits:
  - "444ac92d0 (fix) validate binance_perpetual order book diff sequence and resync on gap"
created: 2026-06-11
---

## Problema
`_parse_order_book_diff_message` (api_order_book_data_source.py:208-219) aplica cada diff del stream
`@depth` incondicionalmente, usando solo `data["u"]` como `update_id`:

```python
order_book_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, {
    "trading_pair": data["s"],
    "update_id": data["u"],
    "bids": data["b"],
    "asks": data["a"]
}, timestamp=timestamp)
```

La doc oficial ("How to manage a local order book correctly") exige:
1. Descartar eventos con `u` < `lastUpdateId` del snapshot REST.
2. El primer evento procesado debe cumplir `U <= lastUpdateId <= u`.
3. Para cada evento siguiente, `pu` (previous update id) debe ser igual al `u` del evento anterior;
   si no coincide, **re-inicializar desde un snapshot nuevo**.

El connector no valida nada de esto: no lee `U` ni `pu`, y la única recuperación ante un mensaje WS
perdido es el snapshot **horario** de `listen_for_order_book_snapshots` (:236-251). Ante un drop o una
reconexión, el order book local queda corrupto/desfasado hasta 1 hora (niveles fantasma, niveles
ausentes) y las estrategias cotizan contra un book inválido.

## Solución propuesta
- Trackear por trading pair el último `u` aplicado.
- En `_parse_order_book_diff_message`, validar `data["pu"] == último u`. Si hay gap, descartar el diff y
  disparar un snapshot inmediato del par (reusar `_order_book_snapshot` y encolarlo vía
  `_snapshot_messages_queue_key`), reseteando el tracking.
- Incluir `"first_update_id": data["U"]` en el contenido del `OrderBookMessage` para que el tracker pueda
  aplicar la regla `U <= lastUpdateId <= u` contra el snapshot.
- Resetear el estado de secuencia en cada reconexión del WS (`listen_for_subscriptions`).

## Criterio de aceptación
- [x] Un diff cuyo `pu` no coincide con el `u` anterior NO se aplica al book y fuerza un snapshot
      inmediato del par afectado.
- [x] Los diffs con `u` menor al `lastUpdateId` del snapshot se descartan.
- [x] Test unitario que simule un gap de secuencia y verifique el re-sync.
- [x] Sin regresiones en los tests existentes del data source.

## Notas
Verificado contra la doc oficial (fetcheada 2026-06-11). El mismo defecto existe en otros connectors
binance del repo (el spot tampoco valida `pu`), pero en futures la doc es explícita en que `pu` debe
encadenar con el `u` anterior. Riesgo medio: toca el camino caliente de market data — cubrir con tests.

**Implementado (444ac92d0):** validación de `pu` por par en `_parse_order_book_diff_message` (tracking
de `self._last_update_id`), descarte del diff con gap y `first_update_id` (U) en el `OrderBookMessage`.
Reset del tracking en `listen_for_subscriptions` ante reconexión.
- Matiz vs la solución propuesta: el resync no se encola como `OrderBookMessage` directamente desde el
  parser de diffs (eso haría el REST en el hot path). En su lugar, ante un gap se encola el `trading_pair`
  como **señal** en `_snapshot_messages_queue_key`, y `listen_for_order_book_snapshots` la consume
  on-demand (vía `asyncio.wait_for` contra el reset horario) para emitir el snapshot REST fuera del hot
  path. La regla `u < lastUpdateId` la sigue aplicando el tracker base (`snapshot_uid > update_id`), ahora
  bien alimentado por el snapshot fresco.
- Tests añadidos: `test_parse_order_book_diff_message_includes_first_update_id`,
  `test_parse_order_book_diff_message_sequence_gap_forces_resync`,
  `test_listen_for_order_book_snapshots_serves_on_demand_resync_request`. Suite del connector: 106 passed.
