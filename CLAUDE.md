# Steinbot

## Setup

Always activate the venv before running backend commands:

```bash
cd backend
source venv/bin/activate
```

After activation, use `python3` and `pip` directly.

## Running the API server

```bash
cd backend
source venv/bin/activate
uvicorn api:app --reload
```

## Running the frontend

```bash
cd frontend
npm run dev
```
