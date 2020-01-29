from fastapi import FastAPI
# from starlette.requests import Request

from app.api import api_router
# from app.db.session import Session

app = FastAPI()

@app.get("/")
def root():
    return "Kodiak web API"

app.include_router(api_router, prefix="/api/v1")


# @app.middleware("http")
# async def db_session_middleware(request: Request, call_next):
#     request.state.db = Session()
#     response = await call_next(request)
#     request.state.db.close()
#     return response
