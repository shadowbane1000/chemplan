.PHONY: dev frontend-dev backend-dev lint frontend-lint build-all frontend-build backend-build

# Development
dev:
	@echo "Starting frontend and backend..."
	@trap 'kill 0' EXIT; \
		$(MAKE) frontend-dev & \
		$(MAKE) backend-dev & \
		wait

frontend-dev:
	cd frontend && npm run dev

backend-dev:
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8123 --reload

# Lint (frontend only — backend has no lint suite yet)
lint: frontend-lint

frontend-lint:
	cd frontend && npm run lint

# Build
build-all: frontend-build backend-build

frontend-build:
	docker build -t chemplan-frontend:latest -f frontend/Dockerfile .

backend-build:
	docker build -t chemplan-backend:latest -f backend/Dockerfile .
