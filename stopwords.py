from app.services.indexing.text import fold

ENGLISH = (
    "a an and are as at be but by for from has have he her his i in is it its of on or "
    "that the their they this to was we were will with you your"
)
TURKISH = (
    "acaba ama ancak ve veya ile bir bu şu o da de ki mi mı mu mü için gibi kadar çok daha "
    "ise ya ne var yok olarak olan her hem değil ben sen biz siz onlar"
)


def build_stop_words(extra: tuple[str, ...] = ()) -> frozenset[str]:
    words = f"{ENGLISH} {TURKISH}".split() + list(extra)
    return frozenset(fold(word) for word in words)
