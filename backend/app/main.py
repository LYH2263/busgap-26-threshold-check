from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.migrate import run_migrations
from app.services.line_validation import LineParamsError
from app.services.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="BusGap", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LineParamsError)
async def line_params_error_handler(_req: Request, exc: LineParamsError) -> JSONResponse:
    # 回包点出的 field/label 与线路页校验提示同一套用词
    return JSONResponse(
        status_code=400,
        content={"detail": {"message": "线路参数校验失败", "errors": exc.errors}},
    )


app.include_router(api_router, prefix="/api")
