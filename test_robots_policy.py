from app.services.crawler.robots import RobotsPolicy, _policy_from_row


def test_policy_variants() -> None:
    body = "User-agent: *\nDisallow: /private\nCrawl-delay: 100\n"
    policy = _policy_from_row({"unreachable": 0, "status_code": 200, "body": body})
    assert policy.allowed("https://a.com/public") and not policy.allowed("https://a.com/private/x")
    assert policy.crawl_delay == 30.0  # capped
    assert _policy_from_row({"unreachable": 0, "status_code": 404, "body": ""}).allowed("https://a.com/x")
    assert not _policy_from_row({"unreachable": 1, "status_code": None, "body": ""}).allowed("https://a.com/")
    assert RobotsPolicy(None, allow_all=True).crawl_delay is None


def test_database_path_defaults_to_tmp_on_vercel() -> None:
    from app.core.config import Settings

    assert Settings.from_env({"VERCEL": "1"}).database_path == "/tmp/search.db"
    assert Settings.from_env({"VERCEL": "1", "DATABASE_PATH": "/data/x.db"}).database_path == "/data/x.db"
    assert Settings.from_env({}).database_path == "data/search.db"
