.PHONY: install install-dev
install:
	python -m pip install .

install-dev:
	python -m pip install -e .
	python .setup_git_hooks.py
