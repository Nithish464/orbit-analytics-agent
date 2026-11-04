from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .database import initialize_database, get_schema
from .schemas import AskRequest
from .agents import execute_workflow, EXAMPLES


app = FastAPI(
    title="ORBIT Analytics Agent API",
    description=(
        "Local-first natural-language analytics workflow "
        "with read-only SQL execution."
    ),
    version="1.1.0",
)


# Frontend CORS configuration.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# In-memory request history.
_history = []


@app.on_event("startup")
def startup():
    """
    Initialize the database when the API starts.
    """

    initialize_database()


@app.get("/")
def root():
    return {
        "name": "ORBIT API",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "orbit-api",
        "mode": "deterministic-demo",
    }


@app.get("/api/schema")
def schema():
    return {
        "tables": get_schema(),
    }


@app.get("/api/examples")
def examples():
    return {
        "questions": EXAMPLES,
    }


@app.get("/api/history")
def history():
    return {
        "items": list(reversed(_history[-12:])),
    }


@app.post("/api/ask")
def ask(req: AskRequest):
    """
    Accept a natural-language analytics question.
    """

    question = req.question.strip()

    try:
        result = execute_workflow(question)

        _history.append(
            {
                "question": question,
                "answer": result["answer"],
                "duration_ms": result["duration_ms"],
            }
        )

        # Keep history bounded.
        if len(_history) > 100:
            del _history[:-100]

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception:
        # Avoid exposing internal database or application details.
        raise HTTPException(
            status_code=500,
            detail="Analysis failed. Check API logs.",
        )