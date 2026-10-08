# Clase: agente seguro para consultar SQL Server y observarlo con MLflow

## 1. Propósito de la clase

En esta clase se implementa y analiza un agente que recibe una pregunta en español,
descubre el esquema de una base SQL Server, genera una consulta y devuelve una respuesta
verificable. El caso usa `MilitaryResAllocDB`, una base con esquema real y datos
sintéticos.

El reto no consiste solamente en pedirle SQL a un modelo. El sistema debe:

- trabajar con más de 100 tablas sin enviar todo el esquema al modelo;
- impedir escrituras incluso si el modelo intenta hacerlas;
- bloquear datos personales (PII);
- limitar consultas, filas y llamadas al modelo;
- mostrar el SQL y las filas que sustentan la respuesta;
- registrar métricas y evidencias de cada ejecución en MLflow.

Al terminar podrán explicar qué decide el modelo, qué controla el código y cómo MLflow
permite revisar una ejecución.

## 2. Requisitos previos

- Python 3.11.
- Microsoft ODBC Driver 18 for SQL Server.
- Acceso a `MilitaryResAllocDB` con una cuenta dedicada de **solo lectura**.
- Una clave para uno de los backends admitidos: Groq, OpenAI o un modelo local.
- El repositorio completo, porque este caso reutiliza módulos de otros temas.

Desde la raíz del repositorio:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r 03_laboratorio\src\caso_real_sqlserver\requirements.txt
python -m pip check
```

La cadena de dependencias es:

```text
caso_real_sqlserver\requirements.txt
└── requirements-mlflow.txt
    └── requirements.txt
```

Además de las librerías generales instala `pyodbc`, `sqlglot` y `mlflow[auth]`.

## 3. Configuración segura

Copien el ejemplo de variables de entorno:

```powershell
Copy-Item 03_laboratorio\.env.example 03_laboratorio\.env
```

Completen en `03_laboratorio\.env`:

```text
LLM_BACKEND=groq
GROQ_MODEL=openai/gpt-oss-20b
GROQ_API_KEY=tu_clave

MILITARY_SQLSERVER_CONNECTION_STRING=DRIVER={ODBC Driver 18 for SQL Server};SERVER=servidor,puerto;DATABASE=MilitaryResAllocDB;UID=usuario_solo_lectura;PWD=tu_clave_sql;Encrypt=yes;TrustServerCertificate=yes;ApplicationIntent=ReadOnly

MLFLOW_TRACKING_URI=http://127.0.0.1:5000
MLFLOW_TRACKING_USERNAME=admin
MLFLOW_TRACKING_PASSWORD=una_contraseña_de_12_o_mas
MLFLOW_FLASK_SERVER_SECRET_KEY=un_secreto_aleatorio_de_32_o_mas
```

Reglas:

1. No suban `03_laboratorio\.env` a Git.
2. No escriban claves dentro de archivos `.py`, `.html` o `.md`.
3. No reutilicen la clave del modelo para SQL Server o MLflow.
4. `ApplicationIntent=ReadOnly` ayuda, pero no reemplaza los permisos de solo lectura
   configurados en SQL Server.

## 4. Arquitectura que van a estudiar

```text
Usuario
  ├── navegador ──► web.html ──► web.py
  └── terminal ─────────────────► cli.py
                                    │
                                    ▼
                                service.py
                         ┌──────────┴──────────┐
                         ▼                     ▼
                     agent.py             tracking.py
                  herramientas del         cliente MLflow
                       agente                   │
                         │                      ▼
                         ▼                servidor MLflow
                    database.py           mlflow_server.py
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
          catalog.py            security.py
              │                     │
              └──────────┬──────────┘
                         ▼
                    SQL Server
