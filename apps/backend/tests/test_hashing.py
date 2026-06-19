from app.domain.hashing import content_hash


def test_hash_is_key_order_independent():
    a = {"x": 1, "y": {"b": 2, "a": 3}}
    b = {"y": {"a": 3, "b": 2}, "x": 1}
    assert content_hash(a) == content_hash(b)


def test_hash_changes_with_content():
    a = {"x": 1}
    b = {"x": 2}
    assert content_hash(a) != content_hash(b)


def test_hash_is_sha256_hex():
    h = content_hash({"x": 1})
    assert len(h) == 64
    int(h, 16)  # valid hex
