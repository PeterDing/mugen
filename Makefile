typecheck:
	mypy -p mugen --ignore-missing-imports --warn-unreachable

format-check:
	black --check .

format:
	black .


build: all
	rm -fr dist
	poetry build -f sdist

publish: all
	poetry publish

build-publish: build publish

all: format-check typecheck
