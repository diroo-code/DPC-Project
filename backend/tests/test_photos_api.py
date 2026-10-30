"""Photo API tests: upload, visibility, pagination, search, signed URLs and deletion safety."""

from __future__ import annotations

import uuid
from pathlib import Path

import psycopg
import pytest

from app.storage import StorageError, storage

from .conftest import STORAGE_ROOT, create_user, make_friends, make_photo, token_for

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 400
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 400
WEBP = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 400


def auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(user_id)}"}


def upload(
    client,
    user_id: uuid.UUID,
    data: bytes = JPEG,
    filename: str = "photo.jpg",
    mime: str = "image/jpeg",
    caption: str = "A photo",
    visibility: str = "friends",
    tags: str | None = None,
):
    form = {"caption": caption, "visibility": visibility}
    if tags:
        form["tags"] = tags
    return client.post(
        "/api/v1/photos",
        headers=auth(user_id),
        files={"file": (filename, data, mime)},
        data=form,
    )


def test_upload_creates_row_tags_and_object(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    response = upload(client, alice, tags="Sunset, Beach")
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["owner_username"] == "alice"
    assert body["visibility"] == "friends"
    assert body["tags"] == ["beach", "sunset"]
    assert body["size_bytes"] == len(JPEG)

    row = conn.execute(
        "select storage_path from public.photos where id = %s", (body["id"],)
    ).fetchone()
    stored = Path(STORAGE_ROOT) / row[0]
    assert stored.exists()
    assert stored.read_bytes() == JPEG


def test_upload_requires_authentication(client) -> None:
    response = client.post(
        "/api/v1/photos", files={"file": ("a.jpg", JPEG, "image/jpeg")}, data={"caption": "x"}
    )
    assert response.status_code == 401


def test_upload_rejects_unsupported_type(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    response = upload(client, alice, data=b"GIF89a", filename="a.gif", mime="image/gif")
    assert response.status_code == 415


def test_upload_rejects_oversize_file(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    response = upload(client, alice, data=JPEG + b"\x00" * (5 * 1024 * 1024))
    assert response.status_code == 413


def test_upload_rejects_content_that_does_not_match_the_declared_type(
    client, conn: psycopg.Connection
) -> None:
    alice = create_user(conn, "alice")
    response = upload(client, alice, data=b"not an image at all", mime="image/jpeg")
    assert response.status_code == 415


def test_upload_accepts_png_and_webp(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    assert upload(client, alice, PNG, "a.png", "image/png").status_code == 201
    assert upload(client, alice, WEBP, "a.webp", "image/webp").status_code == 201


def test_feed_shows_only_visible_photos(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    carol = create_user(conn, "carol")
    make_friends(conn, alice, bob)

    shared = make_photo(conn, alice, visibility="friends", caption="shared")
    private = make_photo(conn, alice, visibility="owner", caption="private")
    stranger_photo = make_photo(conn, carol, visibility="friends", caption="stranger")

    response = client.get("/api/v1/photos", headers=auth(bob))
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {str(shared)}
    assert str(private) not in ids and str(stranger_photo) not in ids

    owner_view = client.get("/api/v1/photos", headers=auth(alice)).json()
    assert {item["id"] for item in owner_view["items"]} == {str(shared), str(private)}


def test_feed_pagination(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    for i in range(3):
        make_photo(conn, alice, caption=f"photo {i}")

    first = client.get("/api/v1/photos?limit=2", headers=auth(alice)).json()
    assert len(first["items"]) == 2
    assert first["total"] == 3
    assert first["has_more"] is True

    second = client.get("/api/v1/photos?limit=2&offset=2", headers=auth(alice)).json()
    assert len(second["items"]) == 1
    assert second["has_more"] is False


def test_feed_filter_by_uploader(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    make_photo(conn, alice)
    make_photo(conn, bob)

    response = client.get("/api/v1/photos?uploader=bob", headers=auth(alice))
    assert response.status_code == 200
    assert [item["owner_username"] for item in response.json()["items"]] == ["bob"]


def test_feed_filter_by_caption_and_tag(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    make_photo(conn, alice, caption="Sunset over the lake")
    tagged = make_photo(conn, alice, caption="Mountain trail")
    conn.execute(
        "insert into public.photo_tags (photo_id, tag) values (%s, 'hiking')", (tagged,)
    )

    by_caption = client.get("/api/v1/photos?q=sunset", headers=auth(alice)).json()
    assert [i["caption"] for i in by_caption["items"]] == ["Sunset over the lake"]

    by_tag = client.get("/api/v1/photos?tag=hiking", headers=auth(alice)).json()
    assert [i["id"] for i in by_tag["items"]] == [str(tagged)]


def test_feed_filter_by_future_date_returns_nothing(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    make_photo(conn, alice)
    response = client.get("/api/v1/photos?date_from=2099-01-01", headers=auth(alice))
    assert response.json()["items"] == []


def test_get_photo_hides_from_stranger(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    carol = create_user(conn, "carol")
    photo = make_photo(conn, alice, visibility="friends")

    assert client.get(f"/api/v1/photos/{photo}", headers=auth(carol)).status_code == 404
    assert client.get(f"/api/v1/photos/{photo}", headers=auth(alice)).status_code == 200


def test_signed_url_for_owner_and_friend_only(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    carol = create_user(conn, "carol")
    make_friends(conn, alice, bob)

    shared = make_photo(conn, alice, visibility="friends")
    private = make_photo(conn, alice, visibility="owner")

    owner = client.get(f"/api/v1/photos/{shared}/url", headers=auth(alice))
    assert owner.status_code == 200
    assert owner.json()["expires_in"] == 60
    assert owner.json()["url"].startswith("/media/")

    friend = client.get(f"/api/v1/photos/{shared}/url", headers=auth(bob))
    assert friend.status_code == 200

    assert client.get(f"/api/v1/photos/{shared}/url", headers=auth(carol)).status_code == 404
    assert client.get(f"/api/v1/photos/{private}/url", headers=auth(bob)).status_code == 404


def test_signed_url_serves_the_actual_bytes(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    uploaded = upload(client, alice)
    assert uploaded.status_code == 201
    photo_id = uploaded.json()["id"]

    url = client.get(f"/api/v1/photos/{photo_id}/url", headers=auth(alice)).json()["url"]
    served = client.get(url)
    assert served.status_code == 200
    assert served.content == JPEG
    assert served.headers["content-type"] == "image/jpeg"


def test_signed_url_rejects_a_tampered_signature(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    photo_id = upload(client, alice).json()["id"]
    url = client.get(f"/api/v1/photos/{photo_id}/url", headers=auth(alice)).json()["url"]

    tampered = url[:-4] + ("0000" if not url.endswith("0000") else "1111")
    assert client.get(tampered).status_code == 403


def test_signed_url_expires(client, conn: psycopg.Connection) -> None:
    """A correctly signed URL must still fail once its expiry has passed."""
    import time
    from urllib.parse import quote

    alice = create_user(conn, "alice")
    photo_id = upload(client, alice).json()["id"]
    key = conn.execute(
        "select storage_path from public.photos where id = %s", (photo_id,)
    ).fetchone()[0]

    expired_at = int(time.time()) - 5
    signature = storage._signature(key, expired_at)
    response = client.get(f"/media/{quote(key)}?exp={expired_at}&sig={signature}")
    assert response.status_code == 403
    assert "expired" in response.json()["detail"]


def test_api_enforces_the_daily_quota(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    for _ in range(20):
        make_photo(conn, alice)
    response = upload(client, alice)
    assert response.status_code == 429


def test_delete_removes_row_and_object(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    photo_id = upload(client, alice).json()["id"]
    key = conn.execute(
        "select storage_path from public.photos where id = %s", (photo_id,)
    ).fetchone()[0]
    assert (Path(STORAGE_ROOT) / key).exists()

    response = client.delete(f"/api/v1/photos/{photo_id}", headers=auth(alice))
    assert response.status_code == 204
    assert conn.execute(
        "select count(*) from public.photos where id = %s", (photo_id,)
    ).fetchone()[0] == 0
    assert not (Path(STORAGE_ROOT) / key).exists()


def test_delete_by_non_owner_is_forbidden(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")

    response = client.delete(f"/api/v1/photos/{photo}", headers=auth(bob))
    assert response.status_code == 403
    assert conn.execute("select count(*) from public.photos").fetchone()[0] == 1


def test_delete_aborts_when_storage_fails(client, conn: psycopg.Connection, monkeypatch) -> None:
    alice = create_user(conn, "alice")
    photo_id = upload(client, alice).json()["id"]

    def boom(key: str) -> None:
        raise StorageError("simulated storage outage")

    monkeypatch.setattr(storage, "delete", boom, raising=False)
    response = client.delete(f"/api/v1/photos/{photo_id}", headers=auth(alice))
    assert response.status_code == 502

    # The metadata row must survive, so the photo is still consistent and the delete can be retried.
    assert conn.execute(
        "select count(*) from public.photos where id = %s", (photo_id,)
    ).fetchone()[0] == 1


def test_tags_can_be_replaced_by_the_owner(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    photo_id = upload(client, alice, tags="old").json()["id"]

    response = client.put(
        f"/api/v1/photos/{photo_id}/tags",
        headers=auth(alice),
        json={"tags": ["new", "second"]},
    )
    assert response.status_code == 200
    assert response.json()["tags"] == ["new", "second"]

    tags = client.get(f"/api/v1/photos/{photo_id}", headers=auth(alice)).json()["tags"]
    assert tags == ["new", "second"]


def test_tags_rejected_for_a_friend(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    make_friends(conn, alice, bob)
    photo = make_photo(conn, alice, visibility="friends")

    response = client.put(
        f"/api/v1/photos/{photo}/tags", headers=auth(bob), json={"tags": ["hijack"]}
    )
    assert response.status_code == 403


@pytest.mark.parametrize("bad", ["with space", "-leading", "sym!bol"])
def test_invalid_tag_is_rejected_at_upload(client, conn: psycopg.Connection, bad: str) -> None:
    alice = create_user(conn, "alice")
    response = upload(client, alice, tags=bad)
    assert response.status_code == 422


def test_uppercase_tag_is_normalised_not_rejected(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    response = upload(client, alice, tags="SUNSET")
    assert response.status_code == 201
    assert response.json()["tags"] == ["sunset"]


def test_search_matches_partial_tag(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    photo = make_photo(conn, alice, caption="Holiday photo")

    conn.execute(
        "INSERT INTO public.photo_tags (photo_id, tag) VALUES (%s, %s)",
        (photo, "hiking"),
    )

    response = client.get(
        "/api/v1/photos/search?q=hik",
        headers=auth(alice),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(photo)]


def test_search_matches_partial_username(client, conn: psycopg.Connection) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")

    make_friends(conn, alice, bob)
    photo = make_photo(conn, bob, caption="A normal photo")

    response = client.get(
        "/api/v1/photos/search?q=bo",
        headers=auth(alice),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(photo)]


def test_search_matches_caption_tag_and_username(
    client, conn: psycopg.Connection
) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    carol = create_user(conn, "carol")

    make_friends(conn, alice, bob)
    make_friends(conn, alice, carol)

    caption_photo = make_photo(
        conn, alice, caption="specialkeyword holiday"
    )

    tag_photo = make_photo(
        conn, alice, caption="Another holiday"
    )
    conn.execute(
        "INSERT INTO public.photo_tags (photo_id, tag) VALUES (%s, %s)",
        (tag_photo, "specialkeyword"),
    )

    username_photo = make_photo(
        conn, bob, caption="Normal photo"
    )
    # Username "carol" is tested separately below.
    username_photo = make_photo(
        conn, carol, caption="Normal photo"
    )

    response = client.get(
        "/api/v1/photos/search?q=specialkeyword",
        headers=auth(alice),
    )

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}

    assert str(caption_photo) in ids
    assert str(tag_photo) in ids
    assert len(ids) == 2


def test_search_does_not_return_invisible_photos(
    client, conn: psycopg.Connection
) -> None:
    alice = create_user(conn, "alice")
    bob = create_user(conn, "bob")
    carol = create_user(conn, "carol")

    make_friends(conn, alice, bob)

    visible_photo = make_photo(
        conn, bob, visibility="friends", caption="uniquekeyword"
    )

    hidden_photo = make_photo(
        conn, carol, visibility="friends", caption="uniquekeyword"
    )

    response = client.get(
        "/api/v1/photos/search?q=uniquekeyword",
        headers=auth(alice),
    )

    assert response.status_code == 200

    ids = {item["id"] for item in response.json()["items"]}

    assert str(visible_photo) in ids
    assert str(hidden_photo) not in ids