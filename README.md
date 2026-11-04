# Lookup – a small, self-hostable search engine

A foundation you can read in an afternoon: a polite crawler, an inverted index with TF-IDF
ranking, a REST API (FastAPI + SQLite) and a SvelteKit interface for searching and administration.

```
apps/web/    SvelteKit + TypeScript + Tailwind v4 (search UI + admin)
backend/     FastAPI, SQLite (stdlib sqlite3), crawler worker, tests
docs/        architecture notes
```

## Quick start

**Backend** (Python 3.12+)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
set -a; source .env; set +a     # load settings into this shell (needed for the worker too)
uvicorn app.main:app --reload   # API on http://localhost:8000 (docs at /api/docs); migrates the DB on start
python -m app.worker            # in a second terminal: processes queued crawl jobs
# manual migration, if you disable AUTO_MIGRATE:  python -m app.db.migrate
```

**Frontend** (Node 20+)

```bash
cd apps/web
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

## Deployment (Vercel, one project, two services)

The root `vercel.json` defines two services behind one domain:

| Service | Root | Public? | Notes |
| --- | --- | --- | --- |
| `web` | `apps/web` | yes, everything except `/api/*` | SvelteKit (`adapter-vercel`) |
| `backend` | `backend` | only `/api/*` | FastAPI; routes already live under `/api/v1`, docs at `/api/docs` |

* `web` declares a binding to `backend`, so Vercel injects `BACKEND_URL` into it. The search page's
  server load (`+page.server.ts`) calls the backend through that internal URL. Browser calls
  (admin pages) go to the same origin, `/api/v1/...`, which the rewrite sends to `backend`; no CORS is needed.
* Develop the whole thing locally with `vercel dev`. Without it, use the Quick start commands above.
* **Persistence:** Vercel's filesystem is read-only except `/tmp`, and instances are ephemeral. On Vercel the
  database defaults to `/tmp/search.db`, so data is lost between cold starts, and the crawl worker
  (`python -m app.worker`) cannot run as a service. Use Vercel only for demos or a prebuilt read-only index; for real use
  run the backend and worker on a VM/container with a persistent volume (see `docker-compose.yml`) and point the web app at it
  with `PUBLIC_API_BASE_URL` (and drop the `backend` service/rewrite).
* The backend's entrypoint (`app/main.py`, variable `app`) is auto-detected; if Vercel does not find it, add
  `"entrypoint": "app/main.py"` to the `backend` service.

## Known limitations (please read)

* **No authentication or authorization.** Admin and write endpoints are open. Put the app behind a reverse proxy with auth / private networking before exposing it. No rate limiting.
* DNS rebinding between our DNS check and the HTTP client's own resolution is not fully closed; restrict egress at the network layer in production.
* JavaScript-rendered pages are not executed; only server-delivered HTML is indexed. HTML only (no PDFs).
* Search scores every document that contains any query term (in Python), which is fine for thousands to low hundreds of thousands of pages, not millions. No stemming, phrase queries, or typo tolerance. Accent folding means e.g. `sık`/`sik` collide.
* Crawl politeness state (per-host timing) is per worker process; run one worker per database unless you accept that.
* Only same-host links are followed and persisted.
* The worker uses synchronous SQLite calls inside its event loop (fast local I/O); HTTP is fully async.
* UI uses native elements (`<dialog>`, `<select>`) styled with Tailwind rather than shadcn-svelte / Ark UI, which could not be installed or verified when this was generated; they can be introduced per component later.
