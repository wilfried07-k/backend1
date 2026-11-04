# EmploiCamer — Backend FastAPI

## Preview local

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend uses SQLite locally when `DATABASE_URL` is unset. If the existing
local Oracle XE 11 client exists at its legacy path, it is detected automatically;
otherwise set `ORACLE_CLIENT_LIB_DIR`. The API is at `http://127.0.0.1:8000`
and its interactive docs are at `/docs`.

## Déploiement preview en ligne

A Render Blueprint is included in `backend/render.yaml`; create a new Render Blueprint from the backend repository to create the Docker web service and its PostgreSQL database in Frankfurt. The free PostgreSQL tier is for short previews: Render deletes it after 30 days unless upgraded. The free web service can spin down while idle. These free-tier limits are documented by [Render](https://render.com/docs/free).

- `APP_ENV=preview`
- `DATABASE_URL` set to the isolated managed PostgreSQL database URL
- `SECRET_KEY` set to a fresh random value of at least 32 characters
- `CORS_ORIGINS` as a comma-separated list of allowed browser origins

The Docker image listens on the platform's `PORT`. PostgreSQL URLs beginning
with `postgres://` and `postgresql://` are supported. SQLite is for local use;
host container filesystems may be temporary.

Create the first administrator with `python -m app.create_admin`. Render Free
web services do not provide a shell, so run this command from a local checkout
connected to the Render database's **External Database URL** (Dashboard ? your
Postgres database ? Connect ? External Database URL). It must begin with
`postgresql://` or `postgres://`; paste only the URL, without `DATABASE_URL=`. Do
not use the local Oracle URL, paste the URL into chat, or commit it.

In PowerShell, from the `backend` directory, install the requirements if needed,
then enter the database URL without echoing it and run the prompt:

```powershell
$secureUrl = Read-Host 'Render External Database URL' -AsSecureString
$env:DATABASE_URL = [System.Net.NetworkCredential]::new('', $secureUrl).Password
if ($env:DATABASE_URL -notmatch '^postgres(?:ql)?://') {
  Remove-Item Env:DATABASE_URL
  throw 'Use only the Render External Database URL (postgres:// or postgresql://).'
}
try { python -m app.create_admin } finally { Remove-Item Env:DATABASE_URL }
```

The script prompts for the admin email, display name, and a password of at least
12 characters. Then use the **Admin** option on the app's login screen. Admin
accounts cannot be created through public registration. Render documents the
Free-service shell limitation [here](https://render.com/docs/ssh). All API routers except `/auth/register`
and `/auth/login` require a bearer token. Administrative routes require the
admin role; profile, company, job, application, messaging, alert, notification,
favorite, and interview operations check the associated user or company owner.

## Build Android preview

For local builds, put `EXPO_PUBLIC_API_BASE_URL` in
`afrijob-connect/.env.local`. For EAS cloud builds, set it in the EAS `preview`
environment because `.env.local` is ignored by Git and is not uploaded:

```bash
cd afrijob-connect
npx eas-cli env:set --name EXPO_PUBLIC_API_BASE_URL --value https://YOUR-API-HOST --environment preview --visibility plaintext
npx eas-cli build --profile preview --platform android
```

The API URL is included in the app bundle and is public; never put credentials
in it. The existing `eas.json` uses the EAS `preview` environment and internal
distribution. EAS Build requires an authenticated Expo account and a configured
project. Use isolated preview data; do not point this build at production data.

Google sign-in requires `GOOGLE_CLIENT_ID` on the backend. Set it to the same
Web OAuth client ID configured as `webClientId` in the mobile app, both locally
in `backend/.env` and in the API host's environment settings.

Password recovery sends short-lived codes over SMTP. Configure `SMTP_HOST`,
`SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM` locally in
`backend/.env` and in the Render environment settings. Use an app password when
your email provider requires one, and never commit credentials.

