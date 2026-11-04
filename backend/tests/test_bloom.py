import pytest

from app.services.bloom import BloomFilter, SeenUrlFilter


def test_no_false_negatives_and_bounded_false_positives():
    bloom = BloomFilter(2000, 0.01)
    for i in range(2000):
        bloom.add(f"https://a.com/{i}")
    assert all(f"https://a.com/{i}" in bloom for i in range(2000))
    false_positives = sum(f"https://b.com/{i}" in bloom for i in range(5000))
    assert false_positives / 5000 < 0.03
    assert 0 < bloom.estimated_false_positive_rate() < 0.03


@pytest.mark.parametrize(("cap", "rate"), [(0, 0.1), (10, 0.0), (10, 1.0)])
def test_invalid_parameters(cap, rate):
    with pytest.raises(ValueError):
        BloomFilter(cap, rate)


def test_disabled_filter_never_reports_absent():
    assert SeenUrlFilter(enabled=False).definitely_absent("x") is False


def test_saturated_filter_falls_back_to_authoritative_store():
    seen = SeenUrlFilter(capacity=5, error_rate=0.01, enabled=True)
    assert seen.definitely_absent("new") is True
    seen.rebuild(f"u{i}" for i in range(50))  # over capacity
    assert seen.definitely_absent("brand-new") is False
