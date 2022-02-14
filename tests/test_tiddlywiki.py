from datasette import hookimpl
from datasette.app import Datasette
from datasette.plugins import pm
import json
import pytest
import sqlite3


@pytest.fixture
@pytest.mark.asyncio
def db_path(tmp_path_factory):
    dbs_dir = tmp_path_factory.mktemp("dbs")
    db_path = str(dbs_dir / "tiddlywiki.db")
    sqlite3.connect(db_path).execute("vacuum")
    return db_path


@pytest.fixture
@pytest.mark.asyncio
async def ds(db_path):
    ds = Datasette([db_path])
    await ds.invoke_startup()
    return ds


@pytest.fixture
@pytest.mark.asyncio
async def one_tiddler(ds):
    db = ds.get_database("tiddlywiki")
    await db.execute_write(
        """
        insert into tiddlers (title, meta, text, revision)
        values (?, ?, ?, ?)
    """,
        ["one", '{"blah": "json"}', "this is text", 1],
        block=True,
    )


def root_cookies(datasette):
    return {"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")}


@pytest.mark.asyncio
async def test_homepage_no_tidlywiki_database():
    ds = Datasette([], memory=True)
    await ds.invoke_startup()
    response = await ds.client.get("/-/tiddlywiki")
    assert response.status_code == 400
    assert "You need to start Datasette with a tiddlywiki.db database" in response.text
    # Should be no link in global navigation either
    home_response = await ds.client.get("/")
    assert '<li><a href="/-/tiddlywiki">TiddlyWiki</a></li>' not in home_response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("base_url", (None, "/foo/"))
async def test_homepage(db_path, base_url):
    settings = {}
    if base_url:
        settings["base_url"] = base_url
    ds = Datasette([db_path], settings=settings)
    await ds.invoke_startup()
    response = await ds.client.get("/-/tiddlywiki")
    assert response.status_code == 200
    assert '<meta name="application-name" content="TiddlyWiki" />' in response.text
    # Extract the baked in tiddlers
    baked = response.text.split(
        '<script class="tiddlywiki-tiddler-store" type="application/json">', 1
    )[1].split("</script>")[0]
    tiddlers = json.loads(baked)
    tiddlyweb_host = [t for t in tiddlers if t["title"] == "$:/config/tiddlyweb/host"][
        0
    ]
    expected = "$protocol$//$host${}-/tiddlywiki/".format(base_url or "/")
    assert tiddlyweb_host == {
        "title": "$:/config/tiddlyweb/host",
        "text": expected,
    }


@pytest.mark.asyncio
async def test_status_anonymous(ds):
    response = await ds.client.get("/-/tiddlywiki/status")
    assert response.json() == {
        "username": None,
        "anonymous": True,
        "read_only": True,
        "space": {"recipe": "all"},
    }


@pytest.mark.asyncio
async def test_status_root(ds):
    response = await ds.client.get("/-/tiddlywiki/status", cookies=root_cookies(ds))
    assert response.json() == {
        "username": "root",
        "anonymous": False,
        "read_only": False,
        "space": {"recipe": "all"},
    }


@pytest.mark.asyncio
async def test_get_tiddlers(ds, one_tiddler):
    response = await ds.client.get("/-/tiddlywiki/recipes/all/tiddlers.json")
    assert response.json() == [
        {"blah": "json", "title": "one", "text": "this is text", "revision": 1}
    ]


@pytest.mark.asyncio
async def test_get_tiddler(ds, one_tiddler):
    response = await ds.client.get("/-/tiddlywiki/recipes/all/tiddlers/one")
    assert response.json() == {
        "blah": "json",
        "title": "one",
        "text": "this is text",
        "revision": 1,
    }


@pytest.mark.asyncio
async def test_put_tiddler_root(ds, one_tiddler):
    response = await ds.client.put(
        "/-/tiddlywiki/recipes/all/tiddlers/one",
        json={
            "blah": "json",
            "title": "one",
            "text": "this is text updated",
        },
        cookies=root_cookies(ds),
        headers={
            # To skip CSRF
            "x-requested-with": "TiddlyWiki",
        },
    )
    assert response.status_code == 204
    db = ds.get_database("tiddlywiki")
    row = (
        await db.execute(
            "select title, meta, text, revision from tiddlers where title = ?", ["one"]
        )
    ).first()
    assert dict(row) == {
        "title": "one",
        "meta": '{"blah": "json", "title": "one"}',
        "text": "this is text updated",
        "revision": 2,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("is_root", (True, False))
async def test_delete_tiddler(ds, one_tiddler, is_root):
    db = ds.get_database("tiddlywiki")
    assert (await db.execute("select count(*) from tiddlers")).single_value() == 1
    cookies = {}
    if is_root:
        cookies = root_cookies(ds)
    response = await ds.client.delete(
        "/-/tiddlywiki/bags/default/tiddlers/one",
        cookies=cookies,
        headers={
            "x-requested-with": "TiddlyWiki",
        },
    )
    if is_root:
        assert response.status_code == 204
        assert (await db.execute("select count(*) from tiddlers")).single_value() == 0
    else:
        assert response.status_code == 403
        assert (await db.execute("select count(*) from tiddlers")).single_value() == 1


@pytest.mark.asyncio
async def test_menu_link(ds):
    response = await ds.client.get("/")
    assert response.status_code == 200
    assert '<li><a href="/-/tiddlywiki">TiddlyWiki</a></li>' in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ("instance_blocked", "database_blocked"))
async def test_cannot_view_tiddlywiki(db_path, one_tiddler, reason):
    metadata = {}
    if reason == "instance_blocked":
        metadata["allow"] = {"id": "root"}
    elif reason == "database_blocked":
        metadata["databases"] = {"tiddlywiki": {"allow": {"id": "root"}}}
    ds = Datasette([db_path], metadata=metadata)
    await ds.invoke_startup()

    for path in (
        "/-/tiddlywiki",
        "/-/tiddlywiki/status",
        "/-/tiddlywiki/recipes/all/tiddlers/one",
    ):
        # Root should be able to see it
        root_response = await ds.client.get(path, cookies=root_cookies(ds))
        assert root_response.status_code == 200
        # Anonymous should not
        anon_response = await ds.client.get(path)
        assert anon_response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("can_view", (True, False))
async def test_menulink(db_path, can_view):
    # Configure so only root can view
    ds = Datasette(
        [db_path], metadata={"databases": {"tiddlywiki": {"allow": {"id": "root"}}}}
    )
    await ds.invoke_startup()

    cookies = {}
    if can_view:
        cookies = root_cookies(ds)

    response = await ds.client.get("/", cookies=cookies)
    fragment = '<li><a href="/-/tiddlywiki">TiddlyWiki</a></li>'
    if can_view:
        assert fragment in response.text
    else:
        assert fragment not in response.text
