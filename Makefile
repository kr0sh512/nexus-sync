.PHONY: all client server cli test clean docs docs-clean i18n-extract i18n-init i18n-update i18n-compile

# CLI localization (nexus-cli strings only; daemon/server logs stay in English).
LOCALE_DIR := src/nexus_sync/locale
POT := $(LOCALE_DIR)/nexus.pot
LANG ?= ru
# PyInstaller --add-data separator is ':' on Unix, ';' on Windows.
LOCALE_DATA := $(LOCALE_DIR):nexus_sync/locale

all: client server cli

client:
	pyinstaller --onefile src/nexus_sync/client/__main__.py --name nexus-sync-client

server:
	pyinstaller --onefile src/nexus_sync/server/__main__.py --name nexus-sync-server

cli: i18n-compile
	pyinstaller --onefile src/nexus_sync/cli/__main__.py --name nexus-cli \
		--add-data "$(LOCALE_DATA)"

# Rebuild the message template from strings wrapped in _()/gettext()/ngettext().
i18n-extract:
	pybabel extract -F babel.cfg -k _ -o $(POT) src

# Create a catalog for a new language, e.g. `make i18n-init LANG=de`.
i18n-init: i18n-extract
	pybabel init -i $(POT) -d $(LOCALE_DIR) -D nexus -l $(LANG)

# Merge new/changed strings into existing catalogs.
i18n-update: i18n-extract
	pybabel update -i $(POT) -d $(LOCALE_DIR) -D nexus

# Compile .po catalogs to the .mo files bundled with nexus-cli.
i18n-compile:
	pybabel compile -d $(LOCALE_DIR) -D nexus

test:
	pytest

# Build the Sphinx HTML documentation into docs/_build/html.
docs:
	sphinx-build -b html docs docs/_build/html

docs-clean:
	rm -rf docs/_build

clean:
	rm -rf build dist *.spec docs/_build
