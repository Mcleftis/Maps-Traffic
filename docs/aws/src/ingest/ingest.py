"""Lambda ingest — το σύγχρονο όριο του συστήματος.

Επικυρώνει, κανονικοποιεί σε canonical event, δημοσιεύει στο EventBridge.
Τίποτα άλλο: ό,τι είναι αργό ή μπορεί να αποτύχει γίνεται async μετά.
Στόχος απόκρισης < 100ms.

Δέχεται ΚΑΙ το σημερινό format του relay/worker.js ({id,t,g,m,lat,lon,ico,label}),
ώστε το Android app να μη χρειαστεί άμεση αλλαγή.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone

import geohash
from normalize import classify, severity_of

EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "maps-traffic-dev")
DEVICE_SALT = os.environ.get("DEVICE_SALT", "dev-salt-χωρίς-σημασία")
TTL_HOURS = int(os.environ.get("TTL_HOURS", "6"))
SCHEMA_VERSION = "1.0"

# Όρια Ελλάδας — απορρίπτει προφανή σφάλματα GPS πριν μολύνουν το data lake.
LAT_MIN, LAT_MAX = 34.5, 42.0
LON_MIN, LON_MAX = 19.0, 30.0

_ULID_CHARS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class ValidationError(ValueError):
    """Το event δεν πληροί το συμβόλαιο. Απαντάμε 400, δεν το προωθούμε."""


def _ulid(now_ms: int = None) -> str:
    """ULID: 48 bits χρόνου + 80 bits τυχαιότητας, σε Crockford base32.

    Lexicographically sortable κατά χρόνο — γι' αυτό δουλεύει ως DynamoDB
    sort key χωρίς δεύτερο index, σε αντίθεση με το UUIDv4.
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")
    value = (now_ms << 80) | rand
    return "".join(_ULID_CHARS[(value >> (5 * i)) & 31] for i in range(25, -1, -1))


def _device_hash(raw: str) -> str:
    """Salted hash. Το salt εναλλάσσεται μηνιαία (docs/aws/05-security.md).

    Σταθερό αναγνωριστικό + δεδομένα θέσης = παρακολούθηση, ανεξάρτητα από το
    αν το ονομάζουμε ψευδωνυμοποιημένο.
    """
    if not raw:
        return ""
    return hashlib.sha256(f"{DEVICE_SALT}:{raw}".encode("utf-8")).hexdigest()[:32]


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def to_canonical(item: dict, now_ms: int = None) -> dict:
    """Adapter: relay format ή canonical -> canonical event.

    Δες τον πίνακα αντιστοίχισης στο docs/aws/02-event-schema.md.
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)

    # Ήδη canonical; πέρασέ το ως έχει (θα το επικυρώσει το validate()).
    if "schemaVersion" in item:
        return item

    lat, lon = item.get("lat"), item.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        raise ValidationError("λείπουν ή δεν είναι αριθμοί τα lat/lon")
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        raise ValidationError(f"συντεταγμένες εκτός Ελλάδας: {lat},{lon}")

    text = str(item.get("m") or "")[:500]
    label = str(item.get("label") or "")
    alert_type, confidence = classify(text, label)

    occurred_ms = item.get("t") if isinstance(item.get("t"), (int, float)) else now_ms

    return {
        "schemaVersion": SCHEMA_VERSION,
        "eventId": _ulid(now_ms),
        "eventType": "traffic.alert.created",
        "occurredAt": _iso(int(occurred_ms)),
        "ingestedAt": _iso(now_ms),
        "alert": {
            "type": alert_type,
            "severity": severity_of(text, alert_type),
            "confidence": confidence,
            "text": text,
            "language": "el",
        },
        "location": {
            "lat": float(lat),
            "lon": float(lon),
            "geohash5": geohash.encode(lat, lon, 5),
            "geohash7": geohash.encode(lat, lon, 7),
        },
        "provenance": {
            "source": "VIBER_GROUP" if item.get("g") else "USER_REPORT",
            "sourceRef": str(item.get("g") or "")[:120],
            "sourceId": str(item.get("id") or "")[:120],
            "inputType": "TEXT",
            "producer": str(item.get("producer") or "relay-adapter"),
            "deviceHash": _device_hash(str(item.get("device") or "")),
            "enrichedBy": [],
            # Το `ico` του relay ΔΕΝ μεταφέρεται: είναι παρουσίαση, ανήκει στο UI.
        },
        "ttl": {"expiresAt": int(now_ms / 1000) + TTL_HOURS * 3600},
    }


def validate(event: dict) -> None:
    """Ελάχιστο συμβόλαιο. Το πλήρες JSON Schema είναι στο iac/event-schema.json."""
    for field in ("schemaVersion", "eventId", "eventType", "occurredAt",
                  "alert", "location", "provenance"):
        if field not in event:
            raise ValidationError(f"λείπει το υποχρεωτικό πεδίο: {field}")

    loc = event["location"]
    if not (LAT_MIN <= loc["lat"] <= LAT_MAX and LON_MIN <= loc["lon"] <= LON_MAX):
        raise ValidationError("συντεταγμένες εκτός Ελλάδας")
    if len(loc.get("geohash5", "")) != 5:
        raise ValidationError("μη έγκυρο geohash5")
    if not 0 <= event["alert"]["confidence"] <= 1:
        raise ValidationError("confidence εκτός [0,1]")


def _entries(events: list) -> list:
    return [{
        "EventBusName": EVENT_BUS_NAME,
        "Source": "maps-traffic.ingest",
        "DetailType": e["eventType"],
        "Detail": json.dumps(e, ensure_ascii=False),
    } for e in events]


def publish(events: list) -> int:
    """PutEvents σε παρτίδες των 10 — σκληρό όριο του EventBridge API."""
    if not events:
        return 0

    import boto3                                   # lazy: κρατά το cold start χαμηλά
    client = boto3.client("events")

    failed = 0
    for i in range(0, len(events), 10):
        response = client.put_events(Entries=_entries(events[i:i + 10]))
        failed += response.get("FailedEntryCount", 0)

    if failed:
        # Μερική αποτυχία δεν είναι εξαίρεση στο PutEvents — πρέπει να την
        # ελέγξεις ρητά, αλλιώς χάνονται events σιωπηλά.
        raise RuntimeError(f"το EventBridge απέρριψε {failed} events")

    return len(events)


def handler(event, context):
    """API Gateway HTTP API (payload format 2.0) -> EventBridge."""
    try:
        body = json.loads(event.get("body") or "[]")
    except json.JSONDecodeError:
        return _response(400, {"error": "μη έγκυρο JSON"})

    items = body if isinstance(body, list) else [body]
    if len(items) > 100:
        return _response(413, {"error": "πάνω από 100 events ανά αίτημα"})

    accepted, rejected = [], []
    for item in items:
        try:
            canonical = to_canonical(item)
            validate(canonical)
            accepted.append(canonical)
        except (ValidationError, KeyError, TypeError) as exc:
            rejected.append(str(exc))

    published = publish(accepted)

    # 202: το δεχτήκαμε, η επεξεργασία συνεχίζεται ασύγχρονα.
    return _response(202, {
        "accepted": published,
        "rejected": len(rejected),
        "errors": rejected[:10],
    })


def _response(status: int, payload: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(payload, ensure_ascii=False),
    }
