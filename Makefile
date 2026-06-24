.PHONY: all client server cli test clean

all: client server cli

client:
	pyinstaller --onefile src/nexus_sync/client/__main__.py --name nexus-sync-client

server:
	pyinstaller --onefile src/nexus_sync/server/__main__.py --name nexus-sync-server

cli:
	pyinstaller --onefile src/nexus_sync/cli/__main__.py --name nexus-cli

test:
	pytest

clean:
	rm -rf build dist *.spec
