# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

TaskAI — the user writes a task in free-form Spanish, Gemini structures it (title, category,
priority, inferred date, productivity advice) and the result is persisted in PostgreSQL scoped to
the logged-in user.

Two independent apps, no monorepo tooling: `backend/` (FastAPI) and `frontend/` (Angular 21).
They are wired only over HTTP. There is no root `package.json` and no shared build.

## Commands

Backend — **must run from `backend/`** (modules import each other flat: `import database`):

```bash
cd backend && ../.venv/Scripts/python -m uvicorn main:app --reload
```

Frontend (from `frontend/`):

```bash
npm start
```
```bash
npm run build
```

Tests use the `@angular/build:unit-test` builder with **Vitest** in jsdom (not Karma):

```bash
npx ng test --include src/app/services/task.spec.ts
```
```bash
npx ng test --filter "^TaskList"
```

Backend tests (stdlib `unittest`, no pytest installed), from `backend/`:

```bash
../.venv/Scripts/python -m unittest test_date_resolver -v
```

Requires PostgreSQL on `127.0.0.1:5432` with database `taskai_db`, plus `GEMINI_API_KEY` in
`backend/.env`. Tables are auto-created on startup.

The Gemini key is on the free plan, where `429 RESOURCE_EXHAUSTED` (quota spent) and
`503 UNAVAILABLE` (Google overloaded) are frequent. `generate_with_fallback()` in `main.py` walks
`GEMINI_MODELS` in order on 429/5xx. Each model has its own free quota, so falling back to another
model helps with both. The client is capped at 2 attempts per model; the SDK default is 5 attempts
with backoff up to 60 s, which made failover take close to a minute. If every model fails, the
endpoint returns 503 or 429 with a Spanish message that `task-form.ts` shows in the toast. Other API
errors such as 400 are never retried on another model. Tests mock the API and spend no quota:
`python -m unittest test_gemini_fallback -v`.

## Architecture

### The Gemini pipeline (`POST /api/process-task`)

This is the core of the product and the least obvious part of the codebase — see
`process_and_save` in `backend/main.py`:

1. **Dates are resolved in Python, not by Gemini.** `date_resolver.resolve_date()` runs *before* the
   API call and handles the common Spanish expressions deterministically (próximo/este + weekday,
   mañana vs. "por la mañana", en N días/semanas/meses, "5 de octubre", "el primer lunes de…").
   The resolved date is injected into the prompt so the title and advice match it, and it overrides
   whatever Gemini returns. Gemini only picks the date when no rule matches, and even then it gets a
   60-day lookup calendar instead of doing arithmetic. The model used to turn "el próximo lunes"
   into this week's already-past Monday. A weekday qualified by a month or "pasado" is deliberately
   left to Gemini: a wrong rule is worse than no rule.
2. The call passes `response_schema=GeminiTaskStructure` + `response_mime_type="application/json"`,
   so Gemini returns schema-conformant JSON rather than prose. Editing the Pydantic field
   `description` strings is how you steer the model — they are the prompt.
3. `GeminiTaskStructure.detected_date` maps to the DB column `Task.due_date`; the names differ.
4. Every task endpoint returns a **hand-built dict**, not the ORM object (`CompleteTaskResponse`
   has no `from_attributes`). Adding a column means updating each endpoint's return dict.

### Database (Neon) and email reminders (GitHub Actions)

The database lives in **Neon** (cloud PostgreSQL 18, US East). `DATABASE_URL` in `backend/.env`
points there, and the old local database is kept as `LOCAL_DATABASE_URL`. Neon runs in **UTC** and
suspends after ~5 min idle, which is why the engine uses `pool_pre_ping=True`.

`.github/workflows/recordatorios.yml` runs `automation/enviar_recordatorios.py` every hour from 8:00
to 21:00 Bogotá. The cron is written in UTC (13–23 plus 0–2), and the script also drops runs outside
8:00–21:59, because GitHub can delay scheduled runs. It reads Neon **directly** (not via the API) and
emails tasks due tomorrow or today through Gmail SMTP. After **each** send it stamps
`tasks.reminder_day_before_sent_at` / `reminder_same_day_sent_at`, so each reminder goes out once;
`update_task_manual` resets both stamps when `due_date` changes. The script runs
`SET TIME ZONE 'America/Bogota'` before the query; without it, after 19:00 Bogotá `CURRENT_DATE` is
already tomorrow. HTML escaping happens in Python (`html.escape`), not in the SQL. Recipient emails
are masked in logs because Actions logs are visible to repo collaborators. The workflow needs the
secrets `DATABASE_URL`, `GMAIL_USER` and `GMAIL_APP_PASSWORD`. `--dry-run --forzar` simulates locally
and writes HTML previews to a temp dir. Tests: `python -m unittest discover -s automation`.
This replaced an earlier local n8n flow. Details are in `automation/LEEME.md`.

