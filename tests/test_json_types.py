from nagara.json_types import JSONAny, JSONDict, JSONList, JSONObject


def test_aliases_accept_typical_payloads():
    a: JSONDict = {"k": "v", "n": 1, "nested": {"a": [1, 2]}}
    b: JSONList = [1, "two", {"three": 3}]
    c: JSONObject = a
    d: JSONObject = b
    e: JSONAny = None
    f: JSONAny = a
    assert isinstance(a, dict)
    assert isinstance(b, list)
    assert c is a
    assert d is b
    assert e is None
    assert f is a
