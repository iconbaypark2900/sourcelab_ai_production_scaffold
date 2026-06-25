.PHONY: install install-all test smoke demo api dashboard release-check ga-check freeze freeze-check clean-artifacts web-install web-dev web-build

install:
	python -m pip install --upgrade pip setuptools wheel
	python -m pip install -e ".[dev]"

install-all:
	python -m pip install --upgrade pip setuptools wheel
	python -m pip install -e ".[dev,api,ui,ingest,retrieval,models]"

test:
	pytest -q

smoke:
	bash scripts/local_v1_smoke.sh

demo:
	bash scripts/local_v1_demo.sh

api:
	bash scripts/start_api.sh

dashboard:
	bash scripts/start_dashboard.sh

release-check:
	sourcelab release check
	sourcelab verify-release --strict

ga-check:
	pytest -q
	sourcelab doctor
	sourcelab init-local
	sourcelab local-demo
	sourcelab verify-release --strict
	sourcelab release bundle
	sourcelab release checksums
	sourcelab release sbom
	sourcelab release attest

freeze:
	bash scripts/freeze_requirements.sh

freeze-check:
	bash scripts/freeze_requirements.sh --check

clean-artifacts:
	rm -rf artifacts/runs artifacts/evals artifacts/release artifacts/index

# ---------------------------------------------------------------------------
# Run Studio (Next.js frontend in apps/web)
# Backend must be served separately: `sourcelab api --serve`.
# ---------------------------------------------------------------------------
web-install:
	cd apps/web && npm install

web-dev:
	cd apps/web && npm run dev

web-build:
	cd apps/web && npm run build
