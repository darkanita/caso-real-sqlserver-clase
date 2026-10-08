# Caso real: agente de planeación y asignación militar

Este proyecto consulta `MilitaryResAllocDB`, una base SQL Server con esquema real y
datos sintéticos. La inspección inicial encontró:

- 130 tablas en `dbo`.
- 1.119 columnas.
- 195 relaciones foráneas.
- 130 tablas legibles por la cuenta de ejecución.
- 0 tablas con permisos `INSERT`, `UPDATE`, `DELETE` o `ALTER`.

El objetivo es responder preguntas analíticas sobre personal, grados, carreras,
especialidades, solicitudes y proyecciones sin exponer información personal.

## Guías

- [Guía de clase](GUIA_CLASE.md): recorrido didáctico completo, introducción a MLflow,
  explicación archivo por archivo, ejecución, pruebas y actividades.
- [Guía del profesor](GUIA_PROFESOR_REPOSITORIO.md): preparación de un repositorio
  funcional, revisión de secretos, publicación en GitHub y entrega a estudiantes.

## Arquitectura

```text
Página web
   │
   ▼
service.py ───────────────► MLflow autenticado
   │
   ▼
agent.py
   ├── search_schema
   ├── describe_table
   └── run_readonly_sql
           │
           ▼
security.py ──► database.py ──► SQL Server
```

| Archivo | Responsabilidad |
|---|---|
| `config.py` | Configuración sin secretos |
| `catalog.py` | Catálogo vivo de tablas, columnas y relaciones |
| `security.py` | Valida el AST SQL y bloquea escritura y PII |
| `database.py` | Conecta, verifica permisos, limita tiempo/filas y hace rollback |
| `agent.py` | Herramientas y agente LangChain |
| `service.py` | Orquesta modelo, agente, métricas y MLflow |
| `tracking.py` | Un run autenticado por pregunta |
| `web.py` / `web.html` | API local e interfaz |
| `mlflow_server.py` | Servidor MLflow con `basic-auth` |

## Seguridad aplicada

1. La cadena de conexión vive solo en `03_laboratorio\.env`.
2. La aplicación verifica que la base sea `MilitaryResAllocDB`.
3. El inicio falla si alguna tabla concede escritura a la cuenta.
4. SQLGlot exige una sola consulta `SELECT`.
5. Se rechazan DDL, DML, otras bases, esquemas y tablas sensibles.
6. Se rechaza `SELECT *`.
7. Columnas de identificación, nombres personales, contacto, dirección y nacimiento
   están bloqueadas.
8. Las tablas de personas solo admiten resultados agregados.
9. Cada consulta tiene timeout de 10 segundos y devuelve máximo 50 filas.
10. Toda conexión termina con rollback y cierre.
11. MLflow exige usuario y contraseña.

Los controles de aplicación complementan, pero no sustituyen, una cuenta SQL Server
dedicada exclusivamente a lectura.

## Instalación

Desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m pip install `
  -r 03_laboratorio\src\caso_real_sqlserver\requirements.txt
```

También se requiere **Microsoft ODBC Driver 18 for SQL Server**.

## Configuración

Completa `03_laboratorio\.env` sin subirlo a Git:

```text
LLM_BACKEND=groq
GROQ_MODEL=openai/gpt-oss-20b
GROQ_API_KEY=tu_clave_nueva

MILITARY_SQLSERVER_CONNECTION_STRING=DRIVER={ODBC Driver 18 for SQL Server};SERVER=servidor,puerto;DATABASE=MilitaryResAllocDB;UID=usuario_solo_lectura;PWD=contraseña;Encrypt=yes;TrustServerCertificate=yes;ApplicationIntent=ReadOnly

MLFLOW_TRACKING_URI=http://127.0.0.1:5000
MLFLOW_TRACKING_USERNAME=admin
MLFLOW_TRACKING_PASSWORD=contraseña_mlflow_de_12_o_mas
MLFLOW_FLASK_SERVER_SECRET_KEY=secreto_aleatorio_de_32_o_mas
```

No reutilices la clave del modelo como contraseña de SQL Server o MLflow.

## Ejecutar MLflow autenticado

Terminal 1:

```powershell
.\.venv\Scripts\python.exe `
  03_laboratorio\src\caso_real_sqlserver\run_mlflow.py
```

Abre `http://127.0.0.1:5000` e inicia sesión. Los usuarios y permisos se guardan en
`03_laboratorio\outputs\caso_real_sqlserver\basic_auth.db`; los runs se guardan en
`mlflow.db`.

La autenticación básica sobre HTTP es solo para acceso local. Para publicar MLflow,
usa HTTPS mediante un proxy inverso y un gestor de secretos.

## Ejecutar la interfaz web

Terminal 2:

```powershell
.\.venv\Scripts\python.exe `
  03_laboratorio\src\caso_real_sqlserver\run_web.py
```

Abre `http://127.0.0.1:8780`.

La página solicita el usuario que ejecuta la pregunta y muestra respuesta, SQL validado,
filas verificables, modelo, tiempo, tokens, herramientas, tablas consultadas, enlace al
run de MLflow e histórico de la sesión.

## Ejecutar desde terminal

```powershell
.\.venv\Scripts\python.exe `
  03_laboratorio\src\caso_real_sqlserver\run_cli.py `
  --user nombre.apellido `
  --question "¿Cuántas personas hay por estado laboral?"
```

Usa `--no-mlflow` únicamente para pruebas locales sin observabilidad.

## Preguntas sugeridas

- ¿Cuántas personas hay por estado laboral?
- ¿Cuántos hombres y mujeres hay por grado?
- ¿Cuáles son los 10 grados con más personal?
- ¿Cuántas personas hay por especialidad?
- ¿Cuál es el total solicitado en las solicitudes de personal?
- ¿Cuántas solicitudes existen por área de conocimiento?
- ¿Cuántas proyecciones existen por año?
- ¿Qué carreras aparecen con mayor frecuencia en las proyecciones?
- ¿Cuántas posiciones ocupadas hay por dependencia?

No solicites listados nominales, identificaciones, teléfonos, correos o direcciones.

## MLflow

El experimento se llama `military-resource-allocation-agent`.

Cada run registra:

| Campo | Significado |
|---|---|
| `trace.created_by` | Usuario escrito en la página o enviado con `--user` |
| `trace.mlflow_writer` | Cuenta autenticada que escribió en MLflow |
| `trace.identity_assurance` | `self-declared`, porque la web no autentica al usuario |
| `requested_by` | Parámetro buscable con el usuario solicitante |

La cuenta MLflow sí está autenticada. El usuario solicitante es declarativo hasta que
la interfaz se integre con un proveedor de identidad corporativo.

En nivel `metrics` se registran hashes, modelo, tiempos, tokens, llamadas y número de
tablas/filas, pero no la pregunta, SQL, respuesta o filas. En nivel `traces` se
registran esos contenidos para depuración; úsalo únicamente con preguntas aprobadas.
