# T3 — Hallazgo: JSON anidado del feed AT (2026-09-14)

> **Nota posterior:** la solución propuesta aquí (Data Pipeline + Data Flow) nunca se construyó. Se reemplazó por aplanar el JSON dentro de la UDF, en Python, antes de enviarlo al Eventstream (ver `udf/get_at_realtime.py`).

## Problema detectado

El JSON del feed GTFS-Realtime de AT tiene estructura altamente anidada:
```json
{
  "header": {
    "timestamp": 1234567890
  },
  "entity": [
    {
      "trip_update": {
        "trip": {
          "trip_id": "...",
          "route_id": "...",
          "schedule_relationship": 0
        },
        "stop_time_update": {
          "stop_sequence": 1,
          "arrival": {
            "delay": 120,
            "time": 1234567890
          },
          "departure": {
            "delay": 120,
            "time": 1234567890
          },
          "stop_id": "..."
        }
      }
    }
  ]
}
```

**Problema:** el transformador SQL/KQL del Eventstream no puede acceder a campos anidados como `trip_update.trip.trip_id` de forma confiable. Intentamos:
1. Transformador SQL (código KQL): rechazado por sintaxis incompatible
2. UI "Administrar campos": no reconoce campos anidados en los dropdowns

## Solución adoptada: Data Flow en Data Pipeline

En vez de intentar transformación en el Eventstream, creamos un **Data Pipeline intermedio** con una actividad **Data Flow** (transformador visual más poderoso):

```
Eventstream (at-disruption-stream)
    ↓ [eventos JSON brutos]
Data Pipeline (at-realtime-ingest)
    ↓ [Data Flow: aplanar JSON]
KQL Table (at_stop_updates_raw)
```

**Ventajas:**
- Data Flow tiene UI visual para mappings complejos
- Soporta JSON anidado sin problemas
- Se ejecuta cada vez que llega un evento al Eventstream

## Próximos pasos de implementación

1. Crear Data Pipeline `at-realtime-ingest`
2. Agregar actividad Data Flow con origen = Eventstream `at-disruption-stream`
3. Mapear campos anidados → columnas flat de `at_stop_updates_raw`
4. Configurar destino = tabla KQL `at_stop_updates_raw`
5. Probar con eventos reales del feed AT
