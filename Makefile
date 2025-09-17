# Simple dev targets

.PHONY: dev backend frontend stop

VENV=.venv-sfgov

## Run backend and frontend together (uses dev.sh)
dev:
	bash ./dev.sh

## Run backend API only (uses existing venv or creates it)
backend:
	@if [ ! -d "$(VENV)" ]; then python3 -m venv $(VENV); fi
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload

## Run frontend dev server only
frontend:
	cd web && npm install && npm run dev

## Stop backend (best effort)
stop:
	-@pkill -f "uvicorn backend.api" || true
