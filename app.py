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
    {"name": "Device 1", "ip": "192.168.137.175", "port": 80},
    {"name": "Device 2", "ip": "192.168.1.169", "port": 80},
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


def get_api(device: dict, path: str, timeout: float = 4.0) -> dict:
    """Shortcut for GET requests, returns text response."""
    res = send_request(device, "GET", path)
    res["text"] = res.get("body", "")
    return res


def rssi_label(val: str) -> str:
    try:
        v = int(val)
        if v >= -55:  return f"Xuất sắc ({v} dBm)"
        if v >= -67:  return f"Tốt ({v} dBm)"
        if v >= -78:  return f"Khá ({v} dBm)"
        if v >= -85:  return f"Yếu ({v} dBm)"
        return f"Không ổn định ({v} dBm)"
    except Exception:
        return val


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

# ── Tab 1: AI-on-the-Edge controls ───────────────────────────────────────────
with tab_control:
    st.subheader("Điều khiển thiết bị AI on the Edge")
    ctrl_cols = st.columns(len(devices))

    for col, dev, status in zip(ctrl_cols, devices, statuses):
        with col:
            st.markdown(f"### {dev['name']}")
            disabled = not status["online"]

            if disabled:
                st.warning("Thiết bị offline")

            # ── Nhận dạng ────────────────────────────────────────────────────
            st.markdown("**📸 Nhận dạng**")

            if st.button("▶ Bắt đầu vòng nhận dạng", key=f"flow_{dev['name']}",
                         use_container_width=True, type="primary", disabled=disabled):
                res = get_api(dev, "flow_start")
                add_log(f"flow_start {dev['name']}: {res.get('text') or res.get('error')}")
                st.success(res["text"]) if res["ok"] else st.error(res["error"])

            if st.button("📊 Xem giá trị hiện tại", key=f"val_{dev['name']}",
                         use_container_width=True, disabled=disabled):
                for label, t in [("Giá trị", "value"), ("Thô", "raw"),
                                  ("Trước", "prevalue"), ("Trạng thái", "error")]:
                    r = get_api(dev, f"value?all=true&type={t}")
                    v = r["text"] if r["ok"] else f"⚠️ {r['error']}"
                    st.text(f"{label}: {v}")
                add_log(f"Đọc giá trị {dev['name']}")

            if st.button("🖼 Tải ảnh ROI", key=f"img_{dev['name']}",
                         use_container_width=True, disabled=disabled):
                img_url = build_url(dev, f"img_tmp/alg_roi.jpg?t={int(time.time())}")
                st.image(img_url, caption="alg_roi.jpg", use_container_width=True)
                add_log(f"Tải ảnh ROI {dev['name']}")

            st.divider()

            # ── Giá trị trước (Previous Value) ───────────────────────────────
            st.markdown("**🔢 Đặt Previous Value**")

            numbers_res = get_api(dev, "value?all=true&type=raw") if not disabled else {"ok": False}
            if numbers_res["ok"]:
                lines = [l.split("\t") for l in numbers_res["text"].split("\r") if "\t" in l]
                number_ids = [l[0] for l in lines if l] or ["main"]
            else:
                number_ids = ["main"]

            sel_num = st.selectbox("Meter ID", number_ids,
                                   key=f"num_{dev['name']}", disabled=disabled)
            new_val = st.text_input("Giá trị mới", placeholder="e.g. 12345.678",
                                    key=f"preval_{dev['name']}", disabled=disabled)

            pc1, pc2 = st.columns(2)
            if pc1.button("✅ Đặt", key=f"setpre_{dev['name']}",
                          use_container_width=True, disabled=disabled or not new_val):
                res = get_api(dev, f"setPreValue?value={new_val}&numbers={sel_num}")
                add_log(f"setPreValue {dev['name']} → {new_val}: {res.get('text') or res.get('error')}")
                st.success(res["text"]) if res["ok"] else st.error(res["error"])

            if pc2.button("🔄 Reset", key=f"resetpre_{dev['name']}",
                          use_container_width=True, disabled=disabled):
                res = get_api(dev, f"setPreValue?numbers={sel_num}")
                add_log(f"resetPreValue {dev['name']}: {res.get('text') or res.get('error')}")
                st.success("Đã reset") if res["ok"] else st.error(res["error"])

            st.divider()

            # ── Hệ thống ──────────────────────────────────────────────────────
            st.markdown("**⚙️ Hệ thống**")

            if st.button("📋 Xem trạng thái flow", key=f"sf_{dev['name']}",
                         use_container_width=True, disabled=disabled):
                res = get_api(dev, "statusflow")
                add_log(f"statusflow {dev['name']}: {res.get('text') or res.get('error')}")
                st.info(res["text"]) if res["ok"] else st.error(res["error"])

            if st.button("🌡 CPU / WiFi / Uptime", key=f"sysinfo_{dev['name']}",
                         use_container_width=True, disabled=disabled):
                for label, path in [("CPU Temp", "cpu_temperature"),
                                     ("WiFi", "rssi"),
                                     ("Uptime", "uptime"),
                                     ("Date", "date"),
                                     ("Round", "info?type=Round"),
                                     ("Firmware", "info?type=FirmwareVersion")]:
                    r = get_api(dev, path)
                    val = rssi_label(r["text"]) if path == "rssi" else (r["text"] if r["ok"] else f"⚠️ {r['error']}")
                    st.text(f"{label}: {val}")
                add_log(f"Xem sysinfo {dev['name']}")

            if st.button("📤 Gửi lại HA Discovery", key=f"mqtt_{dev['name']}",
                         use_container_width=True, disabled=disabled):
                res = get_api(dev, "mqtt_publish_discovery")
                add_log(f"mqtt_discovery {dev['name']}: {res.get('text') or res.get('error')}")
                st.success(res["text"]) if res["ok"] else st.error(res["error"])

            if st.button("🔁 Reboot", key=f"reboot_{dev['name']}",
                         use_container_width=True, disabled=disabled):
                res = get_api(dev, "reboot")
                add_log(f"reboot {dev['name']}: {res.get('text') or res.get('error')}")
                st.info("Thiết bị đang khởi động lại…") if res["ok"] else st.error(res["error"])

            st.divider()

            # ── Liên kết nhanh ────────────────────────────────────────────────
            st.markdown("**🔗 Liên kết nhanh**")
            st.link_button("🌐 Web UI",      build_url(dev),                  use_container_width=True)
            st.link_button("📁 File Server", build_url(dev, "fileserver/"),   use_container_width=True)
            st.link_button("📄 Log file",    build_url(dev, "logfileact"),    use_container_width=True)
            st.link_button("📊 Data file",   build_url(dev, "datafileact"),   use_container_width=True)
            st.link_button("▶ Livestream",   build_url(dev, "stream"),        use_container_width=True)

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
