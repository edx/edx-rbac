.PHONY: clean compile_translations coverage diff_cover docs dummy_translations \
        extract_translations fake_translations help pii_check pull_translations push_translations \
        quality requirements selfcheck test test-all upgrade validate

.DEFAULT_GOAL := help

define BROWSER_PYSCRIPT
import os
import sys
import webbrowser

try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT
BROWSER := python -c "$$BROWSER_PYSCRIPT"

help: ## display this help message
	@echo "Please use \`make <target>' where <target> is one of"
	@perl -nle'print $& if m{^[a-zA-Z_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}'

clean: ## remove generated byte code, coverage reports, and build artifacts, ignores any virtualenvs inside "venvs"
	find . -path ./venvs -prune -name '__pycache__' -exec rm -rf {} +
	find . -path ./venvs -prune -name '*.pyc' -exec rm -f {} +
	find . -path ./venvs -prune -name '*.pyo' -exec rm -f {} +
	find . -path ./venvs -prune -name '*~' -exec rm -f {} +
	coverage erase
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

coverage: clean ## generate and view HTML coverage report
	pytest --cov-report html
	$(BROWSER) htmlcov/index.html

docs: ## generate Sphinx HTML documentation, including API docs
	tox -e docs
	$(BROWSER) docs/_build/html/index.html

upgrade: export CUSTOM_COMPILE_COMMAND=make upgrade
upgrade: ## update the requirements/*.txt files with the latest packages satisfying requirements/*.in
	pip install -qr requirements/pip-tools.txt
	# Make sure to compile files after any other files they include!
	pip-compile --upgrade -o requirements/pip-tools.txt requirements/pip-tools.in
	pip-compile --upgrade -o requirements/base.txt requirements/base.in
	pip-compile --upgrade -o requirements/test.txt requirements/test.in
	pip-compile --upgrade -o requirements/doc.txt requirements/doc.in
	pip-compile --upgrade -o requirements/quality.txt requirements/quality.in
	pip-compile --upgrade -o requirements/travis.txt requirements/travis.in
	pip-compile --upgrade -o requirements/dev.txt requirements/dev.in
	# Let tox control the Django version for tests
	grep -e "^django==" requirements/base.txt > requirements/django.txt
	sed '/^[dD]jango==/d' requirements/test.txt > requirements/test.tmp
	mv requirements/test.tmp requirements/test.txt

quality: ## check coding style with pycodestyle and pylint
	tox -e quality

pii_check: ## check for PII annotations on all Django models
	tox -e pii_check

requirements: ## install development environment requirements
	pip install -qr requirements/pip-tools.txt
	pip-sync requirements/dev.txt requirements/private.*

test: clean ## run tests in the current virtualenv
	pytest

diff_cover: test ## find diff lines that need test coverage
	diff-cover coverage.xml

# Removed pii_check from test-all, because there are no concrete models present in package  
test-all: quality ## run tests on every supported Python/Django combination
	tox

# Removed pii_check from validate, because there are no concrete models present in package
validate: quality test ## run tests and quality checks

selfcheck: ## check that the Makefile is well-formed
	@echo "The Makefile is well-formed."

## Localization targets

extract_translations: ## extract strings to be translated, outputting .mo files
	rm -rf docs/_build
	cd edx-rbac && ../manage.py makemessages -l en -v1 -d django
	cd edx-rbac && ../manage.py makemessages -l en -v1 -d djangojs

compile_translations: ## compile translation files, outputting .po files for each supported language
	cd edx-rbac && ../manage.py compilemessages

detect_changed_source_translations:
	cd edx-rbac && i18n_tool changed

pull_translations: ## pull translations from Transifex
	tx pull -af --mode reviewed

push_translations: ## push source translation files (.po) from Transifex
	tx push -s

dummy_translations: ## generate dummy translation (.po) files
	cd edx_rbac && i18n_tool dummy

build_dummy_translations: extract_translations dummy_translations compile_translations ## generate and compile dummy translation files

validate_translations: build_dummy_translations detect_changed_source_translations ## validate translations
