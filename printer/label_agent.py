#!/usr/bin/env python3
"""
Trig Ops — QL-800 receiving label agent.

Runs LOCALLY on the Trig Mini (the QL-800 is USB on this machine). Watches
Supabase `ops_receiving` for rows with label_printed = false, renders a 62mm
label (DK-2205 continuous), prints it to the QL-800 via CUPS `lp`, and marks
the row printed. Retail-safe: labels carry no pricing.

Config comes from environment / a local .env (NEVER commit the service key).
See .env.example + README.md.
"""
import os, sys, time, json, tempfile, subprocess, urllib.request, urllib.parse, urllib.error

# ---- config ----
def env(k, d=None):
    return os.environ.get(k, d)

SUPABASE_URL   = env("SUPABASE_URL", "https://xyfogedlowneaevmjkci.supabase.co").rstrip("/")
SERVICE_KEY    = env("SUPABASE_SERVICE_KEY")          # service_role — local only, gitignored
PRINTER_QUEUE  = env("PRINTER_QUEUE", "Brother_QL_800")
POLL_SECONDS   = int(env("POLL_SECONDS", "8"))
LABEL_W_MM     = float(env("LABEL_W_MM", "62"))       # DK-2205 continuous width
LABEL_H_MM     = float(env("LABEL_H_MM", "45"))       # length we cut to
DPI            = int(env("DPI", "300"))
APP_BASE       = env("DELIVERY_APP_URL", "https://trig-delivery.netlify.app")
LP_MEDIA       = env("LP_MEDIA", "")                  # e.g. "Custom.62x45mm"; leave blank to omit

MM = lambda mm: int(round(mm / 25.4 * DPI))
W, H = MM(LABEL_W_MM), MM(LABEL_H_MM)

if not SERVICE_KEY:
    sys.exit("Set SUPABASE_SERVICE_KEY in the environment / .env (service_role, local only).")

# ---- deps (Pillow + qrcode) ----
try:
    from PIL import Image, ImageDraw, ImageFont
    import qrcode
except ImportError:
    sys.exit("Missing deps. Run: pip3 install -r requirements.txt")

def _font(sz, bold=False):
    for p in (["/System/Library/Fonts/SFNSDisplay.ttf"] if False else []) + [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ]:
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()

# ---- Supabase REST ----
def sb(method, path, body=None, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params: url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("apikey", SERVICE_KEY)
    req.add_header("Authorization", f"Bearer {SERVICE_KEY}")
    req.add_header("Content-Type", "application/json")
    if method in ("PATCH", "POST"): req.add_header("Prefer", "return=representation")
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else []

def fetch_queue():
    return sb("GET", "ops_receiving", params={
        "label_printed": "eq.false",
        "select": "id,description,sku,vendor,order_ref,client,storage_location,condition,received_at",
        "order": "received_at.asc", "limit": "20",
    })

def mark(id_, ok, err=None):
    sb("PATCH", "ops_receiving", body={
        "label_printed": ok, "label_printed_at": ("now" and __import__("datetime").datetime.utcnow().isoformat()+"Z") if ok else None,
        "label_error": err,
    }, params={"id": f"eq.{id_}"})

# ---- render ----
def render(row, path):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    pad = MM(3)
    qr_px = MM(20)
    # QR -> open this receiving item in the delivery app
    qr = qrcode.QRCode(box_size=6, border=1)
    qr.add_data(f"{APP_BASE}/?receiving={row['id']}")
    qr.make(fit=True)
    qimg = qr.make_image(fill_color="black", back_color="white").resize((qr_px, qr_px))
    img.paste(qimg, (W - qr_px - pad, pad))

    x = pad; y = pad; tw = W - qr_px - pad*3
    def line(txt, sz, bold=False, gap=4):
        nonlocal y
        f = _font(sz, bold)
        # simple wrap
        words = str(txt).split(); cur = ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) > tw and cur:
                d.text((x, y), cur, font=f, fill="black"); y += sz + gap; cur = w
            else: cur = t
        if cur: d.text((x, y), cur, font=f, fill="black"); y += sz + gap

    client = row.get("client") or "(no client)"
    order  = row.get("order_ref")
    line(client, MM(4.5), bold=True)
    if order: line(f"Order {order}", MM(3))
    itemline = " · ".join([v for v in [row.get("vendor"), row.get("sku") and ("SKU "+row["sku"])] if v]) or (row.get("description") or "")
    line(itemline, MM(3.2))
    if row.get("description") and (row.get("vendor") or row.get("sku")):
        line(row["description"], MM(2.8))
    loc = row.get("storage_location")
    d.text((x, H - MM(7)), f"LOC: {loc or '—'}", font=_font(MM(4), bold=True), fill="black")
    if (row.get("condition") or "good") != "good":
        d.text((W - qr_px - pad, H - MM(7)), (row["condition"] or "").upper(), font=_font(MM(3), bold=True), fill="black")
    img.save(path, dpi=(DPI, DPI))

def print_label(path):
    cmd = ["lp", "-d", PRINTER_QUEUE]
    if LP_MEDIA: cmd += ["-o", f"media={LP_MEDIA}"]
    cmd += ["-o", "fit-to-page", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "lp failed")
    return r.stdout.strip()

def main():
    print(f"[label_agent] watching ops_receiving, printer={PRINTER_QUEUE}, label={LABEL_W_MM}x{LABEL_H_MM}mm @ {DPI}dpi")
    while True:
        try:
            for row in fetch_queue():
                try:
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                        render(row, f.name)
                    job = print_label(f.name)
                    mark(row["id"], True)
                    print(f"[printed] #{row['id']} {row.get('client') or ''} {job}")
                except Exception as e:
                    mark(row["id"], False, str(e)[:300])
                    print(f"[ERROR] #{row['id']}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[poll error] {e}", file=sys.stderr)
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
