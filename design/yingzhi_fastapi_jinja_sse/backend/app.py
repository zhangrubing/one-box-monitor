
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os, time, json, asyncio

from .crypto import hash_password, verify_password, create_token, verify_token

APP_NAME = "英智AI监控系统"
AUTH_COOKIE = "auth"
SECRET = os.environ.get("APP_SECRET", "dev_secret_change_me")

app = FastAPI(title=APP_NAME, version="B-sse-full")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

USERS = {"admin": {"password_hash": hash_password("admin123"), "email":"admin@local", "role":"Admin", "enabled":1, "last_login": None}}

# ---- auth helpers ----
def current_user(request: Request):
    tok = request.cookies.get(AUTH_COOKIE)
    if not tok: return None
    try:
        p = verify_token(tok, SECRET)
        u = p.get("sub")
        info = USERS.get(u)
        if not info or not info["enabled"]: return None
        return {"username":u, "role": info["role"], "email": info["email"]}
    except Exception:
        return None

def require_login(request: Request):
    u = current_user(request)
    if not u: return None
    request.state.user = u
    return u

# ---- pages ----
def render(name: str, request: Request, active: str):
    return templates.TemplateResponse(name, {"request": request, "active": active, "user": request.state.user})

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_submit(request: Request, username: str = Form(""), password: str = Form("")):
    info = USERS.get(username.strip())
    if not info or not info["enabled"] or not verify_password(password, info["password_hash"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "账号或密码错误"})
    USERS[username]["last_login"] = time.strftime("%Y-%m-%d %H:%M:%S")
    token = create_token({"sub": username, "role": info["role"]}, SECRET, expire_seconds=3600*12)
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie(AUTH_COOKIE, token, httponly=True, samesite="lax", max_age=3600*12, path="/")
    return resp

@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(AUTH_COOKIE, path="/")
    return resp

def guard(request: Request):
    if not require_login(request):
        return RedirectResponse("/login", 302)

@app.get("/")
def dashboard_page(request: Request):
    r = guard(request)
    if r: return r
    return render("dashboard.html", request, "dashboard")

@app.get("/users")
def users_page(request: Request):
    r = guard(request)
    if r: return r
    return render("users.html", request, "users")

@app.get("/hardware")
def hardware_page(request: Request):
    r = guard(request)
    if r: return r
    return render("hardware.html", request, "hardware")

@app.get("/gpu")
def gpu_page(request: Request):
    r = guard(request)
    if r: return r
    return render("gpu.html", request, "gpu")

@app.get("/network")
def network_page(request: Request):
    r = guard(request)
    if r: return r
    return render("network.html", request, "network")

@app.get("/storage")
def storage_page(request: Request):
    r = guard(request)
    if r: return r
    return render("storage.html", request, "storage")

@app.get("/logs")
def logs_page(request: Request):
    r = guard(request)
    if r: return r
    return render("logs.html", request, "logs")

@app.get("/alerts")
def alerts_page(request: Request):
    r = guard(request)
    if r: return r
    return render("alerts.html", request, "alerts")

@app.get("/operations")
def operations_page(request: Request):
    r = guard(request)
    if r: return r
    return render("operations.html", request, "operations")

@app.get("/settings")
def settings_page(request: Request):
    r = guard(request)
    if r: return r
    return render("settings.html", request, "settings")

@app.get("/reports")
def reports_page(request: Request):
    r = guard(request)
    if r: return r
    return render("reports.html", request, "reports")

@app.get("/audit")
def audit_page(request: Request):
    r = guard(request)
    if r: return r
    return render("audit.html", request, "audit")

@app.get("/about")
def about_page(request: Request):
    r = guard(request)
    if r: return r
    return render("about.html", request, "about")

# ---- APIs ----
def authed(request: Request):
    u = current_user(request)
    if not u: raise HTTPException(401, "Unauthorized")
    return u

@app.get("/api/metrics/system")
def api_metrics_system(request: Request):
    authed(request)
    return {"cpu": 27.2, "mem": 43.1, "gpu": 62.0, "alerts": 5}

@app.get("/api/users")
def api_users(request: Request):
    authed(request)
    rows = []
    for u, info in USERS.items():
        rows.append({"u": u, "e": info["email"], "r": info["role"], "s":"启用" if info["enabled"] else "禁用", "t": info["last_login"] or "—"})
    return rows

# ---- SSE（实时） ----
@app.get("/events/metrics")
async def sse_metrics(request: Request):
    authed(request)
    async def gen():
        i = 0
        while True:
            i += 1
            data = {"cpu": 25 + (i % 10), "gpu": 60 + (i % 5)}
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(gen(), media_type="text/event-stream")
