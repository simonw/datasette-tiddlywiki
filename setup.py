from setuptools import setup
import os

VERSION = "0.1"


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="datasette-tiddlywiki",
    description="Run TiddlyWiki in Datasette and save Tiddlers to a SQLite database",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Simon Willison",
    url="https://github.com/simonw/datasette-tiddlywiki",
    project_urls={
        "Issues": "https://github.com/simonw/datasette-tiddlywiki/issues",
        "CI": "https://github.com/simonw/datasette-tiddlywiki/actions",
        "Changelog": "https://github.com/simonw/datasette-tiddlywiki/releases",
    },
    license="Apache License, Version 2.0",
    classifiers=[
        "Framework :: Datasette",
        "License :: OSI Approved :: Apache Software License",
    ],
    version=VERSION,
    packages=["datasette_tiddlywiki"],
    entry_points={"datasette": ["tiddlywiki = datasette_tiddlywiki"]},
    install_requires=["datasette"],
    extras_require={"test": ["pytest", "pytest-asyncio"]},
    package_data={"datasette_tiddlywiki": ["*.html"]},
    python_requires=">=3.6",
)
