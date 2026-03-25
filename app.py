import streamlit as st
import requests
import time
from datetime import datetime

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Device Manager",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Default device config ─────────────────────────────────────────────────────
DEFAULT_DEVICES = [
    {"name": "Device 1", "ip": "192.168.137.7", "port": 80},
    {"name": "Device 2", "ip": "192.168.137.68", "port": 80},
]

# ── Session state init ────────────────────────────────────────────────────────
if "devices" not in st.session_state:
    st.session_state.devices = DEFAULT_DEVICES
if "log" not in st.session_state:
    st.session_state.log = []

# ── Helpers ───────────────────────────────────────────────────────────────────
def build_url(device: dict, path: str = "") -> str:
    port = device["port"]
    base = f"http://{device['ip']}" if port == 80 else f"http://{device['ip']}:{port}"
    return base + (f"/{path.lstrip('/')}" if path else "")


def check_status(device: dict, timeout: float = 3.0) -> dict:
    url = build_url(device)
    try:
        t0 = time.time()
        r = requests.get(url, timeout=timeout)
        latency = round((time.time() - t0) * 1000, 1)
        return {"online": True, "code": r.status_code, "latency_ms": latency}
    except requests.exceptions.ConnectionError:
        return {"online": False, "code": None, "latency_ms": None, "error": "Connection refused"}
    except requests.exceptions.Timeout:
        return {"online": False, "code": None, "latency_ms": None, "error": "Timeout"}
    except Exception as e:
        return {"online": False, "code": None, "latency_ms": None, "error": str(e)}


