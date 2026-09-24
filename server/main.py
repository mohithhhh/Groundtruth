import os

import uvicorn
from fastapi import FastAPI

from server.api.ask import router as ask_router
from server.api.brief import router as brief_router
from server.api.plan import router as plan_router
from server.api.wards import router as wards_router

app = FastAPI(title="Penumbra")
app.include_router(wards_router, prefix="/api")
app.include_router(ask_router, prefix="/api")
app.include_router(plan_router, prefix="/api")
app.include_router(brief_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
