"""Lambda store — γράφει τα alerts του EventBridge στο live store.

Είναι ο κρίκος που έλειπε: το ingest δημοσιεύει στο EventBridge, το query
διαβάζει από το DynamoDB, αλλά κανείς δεν έγραφε ενδιάμεσα.

Το κλειδί ακολουθεί ό,τι περιμένει το query.py:
    PK  geohash5              — το κελί ~5km
    SK  occurredAt#eventId    — χρονολογική σειρά μέσα στο κελί
"""

import os
from decimal import Decimal

TABLE_NAME = os.environ.get("TABLE_NAME", "maps-traffic-alerts-dev")

_table = None


def _get_table():
    """Lazy + cached: ένα client ανά container, όχι ανά invocation."""
    global _table
    if _table is None:
        import boto3
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


def to_item(detail: dict) -> dict:
    """Canonical event -> DynamoDB item."""
    location = detail["location"]
    alert = detail["alert"]

    item = {
        "geohash5": location["geohash5"],
        "sortKey": f'{detail["occurredAt"]}#{detail["eventId"]}',
        "geohash7": location.get("geohash7"),
        # Το DynamoDB δεν δέχεται float — μόνο Decimal.
        "lat": Decimal(str(location["lat"])),
        "lon": Decimal(str(location["lon"])),
        "alertType": alert.get("type"),
        "severity": alert.get("severity"),
        "confidence": Decimal(str(alert.get("confidence", 0))),
        "text": alert.get("text"),
        "source": detail.get("provenance", {}).get("source"),
    }

    # Το TTL σβήνει μόνο του τα παλιά alerts· χωρίς αυτό ο πίνακας μεγαλώνει
    # για πάντα. Λείπει μόνο αν το event δεν πέρασε από το to_canonical().
    expires_at = detail.get("ttl", {}).get("expiresAt")
    if expires_at is not None:
        item["expiresAt"] = int(expires_at)

    return {k: v for k, v in item.items() if v is not None}


def handler(event, context):
    """EventBridge rule target: ένα event ανά invocation."""
    detail = event.get("detail") or {}

    if not detail.get("location", {}).get("geohash5") or not detail.get("eventId"):
        # Χωρίς κλειδί δεν γράφεται τίποτα. Σηκώνουμε εξαίρεση ώστε το
        # EventBridge να ξαναπροσπαθήσει και τελικά να το στείλει στο DLQ,
        # αντί να το καταπιούμε σιωπηλά.
        raise ValueError(f"event χωρίς geohash5/eventId: {detail.get('eventId')}")

    _get_table().put_item(Item=to_item(detail))
    return {"stored": detail["eventId"]}
