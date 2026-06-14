from tv_photos.state import State


def test_record_and_lookup_upload(tmp_path):
    st = State(tmp_path / "s.db")
    st.record_upload("sha-abc", "mediaid-1", "a.jpg")
    assert st.get_media_item_id("sha-abc") == "mediaid-1"


def test_lookup_unknown_returns_none(tmp_path):
    st = State(tmp_path / "s.db")
    assert st.get_media_item_id("nope") is None


def test_record_upload_is_idempotent_upsert(tmp_path):
    st = State(tmp_path / "s.db")
    st.record_upload("sha-abc", "mediaid-1", "a.jpg")
    st.record_upload("sha-abc", "mediaid-2", "a.jpg")
    assert st.get_media_item_id("sha-abc") == "mediaid-2"
    assert st.count_uploaded() == 1


def test_album_id_roundtrip(tmp_path):
    st = State(tmp_path / "s.db")
    assert st.get_album_id() is None
    st.set_album_id("album-xyz")
    assert st.get_album_id() == "album-xyz"


def test_set_and_get_album_members_replaces(tmp_path):
    st = State(tmp_path / "s.db")
    st.set_album_members(["m1", "m2", "m3"])
    assert st.get_album_members() == {"m1", "m2", "m3"}
    st.set_album_members(["m2", "m4"])
    assert st.get_album_members() == {"m2", "m4"}


def test_all_media_item_ids(tmp_path):
    st = State(tmp_path / "s.db")
    st.record_upload("sha-1", "m1", "a.jpg")
    st.record_upload("sha-2", "m2", "b.jpg")
    assert set(st.all_media_item_ids()) == {"m1", "m2"}


def test_persists_across_reopen(tmp_path):
    path = tmp_path / "s.db"
    st = State(path)
    st.set_album_id("album-xyz")
    st.record_upload("sha-1", "media-1", "x.jpg")
    st.set_album_members(["media-1"])
    st.close()

    st2 = State(path)
    assert st2.get_album_id() == "album-xyz"
    assert st2.get_media_item_id("sha-1") == "media-1"
    assert st2.get_album_members() == {"media-1"}
