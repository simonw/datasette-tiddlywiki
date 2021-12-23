# datasette-tiddlywiki

[![PyPI](https://img.shields.io/pypi/v/datasette-tiddlywiki.svg)](https://pypi.org/project/datasette-tiddlywiki/)
[![Changelog](https://img.shields.io/github/v/release/simonw/datasette-tiddlywiki?include_prereleases&label=changelog)](https://github.com/simonw/datasette-tiddlywiki/releases)
[![Tests](https://github.com/simonw/datasette-tiddlywiki/workflows/Test/badge.svg)](https://github.com/simonw/datasette-tiddlywiki/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/simonw/datasette-tiddlywiki/blob/main/LICENSE)

Run TiddlyWiki in Datasette and save Tiddlers to a SQLite database

## Installation

Install this plugin in the same environment as Datasette.

    $ datasette install datasette-tiddlywiki

## Usage

Start Datasette with a `tiddlywiki.db` database. You can create it if it does not yet exist using `--create`:

    datasette tiddlywiki.db --create

Navigate to `/-/tiddlywiki` on your instance to interact with TiddlyWiki.

## Development

To set up this plugin locally, first checkout the code. Then create a new virtual environment:

    cd datasette-tiddlywiki
    python3 -mvenv venv
    source venv/bin/activate

Or if you are using `pipenv`:

    pipenv shell

Now install the dependencies and test dependencies:

    pip install -e '.[test]'

To run the tests:

    pytest
