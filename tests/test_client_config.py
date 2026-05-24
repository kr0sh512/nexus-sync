import pytest

from nexus_sync.client.config import COMMAND_ACCESS_ENV, load_command_access_policy
from nexus_sync.client.execute import CommandAccessPolicy


def test_load_command_access_policy_defaults_to_deny_all() -> None:
    policy = load_command_access_policy({})

    assert not policy.full_access
    assert not policy.allows("hostname")


def test_load_command_access_policy_uses_default_when_env_is_missing() -> None:
    default = CommandAccessPolicy.allow(["hostname"])

    policy = load_command_access_policy({}, default=default)

    assert policy == default


def test_load_command_access_policy_supports_command_allowlist() -> None:
    policy = load_command_access_policy(
        {COMMAND_ACCESS_ENV: "hostname, network_interfaces"},
    )

    assert policy.allows("hostname")
    assert policy.allows("network_interfaces")
    assert not policy.allows("unknown")


def test_load_command_access_policy_supports_full_access() -> None:
    policy = load_command_access_policy({COMMAND_ACCESS_ENV: "full_access"})

    assert policy.full_access
    assert policy.allows("hostname")
    assert policy.allows("future_registered_preset")


def test_load_command_access_policy_rejects_mixed_full_access() -> None:
    with pytest.raises(ValueError, match="cannot be mixed"):
        load_command_access_policy({COMMAND_ACCESS_ENV: "hostname,full_access"})
