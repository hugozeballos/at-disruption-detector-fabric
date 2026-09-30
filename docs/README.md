# Project documents (Spec-Driven Development)

This project was built with Spec-Driven Development: a written spec was the source of truth, a task list derived from it, and every finding during implementation was written back into the documents before the code changed.

The files in `sdd/` are kept as a record of that process. They are in Spanish and reflect the project as of mid-September 2026, so some values changed afterwards:

| Document | What it is | Superseded by |
| --- | --- | --- |
| `sdd/spec-detector-disrupciones-at.md` | Goals, acceptance criteria, scope and early decisions (v1.0) | Alert thresholds were later recalibrated (now 5/10/15/20 min, 3-min delay); see `kql/02_config_params.kql` |
| `sdd/tasks-detector-disrupciones-at.md` | Tasks T1–T8 with the findings of T1–T5 | T6 became a materialized view **plus** a function (a view cannot use `now()`); T7 is the dashboard in `dashboard/` |
| `sdd/IMPLEMENTACION_T2.md` | How the UDF and its schedule were first implemented (Key Vault version) | Secrets later moved to a Lakehouse when the Azure trial ended |
| `sdd/HALLAZGO_T3_JSON_ANIDADO.md` | The nested-JSON problem and a first proposed fix (Data Pipeline + Dataflow) | Never built: the UDF now flattens the JSON in Python before sending it |

The main [README](../README.md) describes the final system.
