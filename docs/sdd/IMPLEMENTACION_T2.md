# T2 — Implementación completa (2026-09-14)

> **Nota posterior:** en septiembre de 2026 venció la prueba de Azure, el Key Vault quedó deshabilitado y los secretos se movieron a un Lakehouse privado (`lh_secrets`). La versión con Key Vault se conserva en `udf/get_at_realtime_keyvault.py`.

## Resumen
UDF `get_at_realtime` publicada y corriendo automáticamente cada 1 minuto vía Data Pipeline.

## Cambios realizados

### 1. Código de la UDF
- Agregado decorador `@udf.generic_connection(argName="keyVaultClient", audienceType="KeyVault")`
- Integración con `kv-auckland-hazard-hz` para leer `at-subscription-key-2`
- Mantiene lógica original de consulta a AT y envío al Eventstream

### 2. Key Vault
- Secreto `at-subscription-key-2` creado con key de AT regenerada (32 caracteres, vigente)
- Owner-identity del item de UDF ya tiene acceso como owner de la suscripción

### 3. Event Hub
- Connection string regenerada (la anterior quedó expuesta en el chat)
- Nueva clave primaria activa

### 4. Scheduling
- **Scheduler nativo de UDFs:** falló con error `WorkloadException: FunctionName is null or empty` (bug en preview)
- **Workaround adoptado:** Data Pipeline `at-realtime-poller-pipeline` con Schedule Trigger
  - Recurrencia: cada 1 minuto
  - Zona horaria: Auckland (UTC+12)
  - Confirmado: ejecuciones exitosas observadas en Monitoring hub (6:15, 6:16, 6:17... consecutivas)

## Próximos pasos
- T3: crear tabla raw `at_stop_updates_raw` en KQL DB
