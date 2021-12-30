.PHONY: help build check upload upload-test

#==============================================================================
# taken from: https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
.DEFAULT_GOAL := help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

#==============================================================================
# Build / check / publish
#==============================================================================

build:  ## Build package
	python setup.py sdist bdist_wheel

check:  ## Check build
	twine check dist/*

upload:  ## Publish to pypi.org
	twine upload dist/*

upload-test:  ## Publish to test.pypi.org
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*

clean: ## erase build/* and dist/*
	rm -rf build
	rm -rf dist	