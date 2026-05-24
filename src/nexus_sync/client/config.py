import os
from collections.abc import Mapping

from nexus_sync.client.execute import CommandAccessPolicy

COMMAND_ACCESS_ENV = "NEXUS_SYNC_ALLOWED_COMMANDS"
FULL_ACCESS_VALUE = "full_access"


def load_command_access_policy(
    env: Mapping[str, str] = os.environ,
    *,
    default: CommandAccessPolicy | None = None,
) -> CommandAccessPolicy:
    raw_value = env.get(COMMAND_ACCESS_ENV)
    if raw_value is None or not raw_value.strip():
        return default or CommandAccessPolicy.deny_all()

    command_names = [item.strip() for item in raw_value.split(",") if item.strip()]
    if len(command_names) == 1 and command_names[0].lower() == FULL_ACCESS_VALUE:
        return CommandAccessPolicy.allow_all()
    if any(command_name.lower() == FULL_ACCESS_VALUE for command_name in command_names):
        raise ValueError(f"{FULL_ACCESS_VALUE} cannot be mixed with explicit command names")

    return CommandAccessPolicy.allow(command_names)
