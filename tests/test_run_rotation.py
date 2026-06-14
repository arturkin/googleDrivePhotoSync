import random

from tv_photos.gphotos import CreatedItem
from tv_photos.models import Photo
from tv_photos.pipeline import run_rotation
from tv_photos.state import State


def ph(uuid, path, fav=False):
    return Photo(uuid=uuid, path=path, filename=f"{uuid}.jpg", width=4000, height=3000, favorite=fav)


class FakeClient:
    """Stand-in for GooglePhotosClient; records calls, never touches the network."""

    def __init__(self, fail_filenames=()):
        self.fail = set(fail_filenames)
        self.uploaded = []
        self.added = []
        self.removed = []
        self._n = 0

    def upload_bytes(self, data, mime, filename=""):
        self._n += 1
        tok = f"tok{self._n}"
        self.uploaded.append((filename, tok))
        return tok

    def batch_create(self, items, album_id=None):
        out = []
        for tok, name in items:
            ok = name not in self.fail
            out.append(
                CreatedItem(
                    filename=name,
                    media_item_id=(f"media-{tok}" if ok else None),
                    ok=ok,
                    message="Success" if ok else "boom",
                )
            )
        return out

    def album_add(self, album_id, ids):
        self.added.append(list(ids))

    def album_remove(self, album_id, ids):
        self.removed.append(list(ids))


def cands():
    return [ph("a", "/a.jpg"), ph("b", "/b.jpg"), ph("c", "/c.jpg")]


HASH = {"/a.jpg": "sha-a", "/b.jpg": "sha-b", "/c.jpg": "sha-c"}
NOOP_PREPARE = lambda path, m, q: b"bytes"
HASHER = lambda path: HASH[path]


def run(client, state, **kw):
    return run_rotation(
        client=client,
        state=state,
        candidates=cands(),
        count=3,
        album_id="album-1",
        max_long_edge=3840,
        jpeg_quality=85,
        rng=random.Random(0),
        hasher=HASHER,
        prepare=NOOP_PREPARE,
        **kw,
    )


def test_first_run_uploads_all_and_sets_album(tmp_path):
    st = State(tmp_path / "s.db")
    client = FakeClient()
    report = run(client, st)
    assert report.uploaded == 3
    assert report.added == 3
    assert report.removed == 0
    assert st.get_album_members() == {"media-tok1", "media-tok2", "media-tok3"}


def test_second_run_reuses_and_uploads_nothing(tmp_path):
    st = State(tmp_path / "s.db")
    run(FakeClient(), st)  # seed
    client2 = FakeClient()
    report = run(client2, st)
    assert client2.uploaded == []          # nothing re-uploaded
    assert report.uploaded == 0
    assert report.added == 0 and report.removed == 0
    assert len(st.get_album_members()) == 3


def test_dry_run_makes_no_writes(tmp_path):
    st = State(tmp_path / "s.db")
    client = FakeClient()
    report = run(client, st, dry_run=True)
    assert report.dry_run is True
    assert client.uploaded == [] and client.added == [] and client.removed == []
    assert st.get_album_members() == set()


class CountMismatchClient(FakeClient):
    """Returns FEWER create results than uploaded items (API contract violation)."""

    def batch_create(self, items, album_id=None):
        results = super().batch_create(items, album_id)
        return results[:-1]  # drop one -> count mismatch


def test_count_mismatch_skips_persistence_to_avoid_corruption(tmp_path):
    st = State(tmp_path / "s.db")
    client = CountMismatchClient()
    report = run(client, st)
    # nothing persisted (would otherwise mis-map sha -> media_id)
    assert report.uploaded == 0
    assert st.get_album_members() == set()
    assert st.get_media_item_id("sha-a") is None


def test_uploads_use_jpeg_filename(tmp_path):
    st = State(tmp_path / "s.db")
    client = FakeClient()
    run_rotation(
        client=client, state=st,
        candidates=[Photo(uuid="h", path="/h.heic", filename="IMG.HEIC",
                          width=4000, height=3000, favorite=False)],
        count=1, album_id="a", max_long_edge=3840, jpeg_quality=85,
        rng=random.Random(0), hasher=lambda p: "sha-h", prepare=lambda p, m, q: b"x",
    )
    assert client.uploaded[0][0] == "IMG.jpg"  # filename normalized to .jpg


def test_progress_callback_invoked_per_upload(tmp_path):
    st = State(tmp_path / "s.db")
    seen = []
    run_rotation(
        client=FakeClient(), state=st, candidates=cands(), count=3, album_id="a",
        max_long_edge=3840, jpeg_quality=85, rng=random.Random(0),
        hasher=HASHER, prepare=NOOP_PREPARE,
        progress=lambda done, total: seen.append((done, total)),
    )
    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_failed_create_is_excluded_from_album(tmp_path):
    st = State(tmp_path / "s.db")
    client = FakeClient(fail_filenames={"b.jpg"})
    report = run(client, st)
    assert report.uploaded == 2
    assert report.upload_failed == 1
    members = st.get_album_members()
    assert len(members) == 2
    assert st.get_media_item_id("sha-b") is None  # failed item not persisted
