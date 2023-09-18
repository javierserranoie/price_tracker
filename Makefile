.PHONY: build
build:
	@docker build . --tag pricetracker:0.0.1

.PHONY: deploy
deploy:
	@export LOCATION=$(CURDIR) && ./deploy.sh

.PHONY: run
run:
	@sudo systemctl start pricetracker-job.service

.PHONY: run-docker
run-docker:
	@docker run  \
		--name=pricetracker\
		--env-file .env\
		--rm pricetracker:0.0.1

.PHONY: run-github
run-github:
	@act --secret-file .env -j run-script
