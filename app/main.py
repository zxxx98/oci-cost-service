from fastapi import FastAPI

app = FastAPI(title="OCI Current Month Cost Service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
