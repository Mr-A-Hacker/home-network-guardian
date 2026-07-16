# Home Network Guardian — Website (Backend + Dashboard)

The website the router agent connects to. Users **sign up / sign in**, create
a **house**, paste their router's **`hng_house_…` API key**, and watch every
device + alert in a dashboard. Includes a **Pro** tier.

## Stack
Flask + Flask-SQLAlchemy (SQLite by default) + Flask-JWT-Extended + Flask-Cors.
No build step — the dashboard is plain HTML/JS in `static/`.

## Run locally
```bash
cd website
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app app run --host 0.0.0.0 --port 5000
```
Open http://localhost:5000

For production set env vars (or edit `app.py`):
```
SECRET_KEY=... JWT_SECRET_KEY=... DATABASE_URL=postgresql://user:pass@host/db
```

## Deploy to Render (free)
1. Push this repo to GitHub.
2. Go to https://dashboard.render.com → **New** → **Blueprint** → connect
   `Mr-A-Hacker/home-network-guardian`.
3. Render reads `render.yaml`: creates the web service (from `/website`) and a
   free Postgres DB, sets `PORT`, `SECRET_KEY`, `JWT_SECRET_KEY`, and
   `DATABASE_URL` automatically.
4. After deploy, open the provided `*.onrender.com` URL. `render.yaml` also
   works with a plain **Web Service** + **Postgres** if you prefer manual setup
   (use the `Procfile`: `gunicorn app:app --bind 0.0.0.0:$PORT`).

The agent's `config.json` `base_url` should be
`https://YOUR-APP.onrender.com/api`.


## How the router connects
On the router, set `config.json`:
```json
"website": { "base_url": "http://YOUR_SERVER:5000/api", "endpoint": "/v1/report" }
```
The agent sends `POST /api/v1/report` with header `X-API-Key: hng_house_xxx`.
In the website, create a house and paste that same key into "Link Router".
Reports are accepted only if the key matches a registered house.

## API summary
Auth:
- `POST /api/auth/signup` `{email, password}` → `{token, user}`
- `POST /api/auth/signin` → `{token, user}`
- `GET  /api/auth/me` (JWT)

Houses (JWT):
- `GET/POST /api/houses`
- `POST /api/houses/<id>/key` `{api_key}` — link the router's house key
- `DELETE /api/houses/<id>/key`
- `POST /api/houses/<id>/upgrade` — activate Pro (demo)

Agent (API key, no JWT):
- `POST /api/v1/report` — the router calls this

Dashboard (JWT):
- `GET /api/dashboard` — all houses + devices + alerts
- `GET /api/houses/<id>/history` — rolling report log (Pro keeps more)

## Pro tier
- Free: keeps last **50** reports, basic dashboard.
- Pro: keeps last **500** reports, "Go Pro" badge, full history.
- Payment is mocked in `houses.py#upgrade` — wire to Stripe later.
