import os
import time
import json
import asyncio
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .crypto import hash_password, verify_password, create_token, verify_token
from . import db as dbm
import platform, socket, psutil, subprocess


APP_NAME = "一体机监控系统"
AUTH_COOKIE = "auth"
SECRET = os.environ.get("APP_SECRET", "dev_secret_change_me")

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = FastAPI(title=APP_NAME, version="1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ---- in-memory state for rates ----
PREV_NET: Dict[str, Dict[str, Any]] = {}


# ---- startup: init db and seed ----
@app.on_event("startup")
def on_startup():
    dbm.init_db()
    # seed admin
    dbm.seed_admin_if_missing(hash_password("admin123"))


# ---- auth helpers ----
def current_user(request: Request) -> Optional[dict]:
    tok = request.cookies.get(AUTH_COOKIE)
    if not tok:
        return None
    try:
        payload = verify_token(tok, SECRET)
        username = payload.get("sub")
        row = dbm.user_get_by_username(username)
        if not row or not row["enabled"]:
            return None
        return {"username": row["username"], "role": row["role"], "email": row["email"]}
    except Exception:
        return None


def require_login(request: Request) -> Optional[RedirectResponse]:
    u = current_user(request)
    if not u:
        return RedirectResponse("/login", status_code=302)
    request.state.user = u
    return None


def render(name: str, request: Request, active: str):
    return templates.TemplateResponse(name, {"request": request, "active": active, "user": request.state.user})


# ---- routes: auth ----
@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login_submit(request: Request, username: str = Form(""), password: str = Form("")):
    username = username.strip()
    row = dbm.user_get_by_username(username)
    if not row or not row["enabled"] or not verify_password(password, row["password_hash"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "账号或密码错误"})
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    dbm.user_update_last_login(username, now)
    dbm.audit_append(username, "login", "web")
    token = create_token({"sub": username, "role": row["role"]}, SECRET, expire_seconds=3600 * 12)
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie(AUTH_COOKIE, token, httponly=True, samesite="lax", max_age=3600 * 12, path="/")
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(AUTH_COOKIE, path="/")
    return resp


def guard(request: Request) -> Optional[RedirectResponse]:
    return require_login(request)


# ---- routes: pages ----
@app.get("/")
def dashboard_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("dashboard.html", request, "dashboard")


@app.get("/users")
def users_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("users.html", request, "users")


@app.get("/hardware")
def hardware_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("hardware.html", request, "hardware")


@app.get("/gpu")
def gpu_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("gpu.html", request, "gpu")


@app.get("/network")
def network_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("network.html", request, "network")


@app.get("/storage")
def storage_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("storage.html", request, "storage")


@app.get("/logs")
def logs_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("logs.html", request, "logs")


@app.get("/alerts")
def alerts_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("alerts.html", request, "alerts")


@app.get("/operations")
def operations_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("operations.html", request, "operations")


@app.get("/settings")
def settings_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("settings.html", request, "settings")


@app.get("/reports")
def reports_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("reports.html", request, "reports")


@app.get("/audit")
def audit_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("audit.html", request, "audit")


@app.get("/about")
def about_page(request: Request):
    r = guard(request)
    if r:
        return r
    return render("about.html", request, "about")


# ---- APIs ----
def authed(request: Request):
    u = current_user(request)
    if not u:
        raise HTTPException(401, "Unauthorized")
    return u


@app.get("/api/metrics/system")
def api_metrics_system(request: Request):
    authed(request)
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory().percent
    # GPU avg util if available
    gpu_list = _gpu_list()
    if gpu_list:
        try:
            gpu = round(sum(g.get('util', 0) for g in gpu_list) / max(1, len(gpu_list)), 1)
        except Exception:
            gpu = 0.0
    else:
        gpu = 0.0
    # alerts count placeholder from DB table if exists
    try:
        with dbm.get_db() as db:
            cur = db.execute("SELECT COUNT(*) AS c FROM alerts WHERE status='未确认'")
            alerts = cur.fetchone()[0]
    except Exception:
        alerts = 0
    return {"cpu": cpu, "mem": mem, "gpu": gpu, "alerts": alerts}


@app.get("/api/users")
def api_users(request: Request):
    authed(request)
    rows = dbm.user_list()
    data = []
    for r in rows:
        data.append({
            "u": r["username"],
            "e": r["email"],
            "r": r["role"],
            "s": "启用" if r["enabled"] else "禁用",
            "t": r["last_login"] or "-",
        })
    return data


# ---- SSE（实时） ----
@app.get("/events/metrics")
async def sse_metrics(request: Request):
    authed(request)

    async def gen():
        while True:
            data = {
                "cpu": psutil.cpu_percent(interval=None),
                "gpu": (_gpu_avg_util() or 0.0)
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---- Auth JSON APIs (for XHR login/logout) ----
@app.post("/api/auth/login")
async def api_auth_login(request: Request):
    ct = request.headers.get("content-type", "")
    body = {}
    try:
        if "application/json" in ct:
            body = await request.json()
        else:
            form = await request.form()
            body = dict(form)
    except Exception:
        body = {}

    username = (body.get("username") or body.get("user") or "").strip()
    password = (body.get("password") or body.get("pass") or "")
    if not username or not password:
        return JSONResponse({"ok": False, "error": "缺少用户名或密码"}, status_code=400)

    row = dbm.user_get_by_username(username)
    if not row or not row["enabled"] or not verify_password(password, row["password_hash"]):
        return JSONResponse({"ok": False, "error": "账号或密码错误"}, status_code=401)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    dbm.user_update_last_login(username, now)
    dbm.audit_append(username, "login", "api")
    token = create_token({"sub": username, "role": row["role"]}, SECRET, expire_seconds=3600 * 12)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(AUTH_COOKIE, token, httponly=True, samesite="lax", max_age=3600 * 12, path="/")
    return resp


@app.post("/api/auth/logout")
def api_auth_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(AUTH_COOKIE, path="/")
    return resp


@app.get("/api/auth/me")
def api_auth_me(request: Request):
    u = current_user(request)
    if not u:
        raise HTTPException(401, "Unauthorized")
    return u


# ---- Hardware/System APIs ----
def _uptime_seconds() -> int:
    try:
        boot = psutil.boot_time()
        return int(time.time() - boot)
    except Exception:
        return 0


@app.get("/api/hardware/summary")
def api_hw_summary(request: Request):
    authed(request)
    vm = psutil.virtual_memory()
    try:
        host = socket.gethostname()
    except Exception:
        host = "-"
    data = {
        "hostname": host,
        "os": platform.system(),
        "os_version": platform.version(),
        "kernel": platform.release(),
        "arch": platform.machine(),
        "cpu_physical": psutil.cpu_count(logical=False) or 0,
        "cpu_logical": psutil.cpu_count(logical=True) or 0,
        "mem_total_gb": round(vm.total/1024/1024/1024, 1),
        "mem_used_gb": round((vm.total - vm.available)/1024/1024/1024, 1),
        "uptime_seconds": _uptime_seconds(),
    }
    return data


# ---- GPU APIs ----
def _gpu_list() -> List[Dict[str, Any]]:
    # Try pynvml first
    try:
        import pynvml
        try:
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            out = []
            for i in range(count):
                h = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(h).decode() if isinstance(pynvml.nvmlDeviceGetName(h), bytes) else pynvml.nvmlDeviceGetName(h)
                util = 0
                mem_used = mem_total = 0
                temp = power = 0
                try:
                    ur = pynvml.nvmlDeviceGetUtilizationRates(h)
                    util = getattr(ur, 'gpu', 0)
                except Exception:
                    pass
                try:
                    mi = pynvml.nvmlDeviceGetMemoryInfo(h)
                    mem_used = int(mi.used/1024/1024)
                    mem_total = int(mi.total/1024/1024)
                except Exception:
                    pass
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
                except Exception:
                    pass
                try:
                    power = int(pynvml.nvmlDeviceGetPowerUsage(h)/1000)
                except Exception:
                    pass
                out.append({"id": i, "name": name, "util": util, "mem_used_mb": mem_used, "mem_total_mb": mem_total, "temp_c": temp, "power_w": power})
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
            return out
        except Exception:
            pass
    except Exception:
        pass
    # Fallback to nvidia-smi
    try:
        cmd = ["nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu,power.draw,memory.used,memory.total", "--format=csv,noheader,nounits"]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True, timeout=2)
        rows = []
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 6:
                rows.append({
                    "id": len(rows),
                    "name": parts[0],
                    "util": float(parts[1]) if parts[1] else 0.0,
                    "temp_c": float(parts[2]) if parts[2] else 0.0,
                    "power_w": float(parts[3]) if parts[3] else 0.0,
                    "mem_used_mb": float(parts[4]) if parts[4] else 0.0,
                    "mem_total_mb": float(parts[5]) if parts[5] else 0.0,
                })
        return rows
    except Exception:
        return []


def _gpu_avg_util() -> float:
    try:
        gl = _gpu_list()
        if not gl:
            return 0.0
        return round(sum(g.get('util', 0) for g in gl)/max(1, len(gl)), 1)
    except Exception:
        return 0.0


@app.get("/api/gpu")
def api_gpu(request: Request):
    authed(request)
    return _gpu_list()


# ---- Network APIs ----
def _net_interfaces() -> List[Dict[str, Any]]:
    global PREV_NET
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    io_now = psutil.net_io_counters(pernic=True)
    now = time.time()
    out = []
    for name, st in stats.items():
        ipv4 = next((a.address for a in addrs.get(name, []) if getattr(a, 'family', None).__class__.__name__=='' or str(a.family).endswith('AF_INET')), None)
        ipv6 = next((a.address for a in addrs.get(name, []) if str(a.family).endswith('AF_INET6')), None)
        mac = next((a.address for a in addrs.get(name, []) if str(a.family).endswith('AF_LINK') or str(a.family).endswith('AF_PACKET')), None)
        io = io_now.get(name)
        rx_rate = tx_rate = 0.0
        if io is not None:
            prev = PREV_NET.get(name)
            if prev:
                dt = max(0.001, now - prev['ts'])
                rx_rate = ((io.bytes_recv - prev['rx']) * 8 / 1_000_000) / dt
                tx_rate = ((io.bytes_sent - prev['tx']) * 8 / 1_000_000) / dt
            PREV_NET[name] = { 'rx': io.bytes_recv, 'tx': io.bytes_sent, 'ts': now }
        out.append({
            'name': name,
            'isup': st.isup,
            'speed_mbps': st.speed or 0,
            'mtu': st.mtu,
            'ipv4': ipv4,
            'ipv6': ipv6,
            'mac': mac,
            'rx_bytes': getattr(io, 'bytes_recv', 0) if io else 0,
            'tx_bytes': getattr(io, 'bytes_sent', 0) if io else 0,
            'rx_rate_mbps': round(rx_rate, 1),
            'tx_rate_mbps': round(tx_rate, 1),
        })
    return out


@app.get("/api/network/interfaces")
def api_network_interfaces(request: Request):
    authed(request)
    return _net_interfaces()


# ---- Storage APIs ----
@app.get("/api/storage/disks")
def api_storage_disks(request: Request):
    authed(request)
    parts = []
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
            parts.append({
                'device': p.device,
                'mountpoint': p.mountpoint,
                'fstype': p.fstype,
                'total_gb': round(u.total/1024/1024/1024, 2),
                'used_gb': round(u.used/1024/1024/1024, 2),
                'percent': u.percent,
            })
        except Exception:
            parts.append({
                'device': p.device,
                'mountpoint': p.mountpoint,
                'fstype': p.fstype,
                'total_gb': None,
                'used_gb': None,
                'percent': None,
            })
    return parts
