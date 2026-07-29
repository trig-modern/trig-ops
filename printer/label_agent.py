#!/usr/bin/env python3
"""
Trig Ops — QL-800 receiving label agent.

Runs LOCALLY on the Trig Mini (the QL-800 is USB on this machine). Watches
Supabase `ops_receiving` for label_printed = false, renders a 62mm label
(DK-2205 continuous), and prints it via brother_ql raster sent as a RAW CUPS
job (bypasses the flaky Brother image filter; uses the working USB path).
Retail-safe: labels carry no pricing.

Config comes from environment / a local .env (NEVER commit the service key).
"""
import os, sys, time, json, tempfile, subprocess, datetime, urllib.request, urllib.parse

def env(k, d=None): return os.environ.get(k, d)

SUPABASE_URL  = env("SUPABASE_URL", "https://xyfogedlowneaevmjkci.supabase.co").rstrip("/")
SERVICE_KEY   = env("SUPABASE_SERVICE_KEY")
PRINTER_QUEUE = env("PRINTER_QUEUE", "Brother_QL_800")
POLL_SECONDS  = int(env("POLL_SECONDS", "8"))
QL_LABEL      = env("QL_LABEL", "62")        # brother_ql label id: 62mm continuous
PRINT_W       = int(env("PRINT_W", "696"))   # printable dots across a 62mm tape @300dpi
LABEL_H_PX    = int(env("LABEL_H_PX", "480"))# label length in dots (~40mm); grows if needed
APP_BASE      = env("DELIVERY_APP_URL", "https://trig-delivery.netlify.app")

if not SERVICE_KEY:
    sys.exit("Set SUPABASE_SERVICE_KEY in .env (Supabase secret / service_role, local only).")

try:
    from PIL import Image, ImageDraw, ImageFont
    import qrcode
    from brother_ql.conversion import convert
    from brother_ql.raster import BrotherQLRaster
except ImportError as e:
    sys.exit(f"Missing dep ({e}). Run: pip3 install -r requirements.txt")

def _font(sz, bold=False):
    for p in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf"]:
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()

# ---- Supabase REST ----
def sb(method, path, body=None, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params: url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=(json.dumps(body).encode() if body is not None else None), method=method)
    req.add_header("apikey", SERVICE_KEY); req.add_header("Authorization", f"Bearer {SERVICE_KEY}")
    req.add_header("Content-Type", "application/json")
    if method in ("PATCH","POST"): req.add_header("Prefer", "return=representation")
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode(); return json.loads(raw) if raw else []

def fetch_queue():
    return sb("GET", "ops_receiving", params={
        "label_printed": "eq.false",
        "select": "id,description,sku,vendor,order_ref,client,storage_location,condition,received_at",
        "order": "received_at.asc", "limit": "20"})

def mark(id_, ok, err=None):
    sb("PATCH", "ops_receiving",
       body={"label_printed": ok,
             "label_printed_at": (datetime.datetime.utcnow().isoformat()+"Z") if ok else None,
             "label_error": err},
       params={"id": f"eq.{id_}"})

# ---- render label as a PRINT_W-wide PIL image ----
def render(row):
    img = Image.new("RGB", (PRINT_W, LABEL_H_PX), "white")
    d = ImageDraw.Draw(img)
    pad, qr = 14, 150
    q = qrcode.QRCode(box_size=5, border=1)
    q.add_data(f"{APP_BASE}/?receiving={row['id']}"); q.make(fit=True)
    img.paste(q.make_image(fill_color="black", back_color="white").resize((qr, qr)), (PRINT_W - qr - pad, pad))
    x, y, tw = pad, pad, PRINT_W - qr - pad*3
    def line(txt, sz, bold=False, gap=6):
        nonlocal y
        f = _font(sz, bold); words = str(txt).split(); cur = ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) > tw and cur:
                d.text((x, y), cur, font=f, fill="black"); y += sz + gap; cur = w
            else: cur = t
        if cur: d.text((x, y), cur, font=f, fill="black"); y += sz + gap
    line(row.get("client") or "(no client)", 46, bold=True)
    if row.get("order_ref"): line(f"Order {row['order_ref']}", 34)
    item = " · ".join([v for v in [row.get("vendor"), row.get("sku") and ("SKU "+row["sku"])] if v]) or (row.get("description") or "")
    line(item, 32)
    if row.get("description") and (row.get("vendor") or row.get("sku")): line(row["description"], 28)
    d.text((x, LABEL_H_PX - 66), f"LOC: {row.get('storage_location') or '—'}", font=_font(44, bold=True), fill="black")
    if (row.get("condition") or "good") != "good":
        d.text((PRINT_W - qr - pad, LABEL_H_PX - 40), (row["condition"] or "").upper(), font=_font(30, bold=True), fill="black")
    return img

def print_label(img):
    qlr = BrotherQLRaster("QL-800"); qlr.exception_on_warning = False
    convert(qlr, [img], label=QL_LABEL, rotate="auto", dither=False, compress=False, red=False, cut=True)
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(qlr.data); binp = f.name
    r = subprocess.run(["lp", "-d", PRINTER_QUEUE, "-o", "raw", binp], capture_output=True, text=True)
    os.unlink(binp)
    if r.returncode != 0: raise RuntimeError(r.stderr.strip() or "lp raw failed")
    return r.stdout.strip()

def main():
    print(f"[label_agent] brother_ql raw → {PRINTER_QUEUE}, label={QL_LABEL} width={PRINT_W}dots")
    while True:
        try:
            for row in fetch_queue():
                try:
                    job = print_label(render(row)); mark(row["id"], True)
                    print(f"[printed] #{row['id']} {row.get('client') or ''} {job}")
                except Exception as e:
                    mark(row["id"], False, str(e)[:300]); print(f"[ERROR] #{row['id']}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[poll error] {e}", file=sys.stderr)
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
