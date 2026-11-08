"""Batch 19: loopback guard, new settings, neighbour count."""

import pytest

from netguard import check_host, is_loopback
from search import neighbour_hit_ids
from settings import load_settings


def test_loopback_hosts_are_accepted():
    for host in ("127.0.0.1", "localhost", "::1", "127.0.0.5"):
        assert is_loopback(host)
        check_host(host)


def test_other_hosts_are_refused_unless_allowed():
    for host in ("0.0.0.0", "192.168.1.20", "127.evil.example", ""):
        with pytest.raises(ValueError):
            check_host(host)
    check_host("0.0.0.0", allow=True)


def test_settings_defaults_and_overrides():
    s = load_settings(env={}, env_file=None)
    assert s.allow_non_loopback is False
    assert s.context_neighbours == 1
    s = load_settings(env={"ALLOW_NON_LOOPBACK": "true", "CONTEXT_NEIGHBOURS": "2"}, env_file=None)
    assert s.allow_non_loopback is True
    assert s.context_neighbours == 2


def test_neighbour_count_default_is_unchanged():
    assert neighbour_hit_ids("some_index", "abc", 5) == [(4, "abc_0004"), (6, "abc_0006")]


def test_neighbour_count_two_and_edges():
    ids = neighbour_hit_ids("some_index", "abc", 1, count=2)
    assert [k for k, _ in ids] == [0, 2, 3]
    assert neighbour_hit_ids("some_index", "abc", 5, count=0) == []
    assert len(neighbour_hit_ids("some_index", "abc", 10, count=99)) == 6
    assert len(neighbour_hit_ids("some_index", "abc", 10, count="x")) == 2
