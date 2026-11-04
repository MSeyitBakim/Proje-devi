# Architecture notes

```
            +----------------+      HTTP       +---------------------------+
 browser -> | SvelteKit app  | --------------> | FastAPI (sync handlers)   |
            +----------------+                 |  routes -> services ->    |
                                               |  repositories -> SQLite   |
                                               +-------------+-------------+
                                                             | shared DB (queue, pages, index)
                                               +-------------v-------------+
                                               | crawl worker (asyncio)    |
                                               |  claim -> robots -> fetch |
                                               |  -> extract -> index      |
                                               +---------------------------+
```

* **Layers**: `api/` (thin HTTP), `services/` (rules, transactions), `repositories/` (SQL only), `core/` (config, URL policy, SSRF guard, errors).
* **Transactions**: `db.session.transaction()` is `BEGIN IMMEDIATE`/`COMMIT`, or a `SAVEPOINT` when nested. No `await` happens inside a transaction.
* **Indexing is atomic with writes**: creating/updating a page and replacing its postings happen in one transaction; deleting a page or site cascades through postings and triggers fix the statistics.
* **Crawl flow**: `POST /crawl` creates a job and enqueues the seed → worker claims rows (`pending` and due, or `in_progress` with an expired lease) → robots → per-host delay → fetch (SSRF checks per hop, size cap) → extract → upsert page + index (unchanged content hash ⇒ no re-index) → enqueue same-host links within `max_depth`/`max_pages` → job becomes `completed` (≥1 page) or `failed` when nothing is outstanding.
* **Job states**: `queued → running → completed | failed`; other transitions raise `InvalidStateError`.
* **Extending**: swap storage by reimplementing the classes in `app/repositories/`; add stemming in `services/indexing/text.py` (index and query share `tokenize`, then rebuild the index).
