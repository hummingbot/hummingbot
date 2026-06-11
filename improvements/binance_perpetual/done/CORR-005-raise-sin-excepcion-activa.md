---
id: CORR-005
title: raise sin excepción activa en el loop de gestión del listen key
category: correctness
impact: low
effort: S
risk: low
status: done
connector: binance_perpetual
files:
  - hummingbot/connector/derivative/binance_perpetual/binance_perpetual_user_stream_data_source.py:135
doc_refs: []
commits:
  - "bb7628631 (fix) raise explicit IOError instead of bare raise in binance_perpetual listen key loop"
created: 2026-06-10
---

## Problema
En `_manage_listen_key_task_loop`, cuando el refresh (ping) del listen key falla, la rama `else` ejecuta un
`raise` desnudo:

```python
success = await self._ping_listen_key()
if success:
    ...
else:
    self.logger().error(f"Failed to refresh listen key {self._current_listen_key}. Getting new key...")
    raise
    # Continue to next iteration which will get a new key
```

Ese `raise` **no está dentro de un `except`**, por lo que no hay excepción activa para re-lanzar: Python
levanta `RuntimeError("No active exception to re-raise")`. Lo "salva" por accidente el `except Exception as e`
del final del loop (línea ~142), que resetea la key y reintenta — así que el efecto buscado (obtener una key
nueva) ocurre, pero a través de un `RuntimeError` engañoso que ensucia los logs y es frágil ante refactors.

## Solución propuesta
Reemplazar el `raise` desnudo por una excepción explícita y descriptiva, o por un reset directo de estado:

```python
else:
    self.logger().error(f"Failed to refresh listen key {self._current_listen_key}. Getting new key...")
    raise IOError(f"Failed to refresh listen key {self._current_listen_key}")
```

(El `except Exception` existente seguirá reseteando `_current_listen_key` y reintentando, ahora con un
mensaje correcto.)

## Criterio de aceptación
- [x] El fallo de refresh ya no produce `RuntimeError: No active exception to re-raise`.
- [x] Ante fallo de refresh, el loop sigue reseteando la key y obteniendo una nueva (comportamiento
      observable sin cambios).
- [x] Test que simule `_ping_listen_key` devolviendo False y verifique el manejo.

## Notas
Bug latente / code smell: hoy funciona por accidente. Bajo impacto pero trivial de corregir y mejora la
señal en los logs.

Resuelto tal como se propuso: `raise` desnudo reemplazado por `raise IOError(f"Failed to refresh listen
key {self._current_listen_key}")`. El `except Exception` del loop lo captura, resetea `_current_listen_key`
y reintenta. Se reforzó el test existente `test_manage_listen_key_task_loop_keep_alive_failed` para verificar
el mensaje de error correcto y la ausencia de `No active exception to re-raise`.