### Auth

Login uses `OAuth2PasswordRequestForm`, so `POST /api/auth/login` is
`application/x-www-form-urlencoded` and the **email travels in the `username` field**.
`frontend/src/app/services/auth.ts` builds `URLSearchParams` specifically for this — it is not a
JSON endpoint like the rest of the API.

JWT goes to `localStorage`, is attached by `auth.interceptor.ts`, and `auth.guard.ts` gates
`/tasks`. The guard only checks that a token *exists*; expiry is not validated and there is no
401 handling anywhere.

Every task query filters on `owner_id == current_user.id` — preserve that in new endpoints.

### Zoneless change detection

`app.config.ts` uses `provideZonelessChangeDetection()`. **RxJS/HTTP subscribe callbacks do not
trigger change detection.** When mutating plain component fields inside a subscribe, call
`this.cdr.markForCheck()` or the UI silently will not update. Prefer the signal approach used by
`services/notification.ts`, which needs no `ChangeDetectorRef` at all.

### Styling system

Dark theme throughout. Tokens live in `src/styles/_variables.scss`, reusable blocks in
`src/styles/_mixins.scss`; import with `@use '../../../styles/variables' as v;`.

`src/styles.scss` owns the page background — components must not repaint it (`app.scss` used to,
which is why `!important` existed there; both are fixed). `landing.scss` predates the token system
and still hardcodes hex values.

Toasts are global: `NotificationService` holds a signal, a single `<app-toast>` sits in `app.html`.
Components call `notify.success(...)` / `notify.error(...)` — never render their own toast.

Responsive: verified with no horizontal overflow from 320 px up. Breakpoints are 640 px (compact
mobile) and 480 px (navbar and CTAs stack); the landing's mobile rules live in the `RESPONSIVE`
block at the end of `landing.scss`, and headline sizes use `clamp()` so desktop is unchanged.
`.landing-container` has `overflow-x: hidden` for the background glows, which **hides** overflow
instead of producing a scrollbar — check element bounds, not just `scrollWidth`. Grids use
`minmax(min(300px, 100%), 1fr)` so a card never demands more width than a 320 px phone has.

### Landing flip cards

The 6 feature cards flip on CSS `:hover`; their back-face images live in
`public/images/features/` (downloaded from Unsplash — photo IDs are in the HTML comments). Do not
add `loading="lazy"` to them: the back face is rotated and hidden, so the browser never loads the
image until mid-flip.

`services/flip-sound.ts` plays a real page-turn recording, `public/sounds/page-turn.mp3` ("Turn a
Page" by CreatorsHome, Pixabay Content License), through Web Audio. It is fetched eagerly but decoded
only on unlock, and decoded once, because `decodeAudioData` consumes the ArrayBuffer. Playback
constants are at the top. Browsers block audio until a click/key/tap — hover never counts — so the
service unlocks on the first gesture anywhere, and the `🔇 Activar sonido` button asks for one.
That button carries `data-sound-toggle` so the global unlock listener skips it; without that, the
same click would unlock *and then* toggle, muting the user who just asked for sound.

## Known broken / traps

- Config comes only from `backend/.env` (template: `backend/.env.example`). `database.py` and `auth.py`
  raise at import if `DATABASE_URL` or `SECRET_KEY` is missing. There are deliberately no fallbacks.
  Never reintroduce credentials in code.
- The three `.spec.ts` files reference class names that were later renamed (`App`, `TaskList`,
  `TaskForm`, service `Task`), so `ng test` fails to compile until they are fixed.
- No migrations framework — `Base.metadata.create_all` only, which never alters existing tables.
  Hand-written, idempotent SQL lives in `backend/migrations/` and must be applied manually.
- `due_date` is `String(50)` holding `YYYY-MM-DD`, not a `Date`. Sorting/filtering by date is
  string-based.
- `PUT /api/tasks/{id}` and `TaskService.updateTask()` exist but no UI calls them.
- `services/auth.ts` uses `127.0.0.1:8000` while `services/task.ts` uses `localhost:8000`. Both
  work; there are no `environment.ts` files.
- The git repo is at the project root. The root `.gitignore` keeps `.env`, `.venv/`, `.claude/` and
  the 72 MB `PROYECTO_COMPLETO.txt` out of it.
- `angular.json` `anyComponentStyle` budget was raised to 8kB/16kB because `landing.scss` (now
  12.2 kB) broke the default 8 kB error ceiling. It still emits a warning on every production build.
