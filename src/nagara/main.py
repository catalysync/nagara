from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root() -> dict[str, str]:
    return {"hello": "world"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
