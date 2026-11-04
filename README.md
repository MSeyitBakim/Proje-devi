# Lookup – a small, self-hostable search engine

A foundation you can read in an afternoon: a polite crawler, an inverted index with TF-IDF
ranking, a REST API (FastAPI + SQLite) and a SvelteKit interface for searching and administration.

```
apps/web/    SvelteKit + TypeScript + Tailwind v4 (search UI + admin)
backend/     FastAPI, SQLite (stdlib sqlite3), crawler worker, tests
docs/        architecture notes
```

## Quick start

**Windows: start everything after setup**

Once the backend virtual environment and frontend dependencies are installed, run `start-lookup.bat` from the project folder (double-click it or run it in a terminal). It opens the API, crawler worker, and web app in separate windows. Wait for the web window to show its Local URL, then open <http://localhost:5173>. Close those windows to stop the services.

For first-time setup, open PowerShell in the project folder and run:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
cd ..\apps\web
npm.cmd install
cd ..\..
.\start-lookup.bat
```

**Backend** (Python 3.12+)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
set -a; source .env; set +a    # load settings into this shell (needed for the worker too)
uvicorn app.main:app --reload   # API on http://localhost:8000 (docs at /docs); migrates the DB on start
python -m app.worker            # in a second terminal: processes queued crawl jobs
# manual migration, if you disable AUTO_MIGRATE:  python -m app.db.migrate
```

**Frontend** (Node 22.12+)

```bash
cd apps/webs
npm install
npm run dev                     # http://localhost:5173, /api is proxied to :8000
```

Then: *Admin → Crawl*, enter a start URL (a public site you may crawl), watch the job progress, and search.
Set `CRAWLER_CONTACT` (URL or e-mail) so site owners can identify your bot.

**Tests**

```bash
cd backend && pytest            # unit + API tests
cd apps/web && npm test && npm run check
```

**Docker (untested here)**: `docker compose up --build` starts the API (port 8000) and the worker on one shared volume.

## Troubleshooting

Run `python scripts/doctor.py` from `backend/`. It reports the Python version, missing or
mis-named packages (it flags look-alikes such as `httpxz`; the real package is `httpx`) and the
full traceback if `app.main` or `app.worker` fail to import. Always use `python -m pip install`
inside the activated virtual environment, and run commands from `backend/`.

## How it works

| Concern | Decision |
| --- | --- |
| Storage | SQLite via stdlib `sqlite3`, WAL, foreign keys on, numbered SQL migrations (`app/db/migrations`). Repositories hold all SQL; services hold rules and transactions. |
| Index | Inverted index `postings(term, page_id, tf_title, tf_description, tf_body)`. Document frequencies and the document count are maintained by **SQLite triggers**, so cascaded deletes cannot leave stale statistics. `rebuild_index()` recreates everything from stored pages. |
| Text | NFKC → Turkish `İ/I/ı → i` → casefold → strip accents. `ÇALIŞMA`, `çalışma`, `calisma` match; so do `ISPARTA`/`ısparta`. Small English + Turkish stop-word lists (extendable via `EXTRA_STOP_WORDS`). No stemming (deliberately; see limitations). |
| Ranking | `score = length_norm × Σ qw·idf·(w_title·tf_t + w_desc·tf_d + w_body·tf_b)`, `tf = 1+ln(count)`, `idf = ln((N+1)/(df+1))+1`, `length_norm = 1/(1+ln(1+len))`. Weights are configurable. OR semantics: more matching terms ⇒ higher score. Ties break on page id, so pagination is stable. |
| Synonyms | Symmetric groups in `app/data/synonyms.json` (or `SYNONYMS_FILE`), expanded at query time with weight `0.5`, at most 3 per term, single words only. |
| Crawler | Separate worker process. Persistent SQLite queue with atomic claims, lease-based recovery of crashed claims, exponential backoff, retryable vs permanent failures, per-host delay (+ robots `Crawl-delay`), byte/redirect/time limits, only same-host links followed, `max_pages` / `max_depth` per job. robots.txt cached in the DB (RFC 9309 semantics: 4xx ⇒ allowed, 5xx/unreachable ⇒ disallowed for a short TTL). |
| SSRF | Literal and resolved IPs must be public (private, loopback, link-local, CGNAT, multicast, metadata ranges blocked; IPv4-mapped IPv6 handled). Re-checked on **every redirect hop**. `CRAWL_ALLOW_PRIVATE_HOSTS=true` disables this for local experiments only. |
| Bloom filter | Optional (`BLOOM_ENABLED`), only skips database reads for URLs *definitely* never seen; the UNIQUE constraint is the authority, so false positives/stale filters can never drop a URL. Off by default: `scripts/bench.py` shows no gain against SQLite's unique index (≈1 µs per lookup either way, in-memory DB). Enable only after measuring on your data. |
| URLs | One canonical form (`app/core/urls.py`): lowercase scheme/host, punycode, default ports dropped, fragment removed, dot-segments resolved, percent-escapes normalized, query preserved verbatim, `www.` **not** stripped. A site is identified by its hostname (`base_domain`), without a Public Suffix List. |

### API (`/api/v1`)

`GET /search?q=&page=&limit=` · `GET|POST /sites`, `GET|PATCH|DELETE /sites/{id}` ·
`GET|POST /urls`, `GET|PATCH|DELETE /urls/{id}` · `GET|POST /tags`, `PATCH|DELETE /tags/{id}` ·
`POST /crawl` (202), `GET /crawl/jobs`, `GET /crawl/jobs/{id}` · `GET /health`, `GET /stats`.
Errors share one envelope: `{"error": {"code", "message", "details?"}}`. Lists are paginated (`page`, `limit ≤ 100`).

## Deployment

* **Frontend → Vercel**: project root `apps/web` (uses `@sveltejs/adapter-vercel`). Set `PUBLIC_API_BASE_URL` to the API origin.
* **Backend**: `backend/api/index.py` + `vercel.json` expose the FastAPI app on Vercel, **but Vercel's filesystem is ephemeral**: SQLite writes will not persist and the crawler worker cannot run there. Realistic options: run the API + worker on a VM/container with a persistent volume (recommended), or bundle a prebuilt read-only database for search-only use. A durable serverless setup needs a different database behind the repository interfaces (`app/repositories/`), which is the intended seam; no alternative adapter is implemented.
* Set `CORS_ORIGINS` to your frontend origin(s).

## Known limitations (please read)

* **No authentication or authorization.** Admin and write endpoints are open. Put the app behind a reverse proxy with auth / private networking before exposing it. No rate limiting.
* DNS rebinding between our DNS check and the HTTP client's own resolution is not fully closed; restrict egress at the network layer in production.
* JavaScript-rendered pages are not executed; only server-delivered HTML is indexed. HTML only (no PDFs).
* Search scores every document that contains any query term (in Python), which is fine for thousands to low hundreds of thousands of pages, not millions. No stemming, phrase queries, or typo tolerance. Accent folding means e.g. `sık`/`sik` collide.
* Crawl politeness state (per-host timing) is per worker process; run one worker per database unless you accept that.
* Only same-host links are followed and persisted.
* The worker uses synchronous SQLite calls inside its event loop (fast local I/O); HTTP is fully async.
* UI uses native elements (`<dialog>`, `<select>`) styled with Tailwind rather than shadcn-svelte / Ark UI, which could not be installed or verified when this was generated; they can be introduced per component later.
