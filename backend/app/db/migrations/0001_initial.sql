CREATE TABLE sites (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  main_url TEXT NOT NULL UNIQUE,
  base_domain TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  tag_list TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(tag_list)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE tags (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  normalized_title TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE site_tags (
  site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (site_id, tag_id)
) WITHOUT ROWID;
CREATE INDEX idx_site_tags_tag ON site_tags(tag_id);

CREATE TABLE pages (
  id INTEGER PRIMARY KEY,
  site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  url TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL DEFAULT '',
  content_hash TEXT,
  status_code INTEGER,
  doc_length INTEGER NOT NULL DEFAULT 0,
  crawled_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX idx_pages_site ON pages(site_id);

CREATE TABLE postings (
  term TEXT NOT NULL,
  page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  tf_title INTEGER NOT NULL DEFAULT 0,
  tf_description INTEGER NOT NULL DEFAULT 0,
  tf_body INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (term, page_id)
) WITHOUT ROWID;
CREATE INDEX idx_postings_page ON postings(page_id);

CREATE TABLE term_stats (
  term TEXT PRIMARY KEY,
  df INTEGER NOT NULL CHECK (df >= 0)
) WITHOUT ROWID;

CREATE TABLE corpus_stats (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  doc_count INTEGER NOT NULL CHECK (doc_count >= 0)
);
INSERT INTO corpus_stats (id, doc_count) VALUES (1, 0);

-- Document frequencies and the document count are maintained by the database itself,
-- so cascaded deletes (site -> pages -> postings) can never leave stale statistics.
CREATE TRIGGER postings_after_insert AFTER INSERT ON postings
BEGIN
  INSERT INTO term_stats (term, df) VALUES (NEW.term, 1)
  ON CONFLICT (term) DO UPDATE SET df = df + 1;
END;

CREATE TRIGGER postings_after_delete AFTER DELETE ON postings
BEGIN
  UPDATE term_stats SET df = df - 1 WHERE term = OLD.term;
  DELETE FROM term_stats WHERE term = OLD.term AND df <= 0;
END;

CREATE TRIGGER pages_after_insert AFTER INSERT ON pages
BEGIN
  UPDATE corpus_stats SET doc_count = doc_count + 1 WHERE id = 1;
END;

CREATE TRIGGER pages_after_delete AFTER DELETE ON pages
BEGIN
  UPDATE corpus_stats SET doc_count = doc_count - 1 WHERE id = 1;
END;

CREATE TABLE crawl_jobs (
  id INTEGER PRIMARY KEY,
  seed_url TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  max_pages INTEGER NOT NULL CHECK (max_pages > 0),
  max_depth INTEGER NOT NULL CHECK (max_depth >= 0),
  pages_crawled INTEGER NOT NULL DEFAULT 0,
  pages_failed INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);

CREATE TABLE crawl_urls (
  id INTEGER PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,
  job_id INTEGER REFERENCES crawl_jobs(id) ON DELETE SET NULL,
  depth INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'in_progress', 'done', 'failed')),
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  last_status_code INTEGER,
  next_attempt_at TEXT NOT NULL,
  claimed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX idx_crawl_urls_claim ON crawl_urls(status, next_attempt_at);
CREATE INDEX idx_crawl_urls_job ON crawl_urls(job_id, status);

CREATE TABLE robots_cache (
  origin TEXT PRIMARY KEY,
  status_code INTEGER,
  body TEXT NOT NULL DEFAULT '',
  unreachable INTEGER NOT NULL DEFAULT 0,
  fetched_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
) WITHOUT ROWID;
