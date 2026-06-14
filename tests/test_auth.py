import json
import os
import stat

from tv_photos.auth import token_has_scopes, write_private


def write_token(path, scopes):
    path.write_text(json.dumps({"token": "x", "refresh_token": "r", "scopes": scopes}))
    return path


def test_token_has_all_required_scopes(tmp_path):
    p = write_token(tmp_path / "t.json", ["A", "B", "C"])
    assert token_has_scopes(p, ["A", "B"]) is True


def test_token_missing_a_scope(tmp_path):
    p = write_token(tmp_path / "t.json", ["A"])  # only appendonly-equivalent
    assert token_has_scopes(p, ["A", "B"]) is False


def test_token_file_absent(tmp_path):
    assert token_has_scopes(tmp_path / "nope.json", ["A"]) is False


def test_token_without_scopes_key(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"token": "x"}))
    assert token_has_scopes(p, ["A"]) is False


def test_write_private_sets_0600(tmp_path):
    p = tmp_path / "secret.json"
    write_private(p, "data")
    assert p.read_text() == "data"
    mode = stat.S_IMODE(os.stat(p).st_mode)
    assert mode == 0o600
