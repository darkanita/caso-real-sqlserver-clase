# Caso real SQL Server con LangChain y MLflow

Material de clase para implementar y analizar un agente de consultas sobre SQL Server
con descubrimiento progresivo del esquema, controles de solo lectura y PII, interfaz web
y observabilidad con MLflow.

## Documentación

- [Guía de clase](03_laboratorio/src/caso_real_sqlserver/GUIA_CLASE.md)
- [Guía del profesor y publicación](03_laboratorio/src/caso_real_sqlserver/GUIA_PROFESOR_REPOSITORIO.md)
- [Referencia técnica](03_laboratorio/src/caso_real_sqlserver/README.md)

## Inicio rápido

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r 03_laboratorio\src\caso_real_sqlserver\requirements.txt
Copy-Item 03_laboratorio\.env.example 03_laboratorio\.env
```

Complete `03_laboratorio\.env` con credenciales propias y siga la
[guía de clase](03_laboratorio/src/caso_real_sqlserver/GUIA_CLASE.md).

No publique `.env`, credenciales, bases de MLflow, artefactos, trazas ni datos reales.
