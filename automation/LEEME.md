# Recordatorios por correo (GitHub Actions)

Cada hora, entre las 8:00 y las 21:00 de Bogotá, GitHub ejecuta `enviar_recordatorios.py` en sus
servidores, así que **funciona aunque tu PC esté apagado**. El script busca tareas sin completar que
vencen **mañana** o **hoy** en la base de datos de Neon y envía un correo por cada una desde Gmail.
Cada aviso se envía una sola vez: la fecha de envío queda en `tasks.reminder_day_before_sent_at` /
`reminder_same_day_sent_at`, y se reinicia si cambia la fecha de la tarea.

## Archivos

| Archivo | Qué es |
|---|---|
| `../.github/workflows/recordatorios.yml` | Cuándo se ejecuta (horario, botón manual) |
| `enviar_recordatorios.py` | Busca, envía y marca los recordatorios |
| `buscar_recordatorios.sql` | Consulta que decide qué avisos tocan |
| `plantilla_correo.html` | Cuerpo del correo (marcadores `${...}`) |
| `test_enviar_recordatorios.py` | Pruebas sin red; GitHub las ejecuta antes de cada envío |

## Secretos en GitHub

En el repositorio: **Settings → Secrets and variables → Actions → New repository secret**:

| Nombre | Valor |
|---|---|
| `DATABASE_URL` | La cadena de conexión de Neon (la misma de `backend/.env`) |
| `GMAIL_USER` | `taskai.recordatorios@gmail.com` |
| `GMAIL_APP_PASSWORD` | La contraseña de aplicación de esa cuenta |

## Disparador externo (cron-job.org)

El programador propio de GitHub resultó poco fiable: llegó a ejecutar solo el ~23 % de las veces y
pasó horas sin ejecutar. Por eso **cron-job.org** (gratis) lanza el flujo cada hora mediante la API
de GitHub, del mismo modo que el botón "Run workflow". El horario de GitHub se mantiene como
respaldo; no hay duplicados porque cada aviso se marca al enviarse.

1. **Token de GitHub** (solo para esto): <https://github.com/settings/personal-access-tokens/new>
   → *Only select repositories*: `taskai` → *Repository permissions* → **Actions: Read and write**.
   No necesita ningún otro permiso. Tiene fecha de caducidad: renuévalo antes de que venza.
2. **cron-job.org** → *Create cronjob*:
   - URL: `https://api.github.com/repos/Sebas640/taskai/actions/workflows/recordatorios.yml/dispatches`
   - Horario: cada hora, de 8 a 21, zona horaria `America/Bogota`.
   - *Advanced* → método **POST**, cabeceras:
     `Accept: application/vnd.github+json`, `Authorization: Bearer <TOKEN>`,
     `X-GitHub-Api-Version: 2022-11-28`, `Content-Type: application/json`
   - Cuerpo: `{"ref":"main","inputs":{"programado":"true"}}`
   - Respuesta correcta de GitHub: **204 No Content**.

`programado=true` hace que esas ejecuciones respeten la franja 8:00–21:59; el botón manual (sin
marcarlo) la ignora para poder probar a cualquier hora.

## Probar

- **En GitHub:** pestaña **Actions → Recordatorios por correo → Run workflow**. Marca *"Solo simular"*
  para ver qué se enviaría sin enviar nada. Las ejecuciones manuales ignoran el horario.
- **En local**, sin enviar (las vistas previas HTML se guardan en una carpeta temporal):

  ```bash
  .venv/Scripts/python automation/enviar_recordatorios.py --dry-run --forzar
  ```
  (requiere la variable de entorno `DATABASE_URL`).

## A tener en cuenta

- GitHub puede **retrasar o descartar** las ejecuciones programadas. Por eso el horario está a
  **y 17** y no en punto: a las :00, que es el pico de carga de GitHub, solo se ejecutaban ~4 de las
  14 diarias. El script descarta las que caigan fuera de 8:00–21:59 de Bogotá.
- En repositorios **públicos**, GitHub desactiva las tareas programadas tras **60 días sin commits**;
  si deja de enviar, revisa la pestaña Actions y reactívalo.
- Neon trabaja en UTC: el script fija `America/Bogota` al conectarse. Sin eso, desde las 19:00 de
  Bogotá "hoy" sería ya el día siguiente.
