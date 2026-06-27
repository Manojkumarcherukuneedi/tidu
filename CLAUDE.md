# AI Task Organizer

## Project
A full-stack web app. Users enter tasks in natural language; an LLM
enriches each task with a category, priority, and suggested due date.
The AI is one feature inside a normal CRUD task app.

## Stack
- Backend: Python, FastAPI
- Database: MySQL
- Frontend: React
- AI: LLM API for task enrichment (structured JSON output)
- Tests: pytest
- CI: GitHub Actions

## Structure
ai-task-organizer/
├── backend/
│   ├── main.py            # FastAPI app + routes
│   ├── database.py        # MySQL connection
│   ├── models.py          # Pydantic schemas
│   ├── ai_service.py      # LLM call + JSON validation + fallback
│   └── tests/
├── frontend/              # React app
├── requirements.txt
├── .github/workflows/ci.yml
└── README.md

## Conventions
- Keep AI logic isolated in ai_service.py. Routes should not call the LLM directly.
- Validate all LLM output with Pydantic before use.
- The app must never crash on bad AI output — fall back to defaults
  (category "Uncategorized", priority "Medium", no due date).
- Write tests for parsing/validation logic and CRUD, not for the live LLM call.
- Keep endpoints RESTful and thin; business logic lives in service functions.

## Build order
1. Backend skeleton + MySQL + health check
2. CRUD endpoints (no AI)
3. AI enrichment on POST /tasks
4. React frontend
5. Tests, README, CI

## Notes
- MySQL credentials and the LLM API key come from environment variables (.env).
- Confirm each slice runs before starting the next.
