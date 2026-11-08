"""Refuse to serve on a non-loopback address unless the owner allows it."""

import ipaddress


def is_loopback(host):
    """True for 127.x.x.x, ::1 and the name localhost."""
    name = (host or "").strip().lower().strip("[]")
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def check_host(host, allow=False):
    """Raise ValueError when HOST would expose the app to other machines without permission."""
    if is_loopback(host) or allow:
        return
    raise ValueError(
        "Refusing to start: HOST=%r is not a loopback address, so other computers could reach "
        "this app. Use HOST=127.0.0.1, or set ALLOW_NON_LOOPBACK=true if you really mean it." % host
    )
