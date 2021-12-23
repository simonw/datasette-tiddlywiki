from datasette.app import Datasette
import pytest
import sqlite3


@pytest.fixture
@pytest.mark.asyncio
async def ds(tmp_path_factory):
    dbs_dir = tmp_path_factory.mktemp("dbs")
    db_path = str(dbs_dir / "tiddlywiki.db")
    sqlite3.connect(db_path).execute("vacuum")
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
async def test_homepage(ds):
    response = await ds.client.get("/-/tiddlywiki")
    assert response.status_code == 200
    assert '<meta name="application-name" content="TiddlyWiki" />' in response.text


@pytest.mark.asyncio
async def test_status(ds):
    response = await ds.client.get("/status")
    assert response.json() == {"username": "me", "space": {"recipe": "all"}}


@pytest.mark.asyncio
async def test_get_tiddlers(ds, one_tiddler):
    response = await ds.client.get("/recipes/all/tiddlers.json")
    assert response.json() == [
        {"blah": "json", "title": "one", "text": "this is text", "revision": 1}
    ]


@pytest.mark.asyncio
async def test_get_tiddler(ds, one_tiddler):
    response = await ds.client.get("/recipes/all/tiddlers/one")
    assert response.json() == {
        "blah": "json",
        "title": "one",
        "text": "this is text",
        "revision": 1,
    }


@pytest.mark.asyncio
async def test_put_tiddler(ds, one_tiddler):
    response = await ds.client.put(
        "/recipes/all/tiddlers/one",
        json={
            "blah": "json",
            "title": "one",
            "text": "this is text updated",
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
async def test_delete_tiddler(ds, one_tiddler):
    db = ds.get_database("tiddlywiki")
    assert (await db.execute("select count(*) from tiddlers")).single_value() == 1
    response = await ds.client.delete("/bags/default/tiddlers/one")
    assert response.status_code == 204
    assert (await db.execute("select count(*) from tiddlers")).single_value() == 0


@pytest.mark.asyncio
async def test_menu_link(ds):
    response = await ds.client.get("/")
    assert response.status_code == 200
    assert '<li><a href="/-/tiddlywiki">TiddlyWiki</a></li>' in response.text
