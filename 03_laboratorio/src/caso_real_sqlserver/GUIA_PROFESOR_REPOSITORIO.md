# Guía del profesor: preparar y publicar el caso en un repositorio

## 1. Qué se va a publicar

No publique únicamente `03_laboratorio\src\caso_real_sqlserver`: en el estado actual esa
carpeta **no es autónoma**. Reutiliza módulos del laboratorio y del tema 01:

```text
caso_real_sqlserver\config.py
└── reuso.py
    └── 01_patrones_agenticos\src\model.py

caso_real_sqlserver\service.py
├── comun.py
├── trazas_lc.py
└── settings.py
    └── 01_patrones_agenticos\src\trace_log.py
```

También encadena tres archivos de dependencias. La forma más segura de compartir un
repositorio reducido es conservar las rutas originales e incluir las piezas mínimas que
se enumeran abajo.

## 2. Estructura mínima funcional del nuevo repositorio

```text
caso-real-sqlserver-clase\
├── .gitignore
├── requirements.txt
├── requirements-mlflow.txt
├── 01_patrones_agenticos\
│   └── src\
│       ├── model.py
│       └── trace_log.py
└── 03_laboratorio\
    ├── .env.example
    ├── src\
    │   ├── comun.py
    │   ├── reuso.py
    │   ├── settings.py
    │   ├── trazas_lc.py
    │   └── caso_real_sqlserver\
    │       └── todos los archivos fuente y las dos guías
    └── tests\
        └── test_caso_real_sqlserver.py
```

Conservar esta estructura evita modificar imports y rutas. No copie:

- `.env`;
- `.venv\`;
- `__pycache__\` ni `*.pyc`;
- `03_laboratorio\outputs\`;
- `mlflow.db`, `basic_auth.db` o `mlflow-auth.ini`;
- claves, cadenas de conexión reales o exportaciones de la base;
- archivos generados de trazas o artefactos.

La base `MilitaryResAllocDB` no forma parte de este repositorio. Cada estudiante necesita
una conexión autorizada o una instancia de práctica preparada por el profesor.

## 3. Crear la copia publicable

Ejecute desde la raíz del repositorio actual. Cambie `$dest` si quiere otra ubicación:

```powershell
$dest = Join-Path (Split-Path $PWD -Parent) "caso-real-sqlserver-clase"

New-Item -ItemType Directory -Force `
  "$dest\01_patrones_agenticos\src", `
  "$dest\03_laboratorio\src", `
  "$dest\03_laboratorio\tests" | Out-Null

Copy-Item .gitignore, requirements.txt, requirements-mlflow.txt $dest
Copy-Item 03_laboratorio\.env.example "$dest\03_laboratorio"

Copy-Item `
  01_patrones_agenticos\src\model.py, `
  01_patrones_agenticos\src\trace_log.py `
  "$dest\01_patrones_agenticos\src"

Copy-Item `
  03_laboratorio\src\comun.py, `
  03_laboratorio\src\reuso.py, `
  03_laboratorio\src\settings.py, `
  03_laboratorio\src\trazas_lc.py `
  "$dest\03_laboratorio\src"

Copy-Item `
  03_laboratorio\src\caso_real_sqlserver `
  "$dest\03_laboratorio\src" `
  -Recurse

Copy-Item `
  03_laboratorio\tests\test_caso_real_sqlserver.py `
  "$dest\03_laboratorio\tests"
```

La copia recursiva puede llevar un `__pycache__` local. El `.gitignore` impedirá
agregarlo, pero conviene confirmar el contenido antes del commit.

## 4. Revisar secretos antes de crear el repositorio

Entre a la copia y revise qué va a versionar:

```powershell
Set-Location $dest
git init -b main
git status --short --ignored
git add .
git status --short
```

La lista preparada no debe contener `.env`, `outputs`, `.db`, `.pyc` ni `__pycache__`.
Busque indicadores comunes de secretos en los archivos preparados:

```powershell
git grep -n -I -E "gsk_|sk-[A-Za-z0-9]|PWD=|Password=|API_KEY=.+"
```

Es normal encontrar nombres de variables vacías en `.env.example`. No es normal
encontrar valores reales. Si aparece un secreto, quite el archivo del área preparada,
elimine el valor del archivo y rote la credencial antes de continuar.

Revise el diff completo:

```powershell
git diff --cached --stat
git diff --cached
```

## 5. Validar la copia antes de publicarla

Cree un entorno nuevo dentro de la copia. Esto detecta dependencias accidentales con el
repositorio original:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install `
  -r 03_laboratorio\src\caso_real_sqlserver\requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest `
  03_laboratorio\tests\test_caso_real_sqlserver.py -v
```

Luego compruebe la configuración real localmente:

```powershell
Copy-Item 03_laboratorio\.env.example 03_laboratorio\.env
```

Complete el `.env` solo en su máquina y ejecute:

