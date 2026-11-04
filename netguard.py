"""SSRF protection for outbound crawler requests.

Limitation: DNS is resolved by us and again by the HTTP client, so a hostile
resolver could change its answer between the two (DNS rebinding). Production
deployments should additionally restrict egress at the network layer.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable

from app.core.exceptions import BlockedDestinationError

Resolver = Callable[[str], Awaitable[list[str]]]

_BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata"}
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain", ".home.arpa")
_EXTRA_BLOCKED = (
    ipaddress.ip_network("169.254.169.254/32"),
    ipaddress.ip_network("100.100.100.200/32"),
    ipaddress.ip_network("fd00:ec2::254/128"),
)


def is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    ):
        return False
    return not any(ip in network for network in _EXTRA_BLOCKED if ip.version == network.version)


def check_literal_host(host: str) -> None:
    """Cheap, synchronous check usable at request time (no DNS)."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        name = host.lower().rstrip(".")
        if name in _BLOCKED_HOSTS or name.endswith(_BLOCKED_SUFFIXES):
            raise BlockedDestinationError(f"Host '{host}' is not allowed") from None
        return
    if not is_public_ip(host):
        raise BlockedDestinationError(f"Address '{host}' is not a public address")


async def resolve_host(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


async def assert_public_destination(
    host: str, *, resolver: Resolver = resolve_host, allow_private: bool = False
) -> None:
    if allow_private:
        return
    check_literal_host(host)
    try:
        ipaddress.ip_address(host)
        return
    except ValueError:
        pass
    addresses = await resolver(host)
    if not addresses:
        raise BlockedDestinationError(f"Host '{host}' did not resolve")
    for address in addresses:
        if not is_public_ip(address):
            raise BlockedDestinationError(f"Host '{host}' resolves to a non-public address")
