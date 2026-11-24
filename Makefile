# Every task for working on Daruma, in one place.
#
#   make            this help
#   make test       host tests in Python and C++
#   make -n <goal>  print the commands without running them
#
# Plain GNU make; macOS's make 3.81 works. The tools come from uv.lock:
# ESPHome and the dev tools all live in .venv (pyproject.toml).
# Variables that are empty by default add a flag only when you set them,
# so each tool keeps its own default.

.DEFAULT_GOAL := help
SHELL := /bin/sh

# --- Variables -----------------------------------------------------------

EXAMPLE ?= ## An example in examples/, without .yaml (config: all; compile: box3)
PERSONA ?= ## Personas to record, check or update, comma-separated (default: all)
SCENARIO ?= ## Scenarios to record, check or update, comma-separated (default: all)
VARIANT ?= ## Screen for gifs: standard, wide or square (default: standard)
JOBS ?= ## Runs at a time for gifs (default: up to 4); pytest takes -n in PYTEST_ARGS
DOCS ?= ## Where gifs writes the GIFs (default: docs/demos)
PYTEST_ARGS ?= ## Extra pytest arguments, for example "-n 0" or "-k corgi"
DOCKER_CMD ?= ## A command for docker-test (default: golden and screen tests)
GROUP ?= ## One dependency group for setup: test, lint, tidy, dev or esphome
CONFIRM ?= ## Set to 1 to let update-golden write golden pictures
BUILD_REF ?= ci-head## The scratch branch that config and compile point at HEAD (default: ci-head)
BASE ?= origin/main## What mutate-diff compares with, from the merge base (default: origin/main)
PART ?= ## Part K of N of mutate-diff, such as 2/3; C++ runs in part 1 (default: the whole run)

# DARUMA_WORK is the scratch folder of record.py (--out) and pytest. Empty
# means each uses its default temp folder.
DARUMA_WORK ?=
# The ESPHome API port of `make desktop`.
DARUMA_PORT ?=

# uv run syncs .venv first; UV_NO_SYNC=1 skips that.
UV_RUN := uv run
ESPHOME := $(CURDIR)/.venv/bin/esphome
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

# The scenario tests that PERSONA= and SCENARIO= pick (demos/conftest.py).
SCREENS := $(UV_RUN) pytest demos \
	$(if $(PERSONA),--persona '$(PERSONA)') \
	$(if $(SCENARIO),--scenario '$(SCENARIO)')

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

.PHONY: help setup esphome-env esphome-version secrets config compile desktop \
	test test-py test-cpp mutate mutate-diff mutate-parts screens golden test-screens update-golden update-frames gifs \
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

setup: ## Install the tools: ESPHome and the dev groups (GROUP= for one group)
ifeq ($(GROUP),)
	uv sync --locked
else
	uv sync --locked --only-group $(GROUP) --no-install-project
endif

# ESPHome in .venv, next to whatever else is there. A fast no-op when it
# is up to date.
esphome-env:
	uv sync --locked --inexact --only-group esphome --no-install-project --quiet

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

# --- ESPHome builds ------------------------------------------------------

# The examples fetch BUILD_REF from this checkout, so commit first: an
# uncommitted change is not in the build. ESPHome refreshes a git package
# only once a day, so the old clone goes first.
#
# Every example is checked, even after one fails; the failed ones are
# listed at the end. One at a time: the first check draws the persona art
# and the rest reuse it. In GitHub Actions each example gets a log group.
config: secrets esphome-env ## Check the config of every example, or EXAMPLE=box3
	git branch -f $(BUILD_REF) HEAD
	rm -rf examples/.esphome/packages
	@cd examples; failed=""; log=$$(mktemp); for ex in $(CONFIG_EXAMPLES); do \
	  if [ -n "$$GITHUB_ACTIONS" ]; then echo "::group::esphome config $$ex.yaml"; else echo "== esphome config $$ex.yaml"; fi; \
	  $(ESPHOME) $(ESPHOME_SUBS) config $$ex.yaml > "$$log" 2>&1 || { tail -n 60 "$$log"; failed="$$failed $$ex"; }; \
	  if [ -n "$$GITHUB_ACTIONS" ]; then echo "::endgroup::"; fi; \
	done; rm -f "$$log"; \
	if [ -n "$$failed" ]; then echo "Config failed:$$failed"; exit 1; fi