```powershell
.\.venv\Scripts\python.exe `
  03_laboratorio\src\caso_real_sqlserver\run_mlflow.py
```

En otra terminal:

```powershell
.\.venv\Scripts\python.exe `
  03_laboratorio\src\caso_real_sqlserver\run_web.py
```

Verifique <http://127.0.0.1:5000> y <http://127.0.0.1:8780>. Detenga ambos procesos y
vuelva a comprobar `git status --short --ignored`: las bases, artefactos, trazas y `.env`
deben aparecer únicamente como ignorados.

## 6. Crear el commit inicial

Después de validar:

```powershell
git add .
git commit -m "Agregar caso didáctico de agente SQL Server con MLflow"
```

Antes de subir:

```powershell
git status --short
git log -1 --oneline
```

El estado debe estar limpio.

## 7. Crear y subir el repositorio con GitHub CLI

Autentíquese si todavía no lo ha hecho:

```powershell
gh auth login
gh auth status
```

### Opción recomendada durante la preparación: repositorio privado

```powershell
gh repo create caso-real-sqlserver-clase `
  --private `
  --source . `
  --remote origin `
  --push `
  --description "Clase de agente SQL Server seguro con LangChain y MLflow"
```

Cuando haya revisado licencias, datos y secretos, puede cambiar la visibilidad:

```powershell
gh repo edit --visibility public --accept-visibility-change-consequences
```

### Si el repositorio ya existe en GitHub

```powershell
git remote add origin https://github.com/USUARIO/caso-real-sqlserver-clase.git
git push -u origin main
```

No copie literalmente `USUARIO`; reemplácelo por la cuenta u organización docente.

## 8. Comprobación posterior a la publicación

Revise el repositorio desde GitHub y confirme:

1. las dos guías se renderizan correctamente;
2. `.env` no existe;
3. no hay carpetas `outputs` o `__pycache__`;
4. no hay archivos `.db`, `.pyc` ni trazas;
5. `.env.example` solo contiene marcadores;
6. el historial de commits tampoco contiene secretos;
7. la visibilidad del repositorio es la esperada.

Haga una prueba final como estudiante en otra carpeta:

```powershell
Set-Location ..
git clone https://github.com/USUARIO/caso-real-sqlserver-clase.git prueba-estudiante
Set-Location prueba-estudiante
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install `
  -r 03_laboratorio\src\caso_real_sqlserver\requirements.txt
.\.venv\Scripts\python.exe -m unittest `
  03_laboratorio\tests\test_caso_real_sqlserver.py -v
```

Esta prueba de clonación limpia es importante: evita compartir material que solo
funciona por archivos o paquetes presentes en la máquina del profesor.

## 9. Cómo compartirlo con estudiantes

Entregue:

- URL del repositorio;
- rama o etiqueta que usarán;
- versión requerida de Python;
- instrucciones para instalar ODBC Driver 18;
- forma autorizada de obtener la conexión a SQL Server;
- política sobre claves de Groq/OpenAI;
- hora de apertura y cierre del acceso a la base.

Comandos básicos para estudiantes:

```powershell
git clone https://github.com/USUARIO/caso-real-sqlserver-clase.git
Set-Location caso-real-sqlserver-clase
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r 03_laboratorio\src\caso_real_sqlserver\requirements.txt
Copy-Item 03_laboratorio\.env.example 03_laboratorio\.env
```

Después completan su `.env`, ejecutan MLflow y ejecutan la web siguiendo
`GUIA_CLASE.md`.

Para congelar una versión de cada cohorte:

```powershell
git tag -a clase-2026-01 -m "Material entregado a la cohorte 2026-01"
git push origin clase-2026-01
```

Así los estudiantes pueden recuperar exactamente el material usado:

```powershell
git checkout clase-2026-01
```

## 10. Lista de preparación docente

- [ ] La cuenta SQL Server tiene `SELECT` y no tiene escritura.
- [ ] La base contiene únicamente datos permitidos para la clase.
- [ ] Las pruebas pasan desde un clon limpio.
- [ ] MLflow y la web arrancan con el `.env` local.
- [ ] La guía de clase coincide con los puertos y modelos configurados.
- [ ] `.env`, salidas, bases y cachés están ignorados.
- [ ] El diff preparado no contiene secretos.
- [ ] El repositorio comienza privado y se revisa antes de hacerlo público.
- [ ] Existe una etiqueta para la versión entregada.
- [ ] Los estudiantes saben que `metrics` es el nivel predeterminado.
- [ ] El uso de `traces` está limitado a preguntas y datos aprobados.

## 11. Actualizaciones futuras

Trabaje en una rama:

```powershell
git switch -c actualizar-clase
```

Después de los cambios, ejecute nuevamente pruebas y revisión de secretos. Publique por
pull request para conservar una revisión visible. Cuando la actualización esté aprobada,
cree una etiqueta nueva en lugar de mover o sobrescribir la etiqueta de una cohorte
anterior.

