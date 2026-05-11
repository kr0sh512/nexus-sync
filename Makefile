.PHONY: all client server clean

all: client server

client:
	pyinstaller --onefile src/nexus_sync/client/__main__.py --name nexus-sync-client

server:
	pyinstaller --onefile src/nexus_sync/server/__main__.py --name nexus-sync-server

clean:
	rm -rf build dist *.spec
