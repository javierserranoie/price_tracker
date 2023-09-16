.PHONY: run-github
run-github:
	@act --secret-file .env -j run-script

.PHONY: build
build:
	@docker build . --tag pricetracker:0.0.1

.PHONY: run
run:
	@docker run  \
		--name=pricetracker\
		--env-file .env\
		--rm pricetracker:0.0.1