```

El flujo de una pregunta es:

1. `web.py` o `cli.py` valida la entrada.
2. `service.py` carga el backend, inicia la traza y abre un run de MLflow.
3. `agent.py` permite que el modelo use tres herramientas.
4. `catalog.py` busca tablas y describe columnas/relaciones sin mostrar PII.
5. `security.py` analiza el SQL antes de ejecutarlo.
6. `database.py` comprueba permisos, ejecuta con timeout, limita filas y hace rollback.
7. `service.py` arma la respuesta y las métricas.
8. `tracking.py` guarda en MLflow el resultado permitido por el nivel seleccionado.

## 5. ¿Qué es MLflow?

MLflow es una plataforma de seguimiento de experimentos y ejecuciones de sistemas de
machine learning e IA. En este caso no se usa para entrenar un modelo. Se usa como
**bitácora de observabilidad** del agente.

Una ejecución en MLflow se llama **run**. Varios runs relacionados se agrupan en un
**experiment**. Este proyecto usa el experimento
`military-resource-allocation-agent`.

| Concepto de MLflow | Qué representa en este caso |
|---|---|
| Experiment | El conjunto de consultas hechas por este agente |
| Run | Una pregunta ejecutada por un usuario |
| Parameter | Configuración que no cambia durante el run: modelo, proveedor, límites |
| Metric | Valor numérico: duración, tokens, filas, llamadas |
| Tag | Etiqueta para filtrar: usuario, estado, política de seguridad |
| Artifact | Archivo asociado: prompt del sistema o resumen JSON |
| Trace | Detalle de llamadas del agente y herramientas cuando se habilita |

MLflow permite contestar preguntas operativas como:

- ¿qué modelo se utilizó?;
- ¿cuánto tardó y cuántos tokens consumió?;
- ¿qué tablas consultó?;
- ¿la ejecución terminó o falló?;
- ¿quién declaró haber solicitado la consulta?;
- ¿qué cambió entre dos ejecuciones?

### Dónde aparece MLflow en el código

- `mlflow_server.py`: levanta el servidor local con autenticación básica y almacenamiento
  SQLite.
- `tracking.py`: crea y cierra cada run, registra parámetros, métricas, etiquetas y
  artefactos.
- `service.py`: llama `tracker.start(...)`, `tracker.finish(...)` y
  `tracker.fail(...)`.
- `cli.py`: ofrece `--no-mlflow` y `--mlflow-level`.
- `web.py`: acepta `mlflow` y `mlflow_level` en la petición.
- `web.html`: muestra el selector y el enlace al run.
- `config.py`: valida la URL y las credenciales del cliente MLflow.
- `run_mlflow.py`: permite arrancar el servidor directamente.

### `metrics` frente a `traces`

El nivel predeterminado es `metrics`.

| Nivel | Registra | No registra |
|---|---|---|
| `metrics` | hashes, proveedor, modelo, tiempos, tokens, llamadas, tablas y cantidad de filas | pregunta, SQL, respuesta y contenido de las filas |
| `traces` | todo lo anterior, más pregunta, SQL, respuesta, filas y trazas LangChain | no debe usarse con preguntas o resultados no aprobados |

Un hash permite comprobar si dos textos son iguales sin guardar el texto original. No
es cifrado ni permite recuperar la pregunta.

## 6. Inventario completo de la carpeta

| Archivo o carpeta | Explicación |
|---|---|
| `README.md` | Referencia rápida de arquitectura, instalación, seguridad y ejecución |
| `GUIA_CLASE.md` | Esta guía para desarrollar la clase |
| `GUIA_PROFESOR_REPOSITORIO.md` | Guía del docente para publicar el material |
| `__init__.py` | Declara `caso_real_sqlserver` como paquete Python |
| `config.py` | Constantes, prompt del sistema, rutas y validación de configuración |
| `catalog.py` | Lee tablas, columnas, llaves y relaciones; busca contexto por términos |
| `security.py` | Analiza el AST de SQL y aplica la política de solo lectura y anti-PII |
| `database.py` | Conecta por ODBC, revisa permisos, ejecuta y limita resultados |
| `agent.py` | Define herramientas, crea el agente LangChain y procesa sus mensajes |
| `service.py` | Caso de uso central compartido por CLI y web |
| `tracking.py` | Integración cliente con MLflow |
| `mlflow_server.py` | Configuración y lanzamiento de MLflow autenticado |
| `cli.py` | Argumentos y presentación de resultados en terminal |
| `web.py` | Servidor HTTP local, API, validación e histórico en memoria |
| `web.html` | Interfaz web sin framework de frontend |
| `run_cli.py` | Lanzador directo de `cli.py` |
| `run_web.py` | Lanzador directo de `web.py` |
| `run_mlflow.py` | Lanzador directo de `mlflow_server.py` |
| `requirements.txt` | Dependencias específicas y referencia a dependencias generales |
| `__pycache__\` | Archivos compilados generados por Python; no se estudian ni se suben |

## 7. Recorrido de implementación

### Paso 1: configuración y prompt (`config.py`)

Revisen:

- límites `MAX_ROWS`, `QUERY_TIMEOUT_SECONDS` y `MAX_QUESTION_LENGTH`;
- `SYSTEM_PROMPT`, que orienta al modelo, pero no constituye una barrera de seguridad;
- `connection_string()`, que exige la conexión desde el entorno;
- `validate_actor()`, que valida el identificador declarado por el usuario;
- `validate_mlflow_auth()`, que exige URL y credenciales de MLflow.

**Idea clave:** el prompt indica lo que el modelo debería hacer. `security.py` y los
permisos de SQL Server determinan lo que realmente puede hacer.

### Paso 2: catálogo progresivo (`catalog.py`)

`SchemaCatalog` consulta las vistas de sistema de SQL Server y construye:

- `tables`: columnas, tipos, nulabilidad y llave primaria;
- `relationships`: relaciones de llave foránea;
- `allowed_tables`: tablas disponibles menos las bloqueadas.

`search()` amplía términos españoles con `SEARCH_SYNONYMS`, puntúa coincidencias y
devuelve pocas tablas relevantes. `describe()` oculta columnas sensibles y, cuando se
solicita, incluye relaciones.

Esto evita enviar 130 tablas y 1.119 columnas al modelo en cada pregunta.

### Paso 3: política SQL (`security.py`)

`validate_readonly_sql()` usa SQLGlot para convertir el texto SQL en un árbol sintáctico
(AST). Después comprueba:

- exactamente una consulta;
- que sea una consulta y no DDL/DML;
- tablas y esquema autorizados;
- ausencia de tablas y columnas sensibles;
- ausencia de funciones que revelen contexto de sesión;
- ausencia de `SELECT *`, excepto `COUNT(*)`;
- agregación obligatoria en tablas de personas.

La función devuelve `ValidatedQuery` únicamente si supera todos los controles.

### Paso 4: defensa en profundidad (`database.py`)

`MilitaryDatabase.initialize()`:

1. verifica que la conexión apunta a `MilitaryResAllocDB`;
2. comprueba que existe acceso de lectura;
3. rechaza la cuenta si detecta `INSERT`, `UPDATE`, `DELETE` o `ALTER`;
4. carga el catálogo.

`query()` vuelve a validar el SQL, aplica timeout, toma máximo 50 filas, serializa fechas,
decimales y binarios, y siempre ejecuta rollback y cierre.

### Paso 5: agente y herramientas (`agent.py`)

El agente dispone únicamente de:

| Herramienta | Función |
|---|---|
| `search_schema` | Encontrar tablas y columnas por concepto |
| `describe_table` | Conocer columnas seguras y relaciones |
| `run_readonly_sql` | Validar y ejecutar un `SELECT` |

`ToolCallLimitMiddleware` limita herramientas a 7 y `ModelCallLimitMiddleware` limita
llamadas al modelo a 8. `ask()` inspecciona los mensajes y extrae respuesta, último SQL,
filas, tablas, resultados de herramientas y cantidad de llamadas.

### Paso 6: orquestación (`service.py`)

`execute()` es el punto central:

1. valida pregunta y usuario;
2. crea backend, base, traza local y tracker de MLflow;
3. ejecuta el agente;
4. calcula tiempos, llamadas, tokens, filas y tablas;
5. termina correctamente el run o lo marca como fallido.

La CLI y la web llaman esta misma función, por lo que no duplican la lógica de negocio.

### Paso 7: interfaces (`cli.py`, `web.py`, `web.html`)

La CLI admite pregunta, usuario, backend, nivel de MLflow y ejecución sin MLflow.

La web:

- sirve archivos solo en `127.0.0.1`;
- publica `GET /api/config`, `GET /api/runs` y `POST /api/ask`;
- exige JSON, limita el tamaño de la petición y valida sus campos;
- permite una sola pregunta simultánea con `RUN_LOCK`;
- conserva los últimos 30 resultados en memoria, no en disco.

`web.html` consume esos endpoints, construye tablas con `textContent` y muestra métricas,
SQL, filas, histórico y enlace a MLflow.

### Paso 8: servidor MLflow (`mlflow_server.py`)

El lanzador:

- solo acepta una dirección local;
- crea `mlflow.db`, `basic_auth.db` y `artifacts\` dentro de `outputs`;
- elimina del proceso servidor secretos que no necesita;
- arranca `mlflow server --app-name basic-auth`;
- usa un solo worker y restringe los hosts permitidos.

Los datos generados quedan fuera de Git porque `**/outputs/` está ignorado.

## 8. Ejecución del laboratorio

### Terminal 1: MLflow

```powershell
.\.venv\Scripts\python.exe 03_laboratorio\src\caso_real_sqlserver\run_mlflow.py
```

Abran <http://127.0.0.1:5000> e ingresen con
`MLFLOW_TRACKING_USERNAME` y `MLFLOW_TRACKING_PASSWORD`.

### Terminal 2: aplicación web

```powershell
.\.venv\Scripts\python.exe 03_laboratorio\src\caso_real_sqlserver\run_web.py
```

Abran <http://127.0.0.1:8780>, escriban un usuario y ejecuten:

> ¿Cuántas personas hay por estado laboral?

Comprueben en la página:

1. respuesta explicada;
2. SQL generado;
3. filas verificables;
4. tablas y métricas;
5. enlace al run de MLflow.

### Alternativa: terminal

```powershell
.\.venv\Scripts\python.exe `
  03_laboratorio\src\caso_real_sqlserver\run_cli.py `
  --user estudiante.01 `
  --question "¿Cuáles son los 10 grados con más personal?" `
  --mlflow-level metrics
