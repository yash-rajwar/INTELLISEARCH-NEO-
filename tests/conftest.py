"""Live tests (marked live) run only when RUN_LIVE=1. Nothing here imports the app."""

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_LIVE") == "1":
        return
    skip = pytest.mark.skip(reason="live test: set RUN_LIVE=1 with Elasticsearch running")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
