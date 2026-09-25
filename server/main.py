import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

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


WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    """Serves the built web app. Real files (JS, CSS, GeoJSON) are returned
    as-is; any other path gets index.html so client-side routes like /plan
    survive a reload."""
    if path.startswith("api/") or not WEB_DIST.exists():
        raise HTTPException(status_code=404)
    candidate = (WEB_DIST / path).resolve()
    if path and candidate.is_file() and WEB_DIST in candidate.parents:
        return FileResponse(candidate, media_type=_MEDIA_TYPES.get(candidate.suffix))
    # A missing static asset is a real 404. Answering it with index.html once
    # hid a missing map worker behind a 200. Only known asset extensions
    # count: ward keys contain dots (/brief/ward_369_final.317 is a route).
    if Path(path).suffix.lower() in _STATIC_SUFFIXES:
        raise HTTPException(status_code=404)
    return FileResponse(WEB_DIST / "index.html")


# Module workers require a JavaScript MIME type; GeoJSON gets its own.
_MEDIA_TYPES = {".mjs": "text/javascript", ".js": "text/javascript", ".geojson": "application/geo+json"}
_STATIC_SUFFIXES = {".js", ".mjs", ".css", ".map", ".json", ".geojson", ".svg", ".png", ".jpg", ".ico", ".woff", ".woff2", ".txt", ".py"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
