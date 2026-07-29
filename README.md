# trig-ops

Internal Trig Modern ops apps (single-file, static; Supabase-backed, magic-link auth). Deploy FROM this repo, not Netlify-Drop-only.

## Apps
- **ops-dashboard/** — team order-pipeline board. Live: https://trig-ops-dashboard.netlify.app
  - `index.html` — the app. `vendor-doc-autofiler.gs` — Apps Script that files vendor PDFs to Drive.
- **delivery-dashboard/** — Jeff (delivery mgr): receiving check-in, delivery routes/stops, tasks. Live: https://trig-delivery.netlify.app

## Backend
Shared Supabase project `xyfogedlowneaevmjkci`. Tables: ops_signals, ops_users, ops_briefs, ops_dashboard_prefs, ops_receiving, ops_delivery_routes, ops_route_stops, ops_delivery_tasks, agent_comms. Only the browser-safe **anon/publishable** key is in the client (RLS-gated). No service_role, no net/trade pricing in this repo.

## Auth-URL gotcha
Each Netlify URL must be in Supabase → Authentication → URL Configuration or magic links won't return.
