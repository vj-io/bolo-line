from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, routes_config, routes_parse, routes_rows, routes_stt

app = FastAPI(title="Bolo Line", version=routes_config.VERSION)
for module in (routes_config, routes_parse, routes_rows, routes_stt):
    app.include_router(module.router)

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
