from datasette import hookimpl
from datasette.utils.asgi import Response, NotFound
import json
import pathlib
import re
import textwrap
import urllib

html_path = pathlib.Path(__file__).parent / "tiddlywiki.html"
tiddler_store_re = re.compile(
    r'<script class="tiddlywiki-tiddler-store" type="application/json">(.*?)</script>',
    re.DOTALL,
)


@hookimpl
def register_routes():
    return [
        (r"/-/tiddlywiki$", index),
        (r"/-/tiddlywiki/status$", status),
        (r"/-/tiddlywiki/recipes/all/tiddlers.json$", all_tiddlers),
        (r"/-/tiddlywiki/recipes/all/tiddlers/(?P<title>.*)$", tiddler),
        # No idea why but sometimes hits bags/efault/.. instead of /bags/default/..
        (r"/-/tiddlywiki/bags/d?efault/tiddlers/(?P<title>.*)$", delete_tiddler),
    ]


@hookimpl
def skip_csrf(scope):
    if scope.get("headers"):
        headers = dict(scope["headers"])
        if headers.get(b"x-requested-with") == b"TiddlyWiki":
            return True


@hookimpl
def menu_links(datasette):
    try:
        db = datasette.get_database("tiddlywiki")
    except KeyError:
        return
    return [
        {"href": datasette.urls.path("/-/tiddlywiki"), "label": "TiddlyWiki"},
    ]


@hookimpl
def startup(datasette):
    async def inner():
        try:
            db = datasette.get_database("tiddlywiki")
        except KeyError:
            return
        await db.execute_write(
            textwrap.dedent(
                """
            CREATE TABLE IF NOT EXISTS tiddlers ( 
                title TEXT PRIMARY KEY,
                meta TEXT,
                text TEXT,
                revision INTEGER
            )
        """
            ),
            block=True,
        )

    return inner


async def index(datasette):
    try:
        db = datasette.get_database("tiddlywiki")
    except KeyError:
        return Response.text(
            "You need to start Datasette with a tiddlywiki.db database", status=400
        )

    # If a tiddler for `$:/StoryList` exists, we need to replace it
    story_list = (
        await db.execute(
            "select title, meta, text, revision from tiddlers where title = ?",
            ["$:/StoryList"],
        )
    ).first()

    html = html_path.read_text("utf-8")
    # Update tiddlers that are baked into page on startup
    def replace_tiddlers(match):
        tiddlers = json.loads(match.group(1))
        # Tell TiddlyWeb about the API paths
        tiddlers.append(
            {
                "title": "$:/config/tiddlyweb/host",
                "text": "$protocol$//$host${}".format(
                    datasette.urls.path("/-/tiddlywiki/")
                ),
            }
        )
        # Replace StoryList with one from our DB, if available
        if story_list:
            new_tiddlers = []
            for tiddler in tiddlers:
                if tiddler["title"] == "$:/StoryList":
                    replacement = {
                        "created": "20211222224039169",
                        "title": "$:/StoryList",
                        "text": "",
                        "list": json.loads(story_list["meta"])["fields"]["list"],
                        "modified": "20211222224039169",
                    }
                    new_tiddlers.append(replacement)
                else:
                    new_tiddlers.append(tiddler)
            tiddlers = new_tiddlers
        return '<script class="tiddlywiki-tiddler-store" type="application/json">{}</script>'.format(
            json.dumps(tiddlers).replace("<", "\\u003C")
        )

    return Response.html(tiddler_store_re.sub(replace_tiddlers, html))


async def status():
    return Response.json({"username": "me", "space": {"recipe": "all"}})


async def all_tiddlers(datasette):
    db = datasette.get_database("tiddlywiki")
    tiddlers = []
    for row in (
        await db.execute("select title, meta, text, revision from tiddlers")
    ).rows:
        tiddlers.append(tiddler_to_dict(row, row["title"]))
    return Response.json(tiddlers)


async def tiddler(request, datasette):
    title = urllib.parse.unquote(request.url_vars["title"])
    db = datasette.get_database("tiddlywiki")
    if request.method == "PUT":
        # Save it
        body = await request.post_body()
        data = json.loads(body)
        # Looks something like this:
        # {
        #     "title": "$:/StoryList",
        #     "text": "",
        #     "fields": {
        #         "list": "GettingStarted"
        #     },
        #     "type": "text/vnd.tiddlywiki"
        # }
        text = data.pop("text", "")

        # Do we have this already?
        row = (
            await db.execute("select revision from tiddlers where title = ?", [title])
        ).first()
        if row is not None:
            new_revision = row["revision"] + 1
        else:
            new_revision = 1

        await db.execute_write(
            """
            replace into tiddlers (title, meta, text, revision)
            values (:title, :meta, :text, :revision)
        """,
            {
                "title": title,
                "meta": json.dumps(data),
                "text": text,
                "revision": new_revision,
            },
            block=True,
        )

        return Response.text(
            "",
            status=204,
            headers={
                "Etag": "default/{}/{}:".format(urllib.parse.quote(title), new_revision)
            },
        )
    else:
        row = (
            await db.execute(
                "select title, meta, text, revision from tiddlers where title = ?",
                [title],
            )
        ).first()
        if row is None:
            raise NotFound("Tiddler not found")
        return Response.json(tiddler_to_dict(row, title))


async def delete_tiddler(request, datasette):
    title = urllib.parse.unquote(request.url_vars["title"])
    db = datasette.get_database("tiddlywiki")
    if request.method == "DELETE":
        await db.execute_write(
            "delete from tiddlers where title = ?", [title], block=True
        )
        return Response.text("", status=204)
    return Response.text("Needs DELETE", status=405)


def tiddler_to_dict(row, title):
    output = json.loads(row["meta"])
    output["title"] = title
    output["text"] = row["text"]
    output["revision"] = row["revision"]
    return output
