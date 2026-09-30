# Tasks: Detector de Disrupciones en Tiempo Real — Auckland Transport

**Estado:** Borrador v0.1 — Fase 3 (Tasks)
**Deriva de:** `plan-detector-disrupciones-at.md` v0.1
**Última actualización:** 2026-09-13

> **Nota posterior (historial):** este documento quedó en T5. Después: T6 se implementó como una materialized view (`at_route_minute_agg`) más una función (`at_get_route_severity()`), porque una materialized view no puede depender de `now()`; se agregó un filtro de viajes "congelados" (`at_recent_live_updates()`); T7 es el dashboard en `dashboard/`. T8 (validación en hora punta) sigue pendiente. Ver `docs/README.md`.

---

## Cómo leer este documento

Cada tarea es independiente y entregable por sí sola. El orden sugiere dependencias, no es obligatorio ejecutarlas en secuencia estricta salvo donde se indique "bloquea a". Cada tarea referencia el criterio de aceptación de la spec (v1.0) o la sección del plan (v0.1) que la origina, para que Implement nunca se desconecte de la fuente de verdad.

---

## T1 — Confirmar acceso al Key Vault desde la Fabric UDF ✅ COMPLETADA (2026-09-13)

- **Origen:** Plan, sección 6 (riesgo técnico) / Spec, sección 8.
- **Qué hace:** probar en código real la sintaxis de `@udf.generic_connection` para obtener el credential de `kv-auckland-hazard-hz` desde la UDF.
- **Criterio de éxito:** la UDF logra leer el secreto de la subscription key sin hardcodearlo.
- **Resultado:** sintaxis confirmada contra documentación oficial de Fabric (no requirió prueba y error). Detalle completo en Plan, sección 6. Pendiente solo la ejecución manual en el portal (asignar rol "Key Vault Secrets User" e instalar librerías).
- **Bloquea a:** T2.

## T2 — Publicar/actualizar la Fabric UDF `get_at_realtime` ✅ COMPLETADA (2026-09-13)

- **Origen:** Spec, sección 3 (polling 1 min) / Plan, sección 1.
- **Qué hace:** ajustar la función ya probada para que use el secreto vía Key Vault (T1) en vez del valor en texto plano, y programarla con el scheduler cada 1 minuto.
- **Criterio de éxito:** la función corre en el scheduler sin exponer la key en el código.
- **Resultado:** confirmado end-to-end. Secreto `at-subscription-key-2` en `kv-auckland-hazard-hz`, key de AT y connection string del Event Hub regeneradas (ambas habían quedado expuestas en el chat). Prueba real: 3.247 eventos enviados al Eventstream en un solo poll.
- **Pendiente dentro del alcance de T2:** confirmar que el scheduler quede configurado a 1 minuto (no solo probado manualmente).
- **Depende de:** T1.

## T3 — Crear tabla raw `at_stop_updates_raw` en la KQL DB ✅ COMPLETADA (2026-09-16)

- **Origen:** Plan, sección 3.1.
- **Qué hace:** crear la tabla con el schema flat definido y conectar el Eventstream `at-disruption-stream` como destino directo.
- **Hallazgo (JSON anidado):** el feed GTFS-Realtime tiene estructura muy anidada; se pensó que haría falta un Data Pipeline con Data Flow intermedio (ver `HALLAZGO_T3_JSON_ANIDADO.md`), pero finalmente el propio editor de destino del Eventstream reconoció los campos anidados automáticamente al mapear a la tabla flat. El Data Pipeline `at-realtime-ingest` nunca se construyó — quedó descartado por innecesario.
- **Hallazgo (desalineamiento de arquitectura, 2026-09-15/16):** durante la resolución del punto anterior se creó un Eventhouse con una base de datos KQL separada (también llamada `at_stop_updates_raw`), y el destino del Eventstream quedó apuntando ahí en vez de a `at-realtime-db`. Corregido: se recreó la tabla dentro de `at-realtime-db`, se reapuntó el destino del Eventstream (eliminando y recreando el nodo de destino, ya que no es editable in-place), y se eliminaron los ítems sueltos (base de datos hermana, flujos de datos huérfanos `at_flatten_stop_update` y `at_realtime_json_flatten`, y querysets huérfanos).
- **Hallazgo adicional:** el Schedule Trigger de `at-realtime-poller-pipeline` tenía una fecha de fin ya expirada, deteniendo silenciosamente la ingesta. Corregido extendiendo el trigger.
- **Hallazgo de sintaxis KQL:** `datetime(now())` produce `Syntax error: The incomplete fragment is unexpected` en este entorno; `now()` sin envolver funciona correctamente (ya devuelve tipo `datetime`). Usar `now()` a secas en todo el proyecto.
- **Criterio de éxito:** ✅ datos del feed AT llegan transformados a `at_stop_updates_raw` dentro de `at-realtime-db`, con todos los campos mapeados correctamente. Confirmado con 209.274 filas y conteo creciendo en tiempo real.

