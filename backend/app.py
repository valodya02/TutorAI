from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

load_dotenv()

from pathlib import Path
from backend.books import router as books_router
from backend.courses import router as courses_router
from backend.generation import router as generation_router
ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI()
app.include_router(books_router)
app.include_router(courses_router)
app.include_router(generation_router)
app.mount("/", StaticFiles(directory=FRONTEND, html=True))
