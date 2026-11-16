# Every task for working on Daruma, for people and for CI.
#
#   make            this help
#   make test       host tests in Python and C++
#   make -n <goal>  print the commands without running them
#
# Plain GNU make; macOS's make 3.81 works. The tools come from uv.lock:
# the dev groups live in .venv, ESPHome in .venv-esphome (pyproject.toml).
# Variables that are empty by default add a flag only when you set them,
# so each tool keeps its own default.

.DEFAULT_GOAL := help
SHELL := /bin/sh

# --- Variables -----------------------------------------------------------

EXAMPLE ?= ## An example in examples/, without .yaml (config: all; compile: box3)
PERSONA ?= ## Personas to record or update, comma-separated (default: all)
SCENARIO ?= ## Scenarios to record or update, comma-separated (default: all)
VARIANT ?= ## Screen for gifs: standard, wide or square (default: standard)
JOBS ?= ## Runs at a time for record.py (default: up to 4)
DOCS ?= ## Where gifs writes the GIFs (default: docs/demos)
PYTEST_ARGS ?= ## Extra pytest arguments, for example "-n 0" or "-k corgi"
DOCKER_CMD ?= ## A command for docker-test (default: golden and screen tests)
GROUP ?= ## One dependency group for setup: test, lint, tidy, dev or esphome
CONFIRM ?= ## Set to 1 to let update-golden write golden pictures
BUILD_REF ?= ci-head## The scratch branch that config and compile point at HEAD (default: ci-head)

# DARUMA_WORK is the scratch folder of record.py (--out) and pytest. Empty
# means each uses its default temp folder.
DARUMA_WORK ?=
# The Python of .venv-esphome; the screen test harness uses the same one.
DARUMA_PYTHON ?= $(shell cat .python-version)
# The ESPHome API port of `make desktop`.
DARUMA_PORT ?=

# uv run syncs .venv first. CI sets UV_NO_SYNC=1, as each job syncs only
# the groups it needs.
UV_RUN := uv run
ESPHOME_ENV := .venv-esphome
ESPHOME := $(CURDIR)/$(ESPHOME_ENV)/bin/esphome
# The examples fetch Daruma with git. These point them at this checkout.
DARUMA_URL := file://$(CURDIR)
ESPHOME_SUBS := -s daruma_url "$(DARUMA_URL)" -s daruma_ref "$(BUILD_REF)"

