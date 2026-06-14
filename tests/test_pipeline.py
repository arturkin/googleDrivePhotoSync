from tv_photos.models import Photo
from tv_photos.pipeline import build_upload_plan
from tv_photos.state import State


def ph(uuid, path, fav=False):
    return Photo(uuid=uuid, path=path, filename=f"{uuid}.jpg", width=4000, height=3000, favorite=fav)


def hasher_from(mapping):
    return lambda path: mapping[path]


def test_all_new_when_state_empty(tmp_path):
    st = State(tmp_path / "s.db")
    selected = [ph("a", "/a.jpg"), ph("b", "/b.jpg")]
    hasher = hasher_from({"/a.jpg": "sha-a", "/b.jpg": "sha-b"})
    plan = build_upload_plan(selected, st, hasher)
    assert plan.known == {}
    assert [sha for sha, _ in plan.to_upload] == ["sha-a", "sha-b"]


def test_splits_known_and_new(tmp_path):
    st = State(tmp_path / "s.db")
    st.record_upload("sha-b", "media-b", "b.jpg")
    selected = [ph("a", "/a.jpg"), ph("b", "/b.jpg")]
    hasher = hasher_from({"/a.jpg": "sha-a", "/b.jpg": "sha-b"})
    plan = build_upload_plan(selected, st, hasher)
    assert plan.known == {"sha-b": "media-b"}
    assert [sha for sha, _ in plan.to_upload] == ["sha-a"]


def test_dedupes_identical_content_to_single_upload(tmp_path):
    st = State(tmp_path / "s.db")
    # two different files with identical bytes -> same sha
    selected = [ph("a", "/a.jpg"), ph("dup", "/dup.jpg")]
    hasher = hasher_from({"/a.jpg": "sha-x", "/dup.jpg": "sha-x"})
    plan = build_upload_plan(selected, st, hasher)
    assert len(plan.to_upload) == 1
    assert plan.to_upload[0][0] == "sha-x"


def test_dedup_when_already_uploaded(tmp_path):
    st = State(tmp_path / "s.db")
    st.record_upload("sha-x", "media-x", "a.jpg")
    selected = [ph("a", "/a.jpg"), ph("dup", "/dup.jpg")]
    hasher = hasher_from({"/a.jpg": "sha-x", "/dup.jpg": "sha-x"})
    plan = build_upload_plan(selected, st, hasher)
    assert plan.known == {"sha-x": "media-x"}
    assert plan.to_upload == []
