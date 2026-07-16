from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.incidents import router as incidents_router
from backend.app.api.pipelines import router as pipelines_router


app = FastAPI(title="Data Reliability Agent")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(incidents_router)
app.include_router(pipelines_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}