ALL_EXAMPLES := $(filter-out secrets%,$(basename $(notdir $(wildcard examples/*.yaml))))
CONFIG_EXAMPLES := $(if $(EXAMPLE),$(EXAMPLE),$(ALL_EXAMPLES))
COMPILE_EXAMPLE := $(if $(EXAMPLE),$(EXAMPLE),box3)

RECORD := $(UV_RUN) python demos/record.py \
	$(if $(PERSONA),--personas '$(PERSONA)') \
	$(if $(SCENARIO),--scenario '$(SCENARIO)') \
	$(if $(DARUMA_WORK),--out '$(DARUMA_WORK)') \
	$(if $(JOBS),--jobs $(JOBS))

# clang-tidy on macOS needs the SDK's headers.
ifeq ($(shell uname -s),Darwin)
TIDY_ARGS := --extra-arg=-isysroot --extra-arg="$$(xcrun --show-sdk-path)"
endif

FORMAT_HOOKS ?= ruff-check ruff-format clang-format
COMPLEXITY_HOOKS := complexipy lizard

# Runs each pre-commit hook in $(1) on every file. It runs them all, then
# fails if any failed.
define run_hooks
	@status=0; \
	for hook in $(1); do \
	  $(UV_RUN) pre-commit run $$hook --all-files --show-diff-on-failure || status=1; \
	done; \
	exit $$status
endef

.PHONY: help setup esphome-env esphome-version secrets secrets-ci config compile desktop \
	test test-py test-cpp screens golden test-screens update-golden gifs \
	lint format complexity tidy docker-test check clean

# --- Help ----------------------------------------------------------------

help: ## Show the goals and variables
	@echo "Usage: make <goal> [VARIABLE=value ...]"
	@echo
	@echo "Goals:"
	@awk 'BEGIN { FS = ":.*## " } /^[a-z][a-z-]*:.*## / { printf "  %-16s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo
	@echo "Variables:"
	@awk 'BEGIN { FS = " \\?=[^#]*## " } /^[A-Z_]+ \?=.*## / { printf "  %-16s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# --- Setup ---------------------------------------------------------------

setup: ## Install the tools: the dev groups and ESPHome (GROUP= for one group)
ifeq ($(GROUP),)
	uv sync --locked
	@$(MAKE) --no-print-directory esphome-env
else ifeq ($(GROUP),esphome)
	@$(MAKE) --no-print-directory esphome-env
else
	uv sync --locked --only-group $(GROUP) --no-install-project
endif

# ESPHome pins an older aioesphomeapi than the screen tests, so it gets its
# own environment. A fast no-op when it is up to date.
esphome-env:
	env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT=$(ESPHOME_ENV) \
	  uv sync --locked --only-group esphome --no-install-project --python $(DARUMA_PYTHON) --quiet

esphome-version: ## Print the ESPHome version the builds use
	@sed -n 's/^esphome = \["esphome==\(.*\)"\]$$/\1/p' pyproject.toml

# --- Secrets -------------------------------------------------------------

# The builds depend on secrets, so a fresh checkout needs no manual step.
secrets: examples/secrets.yaml ## Write examples/secrets.yaml from the example, with a random API key; never overwrites it
	$(if $(filter secrets,$(MAKECMDGOALS)),@echo "examples/secrets.yaml is in place. Make never overwrites it.",@:)

# No prerequisites on purpose: make never rewrites an existing file.
examples/secrets.yaml:
	@key=$$(openssl rand -base64 32) && \
	  sed "s|^daruma_api_key:.*|daruma_api_key: \"$$key\"|" examples/secrets.example.yaml > $@.tmp && \
	  mv $@.tmp $@
	@echo "Wrote examples/secrets.yaml: placeholder Wi-Fi, a random API key."

# The fixed public secrets of examples/secrets.ci.yaml. It refuses to
# replace a secrets.yaml with other content.
secrets-ci: ## CI only: copy examples/secrets.ci.yaml to examples/secrets.yaml
	@if [ -e examples/secrets.yaml ] && ! cmp -s examples/secrets.ci.yaml examples/secrets.yaml; then \
	  echo "examples/secrets.yaml exists and differs from secrets.ci.yaml. Move it away first." >&2; \
	  exit 1; \
	fi
	cp examples/secrets.ci.yaml examples/secrets.yaml

# --- ESPHome builds ------------------------------------------------------

# The examples fetch BUILD_REF from this checkout, so commit first: an
# uncommitted change is not in the build. ESPHome refreshes a git package
# only once a day, so the old clone goes first.
config: secrets esphome-env ## Check the config of every example, or EXAMPLE=box3
	git branch -f $(BUILD_REF) HEAD
	rm -rf examples/.esphome/packages
	@set -e; cd examples; for ex in $(CONFIG_EXAMPLES); do \
	  echo "== esphome config $$ex.yaml"; \
	  $(ESPHOME) $(ESPHOME_SUBS) config $$ex.yaml > /dev/null; \
	done

compile: secrets esphome-env ## Compile an example's firmware (default EXAMPLE=box3); commit first
	git branch -f $(BUILD_REF) HEAD
	rm -rf examples/.esphome/packages
	cd examples && $(ESPHOME) $(ESPHOME_SUBS) compile $(COMPILE_EXAMPLE).yaml

desktop: secrets esphome-env ## Build and run the desktop device in a window (DARUMA_PORT= for the API port)
	cd examples && $(ESPHOME) $(if $(DARUMA_PORT),-s desktop_api_port $(DARUMA_PORT)) run desktop.yaml

# --- Tests ---------------------------------------------------------------

test: test-py test-cpp ## Host tests in Python and C++ (no ESPHome build)

test-py: ## Host tests in Python (PYTEST_ARGS= for pytest)
	$(UV_RUN) pytest tests $(PYTEST_ARGS)

test-cpp: ## Host tests in C++
	tests/run_cpp.sh

screens: golden test-screens ## The golden check, then the screen tests; make -k runs both on a failure

golden: secrets ## Check the screens against the golden pictures (PERSONA=, SCENARIO=, JOBS=)
	$(RECORD) --test

test-screens: secrets ## Screen tests in pytest on the desktop build (PYTEST_ARGS=)
	$(UV_RUN) pytest demos $(PYTEST_ARGS)

update-golden: secrets ## Write new golden pictures; needs CONFIRM=1 (PERSONA=, SCENARIO=)
ifneq ($(CONFIRM),1)
	@echo "update-golden rewrites tests/golden. Run: make update-golden CONFIRM=1" >&2
	@exit 1
endif
	$(RECORD) --update-golden

gifs: secrets ## Record demo GIFs (PERSONA=, SCENARIO=, VARIANT=, DOCS=, JOBS=)
	$(RECORD) $(if $(VARIANT),--variant $(VARIANT)) $(if $(DOCS),--docs '$(DOCS)')

docker-test: ## The golden check and screen tests in Ubuntu 24.04, as CI runs them (DOCKER_CMD=)
	tests/in_docker.sh $(DOCKER_CMD)

# --- Lint ----------------------------------------------------------------

lint: ## Every pre-commit hook on every file; the formatters fix files in place
	$(call run_hooks,$(COMPLEXITY_HOOKS) $(FORMAT_HOOKS))

format: ## Format Python and C++ (ruff, clang-format) on every file
	$(call run_hooks,$(FORMAT_HOOKS))

complexity: ## Complexity limits: complexipy for Python, lizard for C and C++
	$(call run_hooks,$(COMPLEXITY_HOOKS))

tidy: ## clang-tidy on the host C++ tests and the headers they include
	tests/compile_db.sh
	$(UV_RUN) clang-tidy -p build/clang-tidy --quiet $(TIDY_ARGS) tests/test_*.cpp

# --- All -----------------------------------------------------------------

check: test complexity tidy config compile screens ## Everything CI blocks on (the formatters don't block yet)

clean: ## Remove build output in this checkout (not .venv, secrets or DARUMA_WORK)
	rm -rf build examples/.esphome .pytest_cache .complexipy_cache
	find . -name __pycache__ -type d -not -path './.venv*' -prune -exec rm -rf {} +
