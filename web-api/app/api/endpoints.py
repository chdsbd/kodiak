from fastapi import APIRouter


api_router = APIRouter()

@api_router.post("/ping")
def ping():
    return "pong"
