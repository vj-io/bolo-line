from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, routes_config, routes_parse, routes_rows, routes_stt

app = FastAPI(title="Bolo Line", version=routes_config.VERSION)
for module in (routes_config, routes_parse, routes_rows, routes_stt):
    app.include_router(module.router)


@app.exception_handler(RequestValidationError)
def invalid_request(request: Request, exc: RequestValidationError):
    """Malformed bodies (wrong type, missing field) use the same error shape as every other error."""
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    return JSONResponse(status_code=422, content={"error": "invalid_request", "message": f"{where}: {first.get('msg', 'invalid')}"})

WEB = config.WEB_DIR


@app.get("/", include_in_schema=False)
def operator_page():
    return FileResponse(WEB / "index.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return FileResponse(WEB / "dashboard.html")


@app.get("/demo", include_in_schema=False)
def demo_page():
    return FileResponse(WEB / "demo.html")


for prefix in ("shared", "station", "dashboard", "vendor", "samples"):
    app.mount(f"/{prefix}", StaticFiles(directory=WEB / prefix), name=prefix)
app.mount("/audio", StaticFiles(directory=config.data_dir() / "audio"), name="audio")
