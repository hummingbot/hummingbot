---
id: CORR-001
title: available_balance derivado del WS se sobreestima (usa cw como disponible)
category: correctness
impact: high
effort: S
risk: low
status: done
connector: binance_perpetual
files:
  - hummingbot/connector/derivative/binance_perpetual/binance_perpetual_derivative.py:442
doc_refs:
  - https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams
commits: []
created: 2026-06-10
---

## Problema
En el manejo del evento `ACCOUNT_UPDATE` (`_process_user_stream_event`), el balance disponible se
deriva del campo `cw` del payload:

```python
self._account_balances[asset_name] = Decimal(asset["wb"])           # wallet balance
self._account_available_balances[asset_name] = Decimal(asset["cw"])  # cross wallet balance
```

El payload de `ACCOUNT_UPDATE` solo trae `wb` (Wallet Balance), `cw` (Cross Wallet Balance) y `bc`
(Balance Change). **No existe un campo de "available balance"** en el evento. `cw` es el balance cross
total y NO descuenta el margen inicial de posiciones/órdenes abiertas. Por lo tanto, entre polls REST,
`_account_available_balances` queda **inflado** cuando hay posición/órdenes abiertas. El poll REST
`_update_balances` (línea ~587) sí usa el campo correcto `availableBalance`, así que ambos caminos se
contradicen y el WS gana hasta el próximo poll.

## Solución propuesta
El available balance no es derivable del evento WS, así que no hay que pisarlo con un valor incorrecto.
Opciones (de menor a mayor esfuerzo):
1. En `ACCOUNT_UPDATE`, actualizar solo `_account_balances` (con `wb`) y **no** tocar
   `_account_available_balances` — dejar que el poll REST (`_update_balances`) sea la fuente de verdad
   del disponible.
2. Alternativamente, disparar un refresh de balances (`safe_ensure_future(self._update_balances())`) al
   recibir `ACCOUNT_UPDATE` para acortar la ventana de desincronización.

Preferir la opción 1 (más simple y sin I/O extra).

## Criterio de aceptación
- [x] El handler de `ACCOUNT_UPDATE` ya no setea `_account_available_balances` con `cw`.
- [x] El disponible reportado por el connector con posición abierta coincide con `availableBalance` del
      REST (no con el wallet balance cross).
- [x] Test de `_user_stream_event_listener` para `ACCOUNT_UPDATE` ajustado/añadido que verifique el
      comportamiento.
- [x] No se rompe ningún test existente.

## Notas
Verificado contra la doc oficial de User Data Streams (estructura del evento `ACCOUNT_UPDATE`: campos
`a.B[].{a,wb,cw,bc}`). El total (`_account_balances`) sí es correcto con `wb`; el bug es solo en el
disponible.

Se implementó la opción 1 (la preferida): en `_process_user_stream_event`, el branch `ACCOUNT_UPDATE`
ahora solo actualiza `_account_balances` con `wb` y ya no toca `_account_available_balances`; el poll REST
`_update_balances` queda como única fuente de verdad del disponible. Se añadió un comentario explicativo en
el código. No había ningún test que asserteara el comportamiento viejo (los helpers
`_get_account_update_ws_event_single_position_dict` estaban definidos pero sin usar en el test file de
binance_perpetual), así que se agregó un test nuevo
(`test_account_update_event_does_not_overwrite_available_balance_with_cross_wallet`) que verifica que el
total se actualiza con `wb` y el disponible NO se pisa con `cw`. No hubo desvíos respecto a la solución
propuesta.
