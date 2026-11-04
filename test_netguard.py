import pytest

from app.core.exceptions import BlockedDestinationError
from app.core.netguard import assert_public_destination, check_literal_host, is_public_ip


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1",
     "0.0.0.0", "224.0.0.1", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1", "fd00:ec2::254"],
)
def test_private_addresses_blocked(address: str) -> None:
    assert not is_public_ip(address)


@pytest.mark.parametrize("address", ["93.184.216.34", "8.8.8.8", "2606:4700:4700::1111"])
def test_public_addresses_allowed(address: str) -> None:
    assert is_public_ip(address)


@pytest.mark.parametrize("host", ["localhost", "LOCALHOST.", "a.localhost", "db.internal", "10.0.0.1"])
def test_literal_hosts_blocked(host: str) -> None:
    with pytest.raises(BlockedDestinationError):
        check_literal_host(host)


@pytest.mark.anyio
async def test_hostname_resolving_to_private_ip_is_blocked() -> None:
    async def resolver(_: str) -> list[str]:
        return ["93.184.216.34", "10.0.0.5"]

    with pytest.raises(BlockedDestinationError):
        await assert_public_destination("evil.example", resolver=resolver)


@pytest.mark.anyio
async def test_public_resolution_and_allow_private_flag() -> None:
    async def public(_: str) -> list[str]:
        return ["93.184.216.34"]

    await assert_public_destination("ok.example", resolver=public)
    await assert_public_destination("localhost", allow_private=True)
