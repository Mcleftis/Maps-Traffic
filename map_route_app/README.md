# Route Planner — No Real-Time Traffic

A Google Maps integration that calculates and displays a driving route while
**strictly ignoring real-time traffic**.

## Why you couldn't find "the" example

Traffic-free routing is not a separate Google product or library — it is a
**routing preference** on the [Routes API](https://developers.google.com/maps/documentation/routes):

```json
{ "routingPreference": "TRAFFIC_UNAWARE" }
```

| Value | Behaviour |
|---|---|
| `TRAFFIC_UNAWARE` | **Static road data only — live traffic is never used** (this project) |
| `TRAFFIC_AWARE` | Uses live traffic |
| `TRAFFIC_AWARE_OPTIMAL` | Uses live traffic, highest quality |

Two extra details make it "strict":

1. **No `departureTime` is ever sent** — a departure time is what anchors a
   traffic snapshot. (In the *legacy* Directions API, omitting
   `departure_time` is the *only* way to disable traffic.)
2. **No `TrafficLayer` is added to the map**, so live-traffic colours are
   never even displayed.

## What's here

| File | What it is |
|---|---|
| `index.html` | Complete, self-contained web app (works on mobile browsers): map, origin/destination autocomplete, route drawn as a polyline, distance + duration shown with a "traffic ignored" badge. |
| `route_no_traffic.py` | Command-line version: geocodes two addresses and prints distance/duration computed with `TRAFFIC_UNAWARE`. |

## Setup (once)

1. Go to [Google Cloud Console](https://console.cloud.google.com/), create a
   project, and enable billing (Google gives a large free monthly quota).
2. Enable these APIs (**APIs & Services → Library**):
   - **Maps JavaScript API** (web app)
   - **Routes API** (both)
   - **Places API** (web app autocomplete)
   - **Geocoding API** (Python script)
3. Create an API key (**APIs & Services → Credentials**).

## Run the web app

1. Replace `YOUR_GOOGLE_MAPS_API_KEY` in `index.html` — it appears **twice**
   (the `API_KEY` constant and the `<script src=...>` loader at the bottom).
2. Serve it (the Maps JS API doesn't like `file://` URLs):

   ```bash
   cd map_route_app
   python3 -m http.server 8000
   ```

3. Open <http://localhost:8000> — on your phone, use your computer's LAN IP,
   e.g. `http://192.168.1.10:8000`.

## Run the Python script

```bash
pip install requests
export GOOGLE_MAPS_API_KEY="your-key"
python3 route_no_traffic.py "Syntagma Square, Athens" "Thessaloniki"
```

Example output:

```
Distance : 502.3 km
Duration : 4 h 52 min  (traffic ignored)
Polyline : e~sfFgyqgCn@qBlAyD...
```
