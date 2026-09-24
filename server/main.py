import os

import uvicorn
from fastapi import FastAPI

from server.api.wards import router as wards_router

app = FastAPI(title="Penumbra")
app.include_router(wards_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
