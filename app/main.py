# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routers import auth, courses, favorites, simulate, comments, admin, credits,announcement,profile,admin_course,timetable

from fastapi.staticfiles import StaticFiles

import time
import logging
from fastapi import Request
from app.logging_config import setup_logging


setup_logging()
logger = logging.getLogger("app")


# 建立資料表（若不存在）
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Course Selection Backend", version="1.0.0")

app.include_router(credits.router)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(profile.router)

# CORS 設定
origins = [
    "http://localhost:3000",   
    "http://127.0.0.1:3000",
    "http://localhost:3000/*",
    "https://search-system-xi.vercel.app/*",
]
allow_credentials=True

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
        ms = int((time.time() - start) * 1000)
        logger.info("%s %s -> %s (%dms)", request.method, request.url.path, response.status_code, ms)
        return response
    except Exception:
        ms = int((time.time() - start) * 1000)
        logger.exception("Unhandled error %s %s (%dms)", request.method, request.url.path, ms)
        raise


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(favorites.router)
app.include_router(simulate.router)
app.include_router(comments.router)
app.include_router(admin.router)
app.include_router(credits.router)
app.include_router(announcement.router) 
app.include_router(admin_course.router)
app.include_router(timetable.router)

@app.get("/")
def root():
    return {"message": "Course backend is running!"}