def send_request(device: dict, method: str, path: str, payload: dict | None = None) -> dict:
    url = build_url(device, path)
    try:
        fn = getattr(requests, method.lower())
        kwargs = {"timeout": 5}
        if payload:
            kwargs["json"] = payload
        r = fn(url, **kwargs)
        return {"ok": True, "status": r.status_code, "body": r.text[:2000]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def add_log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.log.insert(0, f"[{ts}] {msg}")
    st.session_state.log = st.session_state.log[:100]  # keep last 100


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Cấu hình")
    st.subheader("Danh sách thiết bị")

    devices_cfg = []
    for i, dev in enumerate(st.session_state.devices):
        with st.expander(f"📡 {dev['name']}", expanded=True):
            name = st.text_input("Tên", value=dev["name"], key=f"name_{i}")
            ip   = st.text_input("IP Address", value=dev["ip"], key=f"ip_{i}")
            port = st.number_input("Port", min_value=1, max_value=65535,
                                   value=dev["port"], key=f"port_{i}")
            devices_cfg.append({"name": name, "ip": ip, "port": int(port)})

    col_add, col_del = st.columns(2)
    if col_add.button("➕ Thêm", use_container_width=True):
        st.session_state.devices.append({"name": f"Device {len(st.session_state.devices)+1}",
                                          "ip": "192.168.137.1", "port": 80})
        st.rerun()
    if col_del.button("➖ Xóa", use_container_width=True) and len(st.session_state.devices) > 1:
        st.session_state.devices.pop()
        st.rerun()

    if st.button("💾 Lưu cấu hình", use_container_width=True, type="primary"):
        st.session_state.devices = devices_cfg
        add_log("Đã lưu cấu hình thiết bị")
        st.success("Đã lưu!")

    st.divider()
    auto_refresh = st.toggle("🔄 Tự động làm mới", value=False)
    refresh_interval = st.slider("Interval (giây)", 5, 60, 10, disabled=not auto_refresh)

# ── Main area ─────────────────────────────────────────────────────────────────
st.title("🖥️ Bảng quản lý thiết bị")

devices = st.session_state.devices

# ── Status cards ──────────────────────────────────────────────────────────────
st.subheader("📊 Trạng thái thiết bị")

cols = st.columns(len(devices))
statuses: list[dict] = []

for col, dev in zip(cols, devices):
    status = check_status(dev)
    statuses.append(status)
    with col:
        if status["online"]:
            st.success(f"**{dev['name']}**\n\n🟢 Online")
            st.metric("Latency", f"{status['latency_ms']} ms")
            st.metric("HTTP Status", status["code"])
        else:
            st.error(f"**{dev['name']}**\n\n🔴 Offline")
            st.caption(status.get("error", "Unknown error"))
        st.caption(f"🌐 {build_url(dev)}")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_control, tab_request, tab_log = st.tabs(["🎮 Điều khiển", "📡 Gửi Request", "📋 Nhật ký"])

# ── Tab 1: Quick controls ─────────────────────────────────────────────────────
with tab_control:
    st.subheader("Điều khiển nhanh")
    ctrl_cols = st.columns(len(devices))

    for col, dev, status in zip(ctrl_cols, devices, statuses):
        with col:
            st.markdown(f"### {dev['name']}")
            disabled = not status["online"]

            if disabled:
                st.warning("Thiết bị offline")

            # Ping
            if st.button("🏓 Ping", key=f"ping_{dev['name']}", use_container_width=True, disabled=disabled):
                s = check_status(dev)
                if s["online"]:
                    add_log(f"PING {dev['name']}: {s['latency_ms']} ms")
                    st.success(f"Pong! {s['latency_ms']} ms")
                else:
                    add_log(f"PING {dev['name']}: FAILED — {s.get('error')}")
                    st.error(f"Không phản hồi: {s.get('error')}")

            # GET /status
            if st.button("📥 GET /status", key=f"get_status_{dev['name']}",
                         use_container_width=True, disabled=disabled):
                res = send_request(dev, "GET", "status")
                add_log(f"GET /status {dev['name']}: {res.get('status', res.get('error'))}")
                if res["ok"]:
                    st.code(res["body"], language="json")
                else:
                    st.error(res["error"])

            # GET /info
            if st.button("ℹ️ GET /info", key=f"get_info_{dev['name']}",
                         use_container_width=True, disabled=disabled):
                res = send_request(dev, "GET", "info")
                add_log(f"GET /info {dev['name']}: {res.get('status', res.get('error'))}")
                if res["ok"]:
                    st.code(res["body"], language="json")
                else:
                    st.error(res["error"])

            # Restart
            if st.button("🔁 POST /restart", key=f"restart_{dev['name']}",
                         use_container_width=True, type="primary", disabled=disabled):
                res = send_request(dev, "POST", "restart")
                add_log(f"POST /restart {dev['name']}: {res.get('status', res.get('error'))}")
                if res["ok"]:
                    st.success(f"Đã gửi lệnh restart ({res['status']})")
                else:
                    st.error(res["error"])

# ── Tab 2: Custom request ─────────────────────────────────────────────────────
with tab_request:
    st.subheader("Gửi HTTP Request tuỳ chỉnh")

    r_col1, r_col2 = st.columns([1, 2])
    with r_col1:
        target_name = st.selectbox("Thiết bị", [d["name"] for d in devices])
        method = st.selectbox("Method", ["GET", "POST", "PUT", "DELETE", "PATCH"])
    with r_col2:
        path = st.text_input("Path", placeholder="api/command", value="")

    payload_str = ""
    if method in ("POST", "PUT", "PATCH"):
        payload_str = st.text_area("JSON Body (tuỳ chọn)", height=100,
                                   placeholder='{"key": "value"}')

    if st.button("🚀 Gửi request", type="primary"):
        target = next(d for d in devices if d["name"] == target_name)
        payload = None
        if payload_str.strip():
            import json
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError as e:
                st.error(f"JSON không hợp lệ: {e}")
                st.stop()

        with st.spinner("Đang gửi…"):
            res = send_request(target, method, path, payload)

        url_shown = build_url(target, path)
        add_log(f"{method} {url_shown} → {res.get('status', res.get('error'))}")

        if res["ok"]:
            st.success(f"HTTP {res['status']}")
            st.code(res["body"], language="json")
        else:
            st.error(f"Lỗi: {res['error']}")

# ── Tab 3: Log ────────────────────────────────────────────────────────────────
with tab_log:
    st.subheader("📋 Nhật ký hoạt động")
    if st.button("🗑️ Xóa nhật ký"):
        st.session_state.log = []
        st.rerun()
    if st.session_state.log:
        st.code("\n".join(st.session_state.log), language="text")
    else:
        st.info("Chưa có hoạt động nào được ghi lại.")

# ── Auto refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
