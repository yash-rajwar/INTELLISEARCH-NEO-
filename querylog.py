"""The LOG_QUERIES switch, kept separate so it can be tested without importing the whole app."""


def make_query_logger(store_fn, enabled):
    """Return a log_query function that calls store_fn only when logging is enabled."""

    def log_query(*args, **kwargs):
        if enabled:
            store_fn(*args, **kwargs)

    return log_query
