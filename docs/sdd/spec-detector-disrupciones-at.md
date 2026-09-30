# Spec: Detector de Disrupciones en Tiempo Real — Auckland Transport

**Estado:** v1.0 — Fase 1 (Specify) congelada
**Última actualización:** 2026-09-13

> **Nota posterior (historial):** este documento refleja la spec al inicio del proyecto. Los umbrales de alerta se recalibraron después con datos reales (retraso de 3 min; niveles a los 5, 10, 15 y 20 min) y los secretos pasaron de Key Vault a un Lakehouse privado. Ver `docs/README.md`.

---

## 1. Contexto y motivación

Proyecto con doble propósito:

1. **Preparación DP-700** — práctica aplicada de Eventstream, KQL Database y Real-Time Dashboard.
2. **Portafolio** — evidencia técnica concreta para postulaciones a Auckland Council (Natural Hazard Data Scientist, Waste Planning Advisor), demostrando manejo de datos en tiempo real sobre un problema público real de NZ.

Se descartaron alternativas simuladas (calidad de agua en playas, denuncias de dumping, sensores de llenado de contenedores) a favor de una fuente **real y pública sin necesidad de simular datos**: el feed GTFS-Realtime de Auckland Transport (AT).

---

## 2. Objetivo del sistema

Detectar y priorizar disrupciones sostenidas en el servicio de transporte público de Auckland (retrasos consistentes en múltiples servicios consecutivos de una misma ruta), a partir del feed en tiempo real de AT, mostrando el resultado en un dashboard operativo.

---

## 3. Criterios de aceptación (estilo EARS — borrador, a confirmar)

> Estos son un punto de partida tomado de las decisiones ya conversadas. Hay que revisarlos y ajustarlos contigo antes de pasar a la fase de Plan.

- El sistema DEBERÁ clasificar cada ruta en uno de 5 niveles de alerta, según cuántos minutos consecutivos el retraso promedio se mantenga sobre el umbral de "vehículo afectado" (`vehicle_delay_threshold_seconds`, 60s):
  - **Sin alerta:** 0-1 minuto consecutivo.
  - **Advertencia:** 2 minutos consecutivos.
  - **Amarilla:** 3 minutos consecutivos.
  - **Naranja:** 4 minutos consecutivos.
  - **Roja:** 5 o más minutos consecutivos.
  Todos los umbrales de minutos son configurables (tabla `at_config_params`), no hardcodeados.
- El sistema DEBERÁ mostrar una tarjeta en el dashboard desde el nivel "Advertencia" en adelante (es decir, `is_active = true` cuando el nivel es distinto de "Sin alerta").
- El sistema DEBERÁ acumular snapshots de `stop_time_update` por `trip_id`/`route_id` en la KQL DB, dado que el feed entrega solo el próximo paradero y no el itinerario completo.
- El sistema DEBERÁ calcular una severidad combinando magnitud del retraso + tendencia + amplitud (cantidad de vehículos afectados de la misma ruta simultáneamente).
- El sistema DEBERÁ mostrar siempre el desglose de qué señal(es) dispararon la severidad (no un número opaco).
- El sistema DEBERÁ considerar una disrupción como "persistente" cuando la señal se mantenga durante un umbral **configurable**, con valor por defecto entre 3 y 6 minutos (recalibrado desde el umbral original de 30 segundos, por el límite de 1 min del scheduler). El umbral no debe quedar hardcodeado en la lógica de detección.
- El Real-Time Dashboard DEBERÁ mostrar tarjetas que aparecen/desaparecen según el estado activo en la KQL DB, sin lógica adicional de UI.
- El sistema NO DEBERÁ requerir acciones de escritura (aceptar/desechar) desde el dashboard, dado que un Real-Time Dashboard es de solo lectura.

---

## 4. Fuera de alcance (por ahora)

