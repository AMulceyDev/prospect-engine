from fastapi import FastAPI

app = FastAPI(title="Prospect Engine")

@app.get("/")
def health():
    return {"status": "ok"}