"""
Mock RESTCONF/YANG server for the Network Programmability demo.

Acts as the programmatic management interface (RESTCONF over HTTP)
for the simulated router, delegating all state access to router_core.py.

Run:
    uvicorn server:app --host 0.0.0.0 --port 8080 --reload
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import time

import router_core

RESTCONF_CONTENT_TYPE = "application/yang-data+json"

app = FastAPI(title="Mock RESTCONF Router")

# Flag used for ACT VII -- pretend the device / transport died.
CHAOS = {"down": False}


@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    # While CHAOS["down"] is True, every /restconf call times out/fails --
    # this represents the "CONNECTION FAILED" beat in Act VII.
    if CHAOS["down"] and request.url.path.startswith("/restconf"):
        time.sleep(1.5)  # feels like a real timeout, not an instant crash
        return JSONResponse(status_code=503, content={"error": "device unreachable"})
    return await call_next(request)


@app.get("/restconf/data/ietf-interfaces:interfaces")
def get_interfaces():
    """Retrieve all interfaces formatted as an ietf-interfaces datastore container."""
    interfaces = router_core.get_all_interfaces()
    return JSONResponse(
        content={"interface": interfaces},
        media_type=RESTCONF_CONTENT_TYPE,
    )


@app.get("/restconf/data/ietf-interfaces:interfaces/interface={name:path}")
def get_interface(name: str):
    """Retrieve single interface by name."""
    intf = router_core.get_interface(name)
    if not intf:
        raise HTTPException(status_code=404, detail=f"interface {name} not found")
    return JSONResponse(content=intf, media_type=RESTCONF_CONTENT_TYPE)


@app.patch("/restconf/data/ietf-interfaces:interfaces/interface={name:path}")
def patch_interface(name: str, body: dict):
    """Patch interface attributes (e.g. enabled, ipv4) via RESTCONF."""
    intf = router_core.update_interface(name, body)
    if not intf:
        raise HTTPException(status_code=404, detail=f"interface {name} not found")
    return JSONResponse(
        content={"result": "ok", "interface": intf},
        media_type=RESTCONF_CONTENT_TYPE,
    )


# ---- Demo-control endpoints (Director's remote for Act VII) ----
@app.post("/simulate/down")
def simulate_down():
    CHAOS["down"] = True
    return {"chaos": True}


@app.post("/simulate/up")
def simulate_up():
    CHAOS["down"] = False
    return {"chaos": False}


@app.post("/simulate/reset")
def simulate_reset():
    CHAOS["down"] = False
    interfaces = router_core.reset_state()
    return {"reset": True, "interfaces": interfaces}
