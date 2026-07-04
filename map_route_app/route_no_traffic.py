#!/usr/bin/env python3
"""Compute a driving route with Google's Routes API, ignoring real-time traffic.

The whole trick is one field:

    "routingPreference": "TRAFFIC_UNAWARE"

TRAFFIC_UNAWARE tells Google to compute the route from static road data
only and to completely ignore live traffic. We also never send a
``departureTime``, which is what would otherwise anchor a traffic
snapshot (this is also how you disable traffic in the legacy
Directions API: just omit departure_time).

Usage:
    export GOOGLE_MAPS_API_KEY="your-key"
    python route_no_traffic.py "Syntagma Square, Athens" "Thessaloniki"

Requires: requests  (pip install requests)
The API key needs "Routes API" and "Geocoding API" enabled in
Google Cloud Console.
"""

import os
import sys

import requests

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def geocode(address: str, api_key: str) -> dict:
    """Turn a free-text address into {"latitude": .., "longitude": ..}."""
    resp = requests.get(
        GEOCODE_URL, params={"address": address, "key": api_key}, timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data["status"] != "OK":
        raise SystemExit(f"Geocoding failed for {address!r}: {data['status']}")
    loc = data["results"][0]["geometry"]["location"]
    return {"latitude": loc["lat"], "longitude": loc["lng"]}


def compute_route_no_traffic(origin: dict, destination: dict, api_key: str) -> dict:
    body = {
        "origin": {"location": {"latLng": origin}},
        "destination": {"location": {"latLng": destination}},
        "travelMode": "DRIVE",
        # THE key setting: never use real-time traffic.
        "routingPreference": "TRAFFIC_UNAWARE",
        # Deliberately NO "departureTime" here.
        "units": "METRIC",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        # Mandatory for the Routes API: ask only for the fields you need.
        "X-Goog-FieldMask": (
            "routes.duration,routes.distanceMeters,"
            "routes.polyline.encodedPolyline"
        ),
    }
    resp = requests.post(ROUTES_URL, json=body, headers=headers, timeout=30)
    if not resp.ok:
        raise SystemExit(f"Routes API error {resp.status_code}: {resp.text}")
    routes = resp.json().get("routes")
    if not routes:
        raise SystemExit("No route found between these points.")
    return routes[0]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} <origin> <destination>")

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise SystemExit("Set the GOOGLE_MAPS_API_KEY environment variable first.")

    origin = geocode(sys.argv[1], api_key)
    destination = geocode(sys.argv[2], api_key)
    route = compute_route_no_traffic(origin, destination, api_key)

    km = route["distanceMeters"] / 1000
    seconds = int(route["duration"].rstrip("s"))
    hours, minutes = divmod(round(seconds / 60), 60)

    print(f"Distance : {km:.1f} km")
    print(f"Duration : {hours} h {minutes} min  (traffic ignored)")
    print(f"Polyline : {route['polyline']['encodedPolyline'][:80]}...")


if __name__ == "__main__":
    main()
