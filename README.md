# Remote Job Bot

Bot gratuito en Python 3.12 que consulta vacantes públicas cada hora y envía por Telegram únicamente oportunidades nuevas, 100% remotas y apropiadas para perfiles tecnológicos junior en México. Acepta puestos disponibles para México, LATAM, Americas o Worldwide; rechaza modalidades híbridas/presenciales, restricciones incompatibles y puestos senior.

## Arquitectura

- `main.py`: coordina fuentes, limpieza, deduplicación, scoring, envío y persistencia.
- `filters.py`: reglas de ubicación, seniority, experiencia, roles y tecnologías.
- `telegram_bot.py`: formato HTML seguro y acceso directo a Telegram Bot API.
- `sources/`: un adaptador normalizado por fuente pública.
- `data/seen_jobs.json`: IDs enviados, versionados entre ejecuciones.
- `.github/workflows/jobs.yml`: ejecución horaria y manual.

Las fuentes iniciales son [Remotive](https://remotive.com/remote-jobs/api), [RemoteOK](https://remoteok.com/api) y [Arbeitnow](https://www.arbeitnow.com/blog/job-board-api). Sus URLs están aisladas en cada adaptador para facilitar cambios. Remotive entrega su feed público con retraso y exige enlazar la vacante original y atribuir la fuente; las alertas cumplen ambas condiciones.

## Filtros y scoring

Una vacante geográficamente incompatible, claramente híbrida/presencial o con seniority alta obtiene 0. La experiencia elevada detectada en requisitos se penaliza sin descartar automáticamente. Las demás suman puntos por compatibilidad remota, señales junior/entry/graduate, requisitos de 0-2 años, rol tecnológico o de marketing, habilidades relevantes, proyectos y fecha de publicación. Durante la calibración amplia solo se envían resultados con `MIN_SCORE = 40`.

No se exige “Junior” en el título: una vacante general puede superar el umbral si su descripción confirma poca experiencia y afinidad suficiente. Cada alerta se marca como vista solo después de que Telegram confirma el envío.

## Configurar Telegram

1. Abre Telegram y conversa con `@BotFather`.
2. Ejecuta `/newbot`, sigue las instrucciones y copia el token.
3. Envía cualquier mensaje a tu bot recién creado.
4. Visita `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` y copia `message.chat.id`. Para un grupo, añade el bot, escribe un mensaje y revisa `getUpdates`; el ID suele ser negativo.

Nunca publiques ni confirmes en Git el token. Guárdalo exclusivamente como variable de entorno o GitHub Secret.

## Ejecutar localmente

Desde la carpeta `remote-job-bot` en PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:TELEGRAM_BOT_TOKEN = "tu_token"
$env:TELEGRAM_CHAT_ID = "tu_chat_id"
python main.py
```

En macOS/Linux, activa con `source .venv/bin/activate` y usa `export TELEGRAM_BOT_TOKEN=...` y `export TELEGRAM_CHAT_ID=...`.

Si no hay coincidencias nuevas, no se envía ningún mensaje. Los conteos y errores aparecen solo en el log.

## Publicar y activar GitHub Actions

1. Crea un repositorio vacío en GitHub, sin archivos iniciales.
2. Desde `remote-job-bot`, ejecuta:

```bash
git init
git add .
git commit -m "Initial remote job bot"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/remote-job-bot.git
git push -u origin main
```

3. Abre **Settings → Secrets and variables → Actions → New repository secret**.
4. Crea `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` con sus valores reales.
5. Abre **Actions → Remote job alerts → Run workflow** para probarlo manualmente.
6. Confirma en el log que una ejecución con envíos crea el commit `Update seen jobs`.

El workflow corre al minuto 0 de cada hora (UTC). Solo responde a `schedule` y `workflow_dispatch`, así que sus commits no crean un bucle. Si hay protección de rama, permite escritura a GitHub Actions o adapta la persistencia. En **Settings → Actions → General → Workflow permissions**, selecciona lectura y escritura si la política no respeta el permiso declarado.

## Añadir una fuente

1. Crea `sources/nueva_fuente.py` con `fetch_jobs() -> list[dict[str, str]]`.
2. Devuelve `id`, `title`, `company`, `location`, `description`, `url`, `source` y `published_at`; usa `""` para campos ausentes.
3. Usa un endpoint público, `requests`, timeout y `raise_for_status()`.
4. Importa la función y añádela a `SOURCES` en `sources/__init__.py`.

Cada fuente está aislada: una excepción queda registrada sin detener las demás consultas.

## Gmail técnico para alertas reenviadas

La fuente `sources/email_alerts.py` se conecta exclusivamente a Gmail mediante IMAP con SSL (`imap.gmail.com:993`). Usa una App Password, nunca la contraseña normal de Google. Abre `INBOX` en modo de solo lectura y descarga mensajes mediante `BODY.PEEK[]`, por lo que no los marca como leídos ni los modifica.

1. Crea una cuenta Gmail dedicada al bot.
2. Activa la verificación en dos pasos de esa cuenta.
3. En la seguridad de la Cuenta de Google, abre **Contraseñas de aplicaciones** y genera una para el bot.
4. Guarda la dirección y la App Password únicamente en variables de entorno o Secrets.
5. En Outlook crea una regla de reenvío para las alertas de LinkedIn, Indeed, Glassdoor, Computrabajo y Wellfound hacia el Gmail técnico. Si Google envía una confirmación, apruébala desde Gmail.
6. Prueba localmente:

```powershell
$env:JOB_EMAIL_ADDRESS = "correo@gmail.com"
$env:JOB_EMAIL_APP_PASSWORD = "app-password"
python main.py
```

En GitHub crea estos Secrets adicionales:

- `JOB_EMAIL_ADDRESS`
- `JOB_EMAIL_APP_PASSWORD`

Para verificar el reenvío, reenvía manualmente una alerta manteniendo su contenido HTML y ejecuta el bot. Aunque `From` sea tu Outlook y el asunto comience con `FW:`, el parser reconoce la plataforma usando asunto, cuerpo, encabezados reenviados y dominios de enlaces.

Los nombres exactos de los controles de alertas pueden cambiar. El parser inspecciona remitente, asunto, dominio, enlace y contexto cercano; ignora footer, preferencias, privacidad, login y unsubscribe. Lee hasta 100 mensajes de los últimos cinco días y no borra, mueve, responde ni marca correos como leídos.

## Boards ATS públicos

Edita `config/job_boards.py`; no necesitas modificar los adaptadores.

### Greenhouse

Usa la API pública `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`. Obtén el token del segmento posterior a `boards.greenhouse.io/` o `job-boards.greenhouse.io/` y añade:

```python
GREENHOUSE_BOARDS = [("token-verificado", "Nombre de Empresa")]
```

### Lever

Usa `https://api.lever.co/v0/postings/{site}?mode=json`. Obtén `site` de `jobs.lever.co/{site}`. Para la instancia europea usa el prefijo `eu:`:

```python
LEVER_COMPANIES = [("site-verificado", "Empresa"), ("eu:site-europeo", "Empresa EU")]
```

### Ashby

Usa la API pública oficial `https://api.ashbyhq.com/posting-api/job-board/{name}`. El nombre es el último segmento de `jobs.ashbyhq.com/{name}`:

```python
ASHBY_BOARDS = [("board-verificado", "Empresa")]
```

Las listas comienzan vacías porque no se asumió que una empresa o slug actual acepte candidatos de México. Cada board falla de manera independiente y todas sus vacantes pasan por el filtro global.

## Agregador opcional Jobicy

Jobicy ofrece una API pública sin autenticación. Se consulta una sola vez, con un máximo de 200 vacantes, y permanece apagada por defecto:

```powershell
$env:ENABLE_JOBICY = "true"
python main.py
```

En GitHub crea una variable de repositorio `ENABLE_JOBICY=true`. No requiere API key. Su documentación exige no consultar más de una vez por hora; el workflow cumple ese límite. Jobicy es una red de seguridad y su URL tiene menor prioridad que una URL directa de Greenhouse, Lever o Ashby.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

Las pruebas no realizan llamadas externas: usan payloads y HTML simulados para Outlook, ATS, normalización, filtros, deduplicación y tolerancia a fallos.
