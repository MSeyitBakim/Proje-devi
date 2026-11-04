import os
from collections.abc import Mapping
from dataclasses import dataclass


def _int(env: Mapping[str, str], key: str, default: int, minimum: int = 0) -> int:
    value = int(env.get(key, default))
    if value < minimum:
        raise ValueError(f"{key} must be >= {minimum}")
    return value


def _float(env: Mapping[str, str], key: str, default: float, minimum: float = 0.0) -> float:
    value = float(env.get(key, default))
    if value < minimum:
        raise ValueError(f"{key} must be >= {minimum}")
    return value


def _bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None:
        return default
    if raw.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if raw.strip().lower() in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} must be a boolean")


def _csv(env: Mapping[str, str], key: str, default: str = "") -> tuple[str, ...]:
    return tuple(item.strip() for item in env.get(key, default).split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "development"
    database_path: str = "data/search.db"
    auto_migrate: bool = True
    log_level: str = "INFO"
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)

    crawler_contact: str = ""
    crawl_timeout_s: float = 10.0
    crawl_max_bytes: int = 2_000_000
    crawl_max_redirects: int = 5
    crawl_concurrency: int = 4
    crawl_host_delay_s: float = 1.0
    crawl_max_attempts: int = 3
    crawl_retry_base_s: float = 60.0
    crawl_lease_s: float = 300.0
    crawl_allow_private_hosts: bool = False
    robots_ttl_s: float = 86_400.0
    robots_error_ttl_s: float = 300.0
    max_text_chars: int = 200_000
    max_links_per_page: int = 500

    bloom_enabled: bool = False
    bloom_capacity: int = 1_000_000
    bloom_error_rate: float = 0.01

    weight_title: float = 3.0
    weight_description: float = 2.0
    weight_body: float = 1.0
    synonym_weight: float = 0.5
    max_synonyms_per_term: int = 3
    max_query_terms: int = 16
    max_query_length: int = 200
    synonyms_file: str | None = None
    extra_stop_words: tuple[str, ...] = ()

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def user_agent(self) -> str:
        suffix = f" (+{self.crawler_contact})" if self.crawler_contact else ""
        return f"SearchEngineBot/0.1{suffix}"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        d = cls()
        return cls(
            environment=e.get("APP_ENV", d.environment),
            database_path=e.get("DATABASE_PATH", d.database_path),
            auto_migrate=_bool(e, "AUTO_MIGRATE", d.auto_migrate),
            log_level=e.get("LOG_LEVEL", d.log_level).upper(),
            cors_origins=_csv(e, "CORS_ORIGINS", ",".join(d.cors_origins)),
            crawler_contact=e.get("CRAWLER_CONTACT", d.crawler_contact),
            crawl_timeout_s=_float(e, "CRAWL_TIMEOUT_S", d.crawl_timeout_s, 0.1),
            crawl_max_bytes=_int(e, "CRAWL_MAX_BYTES", d.crawl_max_bytes, 1024),
            crawl_max_redirects=_int(e, "CRAWL_MAX_REDIRECTS", d.crawl_max_redirects, 0),
            crawl_concurrency=_int(e, "CRAWL_CONCURRENCY", d.crawl_concurrency, 1),
            crawl_host_delay_s=_float(e, "CRAWL_HOST_DELAY_S", d.crawl_host_delay_s, 0.0),
            crawl_max_attempts=_int(e, "CRAWL_MAX_ATTEMPTS", d.crawl_max_attempts, 1),
            crawl_retry_base_s=_float(e, "CRAWL_RETRY_BASE_S", d.crawl_retry_base_s, 0.0),
            crawl_lease_s=_float(e, "CRAWL_LEASE_S", d.crawl_lease_s, 1.0),
            crawl_allow_private_hosts=_bool(e, "CRAWL_ALLOW_PRIVATE_HOSTS", False),
            robots_ttl_s=_float(e, "ROBOTS_TTL_S", d.robots_ttl_s, 0.0),
            robots_error_ttl_s=_float(e, "ROBOTS_ERROR_TTL_S", d.robots_error_ttl_s, 0.0),
            max_text_chars=_int(e, "MAX_TEXT_CHARS", d.max_text_chars, 1000),
            max_links_per_page=_int(e, "MAX_LINKS_PER_PAGE", d.max_links_per_page, 1),
            bloom_enabled=_bool(e, "BLOOM_ENABLED", d.bloom_enabled),
            bloom_capacity=_int(e, "BLOOM_CAPACITY", d.bloom_capacity, 1),
            bloom_error_rate=_float(e, "BLOOM_ERROR_RATE", d.bloom_error_rate, 1e-9),
            weight_title=_float(e, "WEIGHT_TITLE", d.weight_title),
            weight_description=_float(e, "WEIGHT_DESCRIPTION", d.weight_description),
            weight_body=_float(e, "WEIGHT_BODY", d.weight_body),
            synonym_weight=_float(e, "SYNONYM_WEIGHT", d.synonym_weight),
            max_synonyms_per_term=_int(e, "MAX_SYNONYMS_PER_TERM", d.max_synonyms_per_term, 0),
            max_query_terms=_int(e, "MAX_QUERY_TERMS", d.max_query_terms, 1),
            max_query_length=_int(e, "MAX_QUERY_LENGTH", d.max_query_length, 1),
            synonyms_file=e.get("SYNONYMS_FILE") or None,
            extra_stop_words=_csv(e, "EXTRA_STOP_WORDS"),
        )