⚠️ Hallazgo (2026-09-16): la UDF enviaba todas las entidades del feed AT sin filtrar (trip_update, vehicle_position, alert mezcladas), lo cual hacía que el mapeo del Eventstream fuera inestable (dependía de qué tipo de entidad tomara como muestra). Corregido: la UDF ahora filtra solo trip_update y aplana el JSON anidado en Python antes de enviarlo (función flatten_trip_update), en vez de depender del asistente de mapeo del Eventstream para resolver el anidamiento. Esto también vuelve obsoleta la estrategia original de T3 (Data Pipeline + Data Flow) — nunca se implementó y ya no es necesaria.

Decisión de diseño: vehicle_id puede venir vacío (~1% de los casos) cuando AT aún no ha asignado un vehículo físico al trip programado. Estas filas se conservan en la tabla raw (dato válido), pero se excluyen del cálculo de affected_vehicles en T6 mediante where isnotempty(vehicle_id).

Decisión de diseño: feed_timestamp (el campo timestamp del trip_update) no se actualiza si el trip no tiene cambios recientes, por lo que no es confiable como reloj para las ventanas de tiempo. Se usa ingestion_timestamp (generado por la UDF en cada poll) como base de las ventanas de persistencia en T5/T6.

## T4 — Crear tabla de parámetros `at_config_params` ✅ COMPLETADA (2026-09-16)

- **Origen:** Plan, sección 3.3 / Spec, sección 3 (umbral configurable, no hardcodeado).
- **Qué hace:** crear la tabla y cargar el valor inicial de `persistence_threshold_minutes`.
- **Decisión tomada:** valor inicial = 4 minutos (dentro del rango 3–6 acordado en la spec). Diseño key-value genérico (`param_name`/`param_value`/`updated_at`), confirmado para dejar espacio a futuros parámetros (ej. pesos w1/w2/w3 de T5).
- **Nota para T6:** la lectura del umbral debe tomar el valor más reciente por `param_name` (ej. `arg_max(updated_at, param_value)`), ya que `.set-or-append` agrega filas nuevas en vez de sobrescribir — no asumir que hay una sola fila por parámetro.
- **Criterio de éxito:** ✅ el valor se puede cambiar con un `.set-or-append` sin tocar código de la materialized view ni del dashboard. Tabla creada en `at-realtime-db`, verificada con `at_config_params | take 10`.

## T5 — Definir y probar la fórmula de severidad ✅ COMPLETADA (2026-09-17)

- **Resultado:** fórmula validada contra datos reales (ver Plan, sección 4, actualizada). Iteración necesaria tras detectar dos bugs: (1) el tope de amplitud saturaba con demasiada frecuencia (subido de 5 a 8 vehículos), (2) delays negativos (adelantos) generaban severity_score negativo y una lógica de tendencia invertida — corregido con clamping a 0 y comparación por diferencia absoluta en vez de razón/multiplicador.
- **Criterio de éxito:** ✅ rutas con retrasos visiblemente peores obtienen scores más altos; `signals_breakdown` refleja correctamente cuál señal dominó.

## T6 — Crear la materialized view `at_route_severity`

- **Origen:** Plan, sección 3.2.
- **Qué hace:** implementar la vista materializada que agrega por `route_id`, calcula `severity_score` (T5), `trend`, `affected_vehicles`, y determina `is_active` según el umbral de `at_config_params` (T4).
- **Criterio de éxito:** la tabla derivada se actualiza incrementalmente sin recalcular todo el histórico raw.
- **Depende de:** T3, T4, T5.

## T7 — Diseñar y construir el Real-Time Dashboard

- **Origen:** Plan, sección 5 / Spec, sección 3 (tarjetas que aparecen/desaparecen, sin lógica adicional de UI).
- **Qué hace:** crear las tarjetas que consultan directo `at_route_severity` filtrando por `is_active = true`, mostrando severidad, desglose de señales, y tendencia.
- **Criterio de éxito:** una disrupción nueva aparece como tarjeta sin intervención manual, y desaparece sola cuando `is_active` vuelve a `false`.
- **Depende de:** T6.

## T8 — Prueba end-to-end con datos reales en vivo

- **Origen:** Spec completa (validación de todos los criterios de aceptación).
- **Qué hace:** dejar el pipeline corriendo un período (ej. una hora punta de tráfico) y verificar que las tarjetas reflejan disrupciones reales conocidas.
- **Criterio de éxito:** al menos una disrupción real detectada y visible en el dashboard, con desglose de señales coherente.
- **Depende de:** T2, T7.

---

## Fuera de estas tareas (recordatorio)

- Regenerar la subscription key de AT sigue pendiente y es independiente de este flujo — no bloquea ninguna tarea de arriba, pero debe resolverse antes de T8 (prueba en vivo prolongada).
- Fase 2 (Fabric Apps / escritura) no genera tareas en este documento — sigue solo registrada como idea futura.

---

## Próximos pasos

- [ ] Validar contigo el orden y alcance de T1–T8 antes de pasar a Implement.
- [ ] Empezar por T1, dado que es la única dependencia técnica no confirmada de todo el proyecto.
