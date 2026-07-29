# QL-800 receiving label agent

Local agent (runs on the **Trig Mini**, where the QL-800 is USB). Watches Supabase
`ops_receiving` for `label_printed = false`, prints a 62 mm label (client + order,
SKU + vendor, storage location, QR → the item in the delivery app), and marks it printed.
Labels carry **no pricing** — retail-safe.

## One-time setup

**1. Printer (macOS)**
- Install the Brother **QL-800** driver: support.brother.com → QL-800 → Downloads → macOS.
- Plug in the USB cable, load the **DK-2205** (62 mm continuous) roll.
- Add it: System Settings → Printers & Scanners → +. Then note the exact queue name:
  ```
  lpstat -p
  ```
  (e.g. `Brother_QL_800`). Print a macOS test page to confirm it works before wiring the agent.

**2. Agent**
```
cd "/Users/trig/Desktop/Trig-Mini-Handoff/repos/trig-ops/printer"
pip3 install -r requirements.txt
cp .env.example .env
```
Edit `.env`:
- `SUPABASE_SERVICE_KEY` = Supabase → Settings → API → **service_role** key (this stays local; `.env` is gitignored — never commit it).
- `PRINTER_QUEUE` = the exact name from `lpstat -p`.
- Adjust `LABEL_H_MM` if you want a longer/shorter cut; set `LP_MEDIA` only if your driver needs an explicit media size.

**3. Test**
```
./run.sh
```
Leave it running, then check an item in at trig-delivery.netlify.app → a label should print within ~8s. Errors print to the terminal and land in `ops_receiving.label_error`.

**4. Run it always (auto-start)**
```
cp com.trigmodern.labelagent.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.trigmodern.labelagent.plist
```
Logs: `/tmp/trig-labelagent.out.log` and `.err.log`. To stop: `launchctl unload ~/Library/LaunchAgents/com.trigmodern.labelagent.plist`.

## How it fits
- Check-in (app or scan) writes `ops_receiving`; the agent reacts off `label_printed = false`.
- The QR encodes `trig-delivery.netlify.app/?receiving=<id>` (deep-link into the app is a follow-up).
- Web-push on check-in is the next piece (push_subscriptions + a notifier); separate from printing.