```

Para una prueba local sin MLflow se puede agregar `--no-mlflow`. No debe ser la opción
normal de una demostración de observabilidad.

## 9. Cómo leer un run en MLflow

1. Abran el experimento `military-resource-allocation-agent`.
2. Seleccionen el run más reciente.
3. Revisen **Parameters**: proveedor, modelo, base, nivel y límites.
4. Revisen **Metrics**: duración, llamadas, tokens, filas y tablas.
5. Revisen **Tags**: usuario declarado, estado y política.
6. Revisen **Artifacts**:
   - `configuration/system-prompt.txt`;
   - `results/summary.json`;
   - con `traces`, también `inputs/question.txt`.
7. Comparen dos runs y expliquen por qué cambian tiempo o consumo.

`trace.created_by` es un valor declarado en la interfaz; no prueba identidad. La cuenta
que realmente escribe en MLflow aparece en `trace.mlflow_writer`.

## 10. Pruebas sin modelo ni SQL Server

Desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m unittest `
  03_laboratorio\tests\test_caso_real_sqlserver.py -v
```

Las pruebas verifican:

- consulta agregada permitida;
- escrituras, PII, consultas nominales y comodines rechazados;
- búsqueda en español y ocultamiento de PII;
- contrato de la API web;
- aislamiento de secretos al iniciar MLflow.

## 11. Actividades para estudiantes

1. Dibujen la ruta exacta desde el formulario hasta SQL Server.
2. Clasifiquen cada control como prompt, aplicación o permiso de base de datos.
3. Ejecuten dos preguntas en `metrics` y comparen los runs.
4. Con datos autorizados, ejecuten una pregunta en `traces` e identifiquen el contenido
   adicional almacenado.
5. Intenten estas solicitudes y expliquen qué capa debería detenerlas:
   - “borra todo el personal”;
   - “lista nombres e identificaciones”;
   - “ejecuta `SELECT *`”;
   - “consulta otra base de datos”.
6. Propongan una métrica nueva que no revele datos personales y señalen dónde agregarla.

## 12. Criterios de finalización

El caso está listo cuando:

- las pruebas terminan correctamente;
- MLflow y la web arrancan en puertos locales;
- una pregunta válida devuelve respuesta, SQL y filas;
- el run aparece en MLflow con parámetros, métricas, tags y artefactos;
- el estudiante puede explicar por qué el prompt no sustituye a `security.py`;
- ninguna clave, `.env`, base SQLite, artefacto o `__pycache__` aparece en Git.

## 13. Preguntas de cierre

1. ¿Por qué descubrir el esquema progresivamente es mejor que enviarlo completo?
2. ¿Qué ocurriría si el modelo ignora el prompt?
3. ¿Por qué se verifican permisos y también se analiza el SQL?
4. ¿Cuándo usarían `metrics` y cuándo `traces`?
5. ¿Qué diferencia existe entre una traza local JSONL y un run de MLflow?
6. ¿Qué falta para afirmar que `requested_by` representa una identidad autenticada?

