"""Batch 20: parallel Compare. Imports nothing that touches config."""

import threading

from parallel import SKIPPED, run_compare


class Boom(Exception):
    pass


def fake_result(mode):
    return {"hits": [1, 2], "elapsed_ms": 10, "mode_used": mode}


def test_order_results_and_logging():
    logged = []
    out = run_compare(fake_result, lambda *a: logged.append(a), (Boom,))
    assert list(out) == ["keyword", "semantic", "hybrid", "weighted"]
    assert all(entry["error"] == "" and entry["result"]["mode_used"] == m for m, entry in out.items())
    assert sorted(m for m, *_ in logged) == ["hybrid", "keyword", "semantic", "weighted"]
    assert all(a[1:] == (2, 10, "ok") for a in logged)


def test_methods_really_run_at_the_same_time():
    barriers = {
        frozenset(("keyword", "semantic")): threading.Barrier(2, timeout=3),
        frozenset(("hybrid", "weighted")): threading.Barrier(2, timeout=3),
    }

    def search_fn(mode):
        for pair, barrier in barriers.items():
            if mode in pair:
                barrier.wait()  # raises BrokenBarrierError unless both threads are inside at once
        return fake_result(mode)

    out = run_compare(search_fn, lambda *a: None, (Boom,))
    assert all(entry["error"] == "" for entry in out.values())


def test_semantic_timeout_skips_the_two_elser_methods():
    called = []

    def search_fn(mode):
        called.append(mode)
        if mode == "semantic":
            raise Boom("timeout [10s] waiting for inference result (408)")
        return fake_result(mode)

    logged = []
    out = run_compare(search_fn, lambda *a: logged.append(a), (Boom,))
    assert sorted(called) == ["keyword", "semantic"]
    assert out["hybrid"]["error"] == SKIPPED and out["weighted"]["error"] == SKIPPED
    assert out["semantic"]["result"] is None and out["keyword"]["result"] is not None
    assert ("semantic", 0, 0, "error") in logged
    assert len(logged) == 2  # skipped methods are not logged as searches


def test_other_failures_do_not_skip_anything():
    def search_fn(mode):
        if mode == "hybrid":
            raise Boom("bad request")
        return fake_result(mode)

    out = run_compare(search_fn, lambda *a: None, (Boom,))
    assert out["hybrid"]["error"] == "bad request"
    assert out["weighted"]["result"] is not None
