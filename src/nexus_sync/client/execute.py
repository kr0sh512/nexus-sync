import shlex
import subprocess
from typing import Dict, Optional


def run(command: str, stdin: Optional[str] = None) -> Dict[str, str]:
    process = _execute(command, stdin)

    return {
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def _parse_command(command: str) -> list[str]:
    # return command.split()
    return shlex.split(command)


def _execute(command: str, stdin: Optional[str] = None) -> subprocess.CompletedProcess:
    parsed_command = _parse_command(command)
    result = subprocess.run(
        parsed_command, input=stdin, text=True, capture_output=True, shell=True
    )
    return result
