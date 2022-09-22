.PHONY: clean clean-build clean-pyc dist help
.DEFAULT_GOAL := help

help:
	@echo "clean - remove all artifacts"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove python artifacts"
	@echo "install - install the package"
	@echo "init - initialize the development environment"
	@echo "dist - build package"
	@echo "release - upload package to PyPi"
	@echo "lint - check style with pylint"

clean: clean-build clean-pyc

clean-build:
	rm -rf build/
	rm -rf dist/
	rm -rf .eggs/
	find . -name '*.egg-info' -exec rm -rf {} +
	find . -name '*.egg' -exec rm -rf {} +
	find . -name '.DS_Store' -exec rm -f {} +

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -rf {} +

lint:
	pylint --max-line-length=120 --rcfile=setup.cfg tracker_exporter

dist:
	python3 setup.py sdist bdist_wheel

release: clean dist
	@make clean
	@make dist
	python3 -m twine upload --repository pypi dist/*

install: clean
	python3 setup.py install

init:
	pip3 install -r requirements-dev.txt