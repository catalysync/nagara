from fastapi import FastAPI

from nagara.org.api import router as org_router
from nagara.workspace.api import router as workspace_router

app = FastAPI()
app.include_router(org_router)
app.include_router(workspace_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"hello": "world"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
