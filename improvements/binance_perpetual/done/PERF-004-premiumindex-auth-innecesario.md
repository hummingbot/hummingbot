---
id: PERF-004
title: _request_complete_funding_info firma un endpoint público (premiumIndex)
category: performance
impact: low
effort: S
risk: low
status: done
connector: binance_perpetual
files:
  - hummingbot/connector/derivative/binance_perpetual/binance_perpetual_api_order_book_data_source.py:270
doc_refs:
  - https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price
commits:
  - "b661267b7 (perf) binance_perpetual: drop unnecessary auth on premiumIndex funding info request"
created: 2026-06-10
---

## Problema
`_request_complete_funding_info` llama al endpoint de mark price (`/fapi/v1/premiumIndex`, `MARK_PRICE_URL`)
con `is_auth_required=True`:

```python
data = await self._connector._api_get(
    path_url=CONSTANTS.MARK_PRICE_URL,
    params={"symbol": ex_trading_pair},
    is_auth_required=True)
```

La doc oficial marca `premiumIndex` como **público** (no requiere API key ni firma; weight 1 con symbol).
Firmar agrega `timestamp` + firma HMAC innecesarios y obliga a sincronización de tiempo en una llamada de
market data. Es además **inconsistente** con `_fetch_last_fee_payment` (derivative.py:790), que llama el
mismo endpoint SIN auth.

## Solución propuesta
Quitar `is_auth_required=True` de la llamada:

```python
data = await self._connector._api_get(
    path_url=CONSTANTS.MARK_PRICE_URL,
    params={"symbol": ex_trading_pair})
```

## Criterio de aceptación
- [x] La llamada a `MARK_PRICE_URL` en `_request_complete_funding_info` ya no firma el request.
- [x] `get_funding_info` sigue devolviendo `index_price`, `mark_price`, `next_funding_utc_timestamp` y
      `rate` correctos.
- [x] No se rompe ningún test existente.

## Notas
Cambio de bajo riesgo y bajo impacto (correctitud de patrón + un poco menos de overhead). Verificado contra
la doc oficial de Mark Price.
