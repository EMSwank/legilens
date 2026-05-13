web: cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: cd backend && python -m worker.scheduler
