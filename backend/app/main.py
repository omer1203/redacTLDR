from fastapi import FastAPI

app = FastAPI(title = "RedacTLDR API", version = "0.1.0")

@app.get("/v1/health")
def health():
    return {"status": "ok"}

