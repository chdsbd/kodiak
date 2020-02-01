from fastapi import FastAPI
from starlette.responses import PlainTextResponse, Response

from app import config  # noqa
from app.api import api_router

# from app.db.session import Session
# from starlette.requests import Request


app = FastAPI()


@app.get("/")
def root() -> Response:
    return PlainTextResponse("OK")


app.include_router(api_router, prefix="/v1")


# @app.middleware("http")
# async def db_session_middleware(request: Request, call_next):
#     request.state.db = Session()
#     response = await call_next(request)
#     request.state.db.close()
#     return response