- Mapas o visualización geoespacial de las disrupciones.
- Interacción de escritura (aceptar/desechar alertas) — ver Fase 2 registrada abajo.
- Simulación de datos — todo el pipeline usa el feed real de AT.

### Fase 2 (registrada, no bloqueante para esta spec)

- **Idea:** habilitar acciones de escritura (aceptar/desechar disrupciones) desde el dashboard operativo.
- **Camino técnico evaluado:** Fabric Apps (operational), con base SQL administrada + API GraphQL. GA reciente de Build 2026.
- **Por qué queda fuera de esta iteración:** está en preview, probablemente fuera del temario DP-700, y requiere desarrollo tipo código (Rayfin SDK).
- **Estado:** solo registrado como idea futura; no se planifica ni se dimensiona en esta spec.

---

## 5. Restricciones de arquitectura conocidas

- No hay VPS disponible (el que se administraba antes ya no existe) → se descartó notebook Spark con loop infinito.
- Región del tenant: Australia East (coincide con el Key Vault `kv-auckland-hazard-hz` ya existente del proyecto de hazard, que se reutiliza).
- Autenticación al feed de AT vía header `Ocp-Apim-Subscription-Key`, secreto gestionado en Key Vault (no en texto plano).
- Volumen esperado con polling de 1/min ≈ 10.080 llamadas/semana — muy por debajo del límite de 35.000/semana del plan de AT.

---

## 6. Decisiones ya tomadas (para no perderlas)

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| Fuente: AT GTFS-Realtime | GeoNet sísmico, denuncias de dumping simuladas | Datos reales sin simular; mapea directo a contenido del examen (KQL windowing) |
| Captura: Fabric User Data Functions | Notebook Spark con loop infinito | Sin VPS disponible; UDF es GA (feb 2026) y confirmado disponible en la región |
| Secreto: Key Vault + identidad administrada | Key hardcodeada en el código | Seguridad; patrón confirmado por comunidad de Fabric |
| UX: tarjetas dinámicas sin mapas | Mapa interactivo | Real-Time Dashboard es de solo lectura; mantener simple |

---

## 7. Preguntas resueltas

1. **¿Key de AT regenerada?** No, todavía no. ⚠️ **Acción pendiente urgente, fuera del flujo SDD** — regenerar en el portal de AT antes de dejar el sistema corriendo de forma permanente.
2. **Sintaxis de `@udf.generic_connection`:** no se confirma ahora — queda como riesgo técnico documentado (ver sección 9) a resolver en la fase Implement.
3. **Umbral de persistencia:** parametrizable desde el inicio (ver criterio actualizado en sección 3), no hardcodeado.
4. **Fase 2 (Fabric Apps / escritura):** registrada como idea futura (ver sección 4), no bloqueante ni planificada en esta spec.

---

## 8. Riesgos técnicos conocidos (a resolver en fase Implement)

| Riesgo | Detalle | Impacto si no se resuelve como se espera |
|---|---|---|
| Sintaxis `@udf.generic_connection` no confirmada | La forma de obtener el `credential` desde `FabricItem` (`.connection` vs `.get_credential()` u otra) es una estimación, no una API documentada end-to-end | Puede requerir ajuste por prueba y error durante Implement; no bloquea la spec |
| Key de AT sin regenerar | Key expuesta en texto plano en un chat anterior sigue activa | Riesgo de seguridad activo, independiente del cronograma del proyecto |

---

## 9. Próximos pasos

- [ ] Regenerar la subscription key de AT (independiente del SDD, prioridad inmediata).
- [ ] Congelar esta spec como v1.0.
- [ ] Pasar a la fase **Plan**: arquitectura técnica detallada (modelo de datos KQL, contrato del evento en el Eventstream, diseño exacto del Real-Time Dashboard, y parámetro configurable del umbral de persistencia).
- [ ] Considerar mover la spec y el código a un repo Git como fuente de verdad versionada, en línea con el espíritu del SDD (spec versionada, no atada al historial de un chat).