compile: secrets esphome-env ## Compile an example's firmware (default EXAMPLE=box3); commit first
	git branch -f $(BUILD_REF) HEAD
	rm -rf examples/.esphome/packages
	cd examples && $(ESPHOME) $(ESPHOME_SUBS) compile $(COMPILE_EXAMPLE).yaml

desktop: secrets esphome-env ## Build and run the desktop device in a window (DARUMA_PORT= for the API port)
	cd examples && $(ESPHOME) $(if $(DARUMA_PORT),-s desktop_api_port $(DARUMA_PORT)) run desktop.yaml

# --- Tests ---------------------------------------------------------------

test: test-py test-cpp ## Host tests in Python and C++ (no ESPHome build)

test-py: ## Host tests in Python (PYTEST_ARGS= for pytest)
	$(UV_RUN) pytest tests -m "not cpp" $(PYTEST_ARGS)

test-cpp: ## Host tests in C++, through pytest (PYTEST_ARGS="-k layout" for one)
	$(UV_RUN) pytest tests -m cpp $(PYTEST_ARGS)

# Mutation tests (docs/testing.md). Python, then C++; both run when the
# first fails.
mutate: ## Mutation tests of all the code the host tests reach: a report, never fails on survivors
	@status=0; \
	$(UV_RUN) python tests/mutate_py.py || status=1; \
	$(UV_RUN) python tests/mutate_cpp.py || status=1; \
	exit $$status

# A fresh mutants/ each time, as in CI: mutmut keeps old mutants when only
# a comment changed, so it would miss a new pragma.
mutate-diff: ## Mutation tests of the lines changed since BASE; fails on a surviving mutant (MINUTES= caps the Python run, PART=K/N)
	rm -rf mutants
	@status=0; \
	$(UV_RUN) python tests/mutate_py.py --diff '$(BASE)' $(if $(PART),--part $(PART)) $(if $(MINUTES),--minutes $(MINUTES)) || status=1; \
	$(if $(filter-out 1/%,$(PART)),true,$(UV_RUN) python tests/mutate_cpp.py --diff '$(BASE)') || status=1; \
	exit $$status

mutate-parts: ## How many parts CI runs mutate-diff in for the change since BASE
	$(UV_RUN) python tests/mutate_py.py --diff '$(BASE)' --count-parts

screens: secrets ## The golden check and the screen tests, in one pytest run (PERSONA=, SCENARIO=, PYTEST_ARGS=)
	$(SCREENS) $(PYTEST_ARGS)

golden: secrets ## Check the scenarios against the golden pictures (PERSONA=, SCENARIO=, PYTEST_ARGS=)
	$(SCREENS) -m scenario $(PYTEST_ARGS)

test-screens: secrets ## The screen tests in Python, without the scenarios (PYTEST_ARGS=)
	$(UV_RUN) pytest demos -m "not scenario" $(PYTEST_ARGS)

update-golden: secrets ## Write new golden pictures, screens and persona frames; needs CONFIRM=1 (PERSONA=, SCENARIO=)
ifneq ($(CONFIRM),1)
	@echo "update-golden rewrites tests/golden. Run: make update-golden CONFIRM=1" >&2
	@exit 1
endif
	$(UV_RUN) python tests/persona_frames.py update
	$(SCREENS) -m scenario --update-golden $(PYTEST_ARGS)

update-frames: ## Write new golden pictures of the persona frames only; needs CONFIRM=1
ifneq ($(CONFIRM),1)
	@echo "update-frames rewrites tests/golden/frames. Run: make update-frames CONFIRM=1" >&2
	@exit 1
endif
	$(UV_RUN) python tests/persona_frames.py update

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
