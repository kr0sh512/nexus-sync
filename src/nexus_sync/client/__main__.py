import sys

from nexus_sync.client.runtime import main
from nexus_sync.utils import configure_logging

if __name__ == "__main__":
    configure_logging()
    raise SystemExit(main(sys.argv[1:]))
