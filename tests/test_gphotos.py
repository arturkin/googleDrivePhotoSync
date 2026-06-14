import random

import pytest
import requests

from tv_photos.gphotos import (
    GooglePhotosClient,
    backoff_seconds,
    parse_batch_create_result,
    should_retry,
)


class FakeResp:
    def __init__(self, status_code, json_body=None, text="", headers=None):
        self.status_code = status_code
        self._json = json_body or {}
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kw):
        self.calls.append((method, url))
        return self.responses.pop(0)


def _success_body(n, offset=0):
    return {
        "newMediaItemResults": [
            {"status": {"message": "Success"}, "mediaItem": {"id": f"m{i}", "filename": f"f{i}.jpg"}}
            for i in range(offset, offset + n)
        ]
    }


def test_request_retries_429_then_succeeds():
    session = FakeSession([FakeResp(429, headers={"Retry-After": "0"}), FakeResp(200, {})])
    client = GooglePhotosClient(session, max_retries=3, pace=0)
    client._sleep = lambda s: None  # don't actually wait in tests
    r = client._request("GET", "http://x")
    assert r.status_code == 200
    assert len(session.calls) == 2  # retried once


def test_album_add_recovers_from_429():
    session = FakeSession([FakeResp(429, headers={"Retry-After": "0"}), FakeResp(200, {})])
    client = GooglePhotosClient(session, max_retries=3, pace=0)
    client._sleep = lambda s: None
    client.album_add("alb", ["m1", "m2"])  # one chunk: 429 then 200 -> must NOT raise
    assert len(session.calls) == 2


def test_batch_create_continues_after_a_chunk_fails():
    # 60 items -> two chunks [50, 10]; first chunk HTTP 400, second OK.
    items = [(f"tok{i}", f"f{i}.jpg") for i in range(60)]
    session = FakeSession([FakeResp(400, text="bad"), FakeResp(200, _success_body(10, offset=50))])
    client = GooglePhotosClient(session, max_retries=0)
    results = client.batch_create(items)
    assert len(results) == 60                      # stays aligned with the request
    assert all(not r.ok for r in results[:50])     # failed chunk -> all failed, not an exception
    assert all(r.ok for r in results[50:])         # second chunk still processed


def test_parse_all_success():
    resp = {
        "newMediaItemResults": [
            {"status": {"message": "Success"}, "mediaItem": {"id": "m1", "filename": "a.jpg"}},
            {"status": {"message": "Success"}, "mediaItem": {"id": "m2", "filename": "b.jpg"}},
        ]
    }
    results = parse_batch_create_result(resp)
    assert [r.ok for r in results] == [True, True]
    assert [r.media_item_id for r in results] == ["m1", "m2"]


def test_parse_partial_failure():
    resp = {
        "newMediaItemResults": [
            {"status": {"message": "Success"}, "mediaItem": {"id": "m1", "filename": "a.jpg"}},
            {"status": {"code": 3, "message": "bad token"}},
        ]
    }
    results = parse_batch_create_result(resp)
    assert results[0].ok is True
    assert results[1].ok is False
    assert results[1].media_item_id is None
    assert "bad token" in results[1].message


def test_parse_empty():
    assert parse_batch_create_result({}) == []


def test_should_retry_on_transient():
    for code in (429, 500, 502, 503, 504):
        assert should_retry(code) is True


def test_should_not_retry_on_client_or_ok():
    for code in (200, 400, 401, 403, 404):
        assert should_retry(code) is False


def test_backoff_increases_and_is_capped():
    rng = random.Random(1)
    d0 = backoff_seconds(0, rng, base=1.0, cap=32.0)
    assert 1.0 <= d0 < 2.0
    capped = backoff_seconds(10, rng, base=1.0, cap=32.0)
    assert 32.0 <= capped < 33.0
