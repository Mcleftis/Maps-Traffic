"""Lambda store — γράφει τα alerts του EventBridge στο live store.

Είναι ο κρίκος που έλειπε: το ingest δημοσιεύει στο EventBridge, το query
διαβάζει από το DynamoDB, αλλά κανείς δεν έγραφε ενδιάμεσα.

Το κλειδί ακολουθεί ό,τι περιμένει το query.py:
    PK  geohash5              — το κελί ~5km
    SK  occurredAt#eventId    — χρονολογική σειρά μέσα στο κελί

Αποδιπλασιασμός: κάθε alert γράφεται μαζί με ένα marker item του οποίου το
κλειδί είναι το αποτύπωμα του περιεχομένου. Τα δύο γράφονται σε ΜΙΑ
transaction με συνθήκη στο marker, οπότε το δεύτερο αντίγραφο δεν μπορεί να
γράψει ούτε alert. Ένα read-then-write θα άφηνε παράθυρο ανάμεσα στον
έλεγχο και στην εγγραφή — δύο ταυτόχρονες Lambda θα περνούσαν και οι δύο.
"""

import hashlib
import os
import time
from decimal import Decimal

TABLE_NAME = os.environ.get("TABLE_NAME", "maps-traffic-alerts-dev")

# Όσο ζει το marker, τόσο διαρκεί η μνήμη του αποδιπλασιασμού. Ίδιο με τη
# ζωή του alert: όταν σβήσει το alert, ένα νέο για το ίδιο σημείο είναι
# πραγματικά νέο συμβάν, όχι διπλότυπο.
FALLBACK_TTL_SECONDS = 6 * 3600

# Το '#' δεν υπάρχει στο αλφάβητο του geohash (0-9, b-z χωρίς a/i/l/o), άρα
# ένα marker δεν μπορεί ποτέ να συγκρουστεί με πραγματικό κελί ούτε να
# επιστραφεί από το query.py, που ρωτά με ακριβή geohash5 τιμές.
DEDUP_PREFIX = "dedup#"

_client = None
_serializer = None


def _get_client():
    """Lazy + cached: ένα client ανά container, όχι ανά invocation."""
    global _client
    if _client is None:
        import boto3
        _client = boto3.client("dynamodb")
    return _client


def _serialize(item: dict) -> dict:
    """Python types -> DynamoDB AttributeValue.

    Το transact_write_items είναι low-level API και δεν δέχεται τα απλά
    dicts που φτιάχνει το to_item().
    """
    global _serializer
    if _serializer is None:
        from boto3.dynamodb.types import TypeSerializer
        _serializer = TypeSerializer()
    return {k: _serializer.serialize(v) for k, v in item.items()}


def fingerprint(detail: dict) -> str:
    """Αποτύπωμα περιεχομένου: τι σημαίνει «ίδιο συμβάν».

    geohash7 (~150m) και όχι geohash5 (~5km): αλλιώς δύο άσχετα περιστατικά
    στην ίδια πόλη θα θεωρούνταν ένα.

    Το κείμενο μπαίνει αυτούσιο. Τα διπλότυπα που πονάνε είναι
    byte-identical — το ίδιο μήνυμα Viber που το διαβάζουν πολλά κινητά, ή
    ένα retry του client — και τα πιάνει. Δύο άνθρωποι που περιγράφουν το
    ίδιο συμβάν με δικά τους λόγια περνούν, και σωστά: είναι επιβεβαίωση.
    """
    location = detail.get("location") or {}
    alert = detail.get("alert") or {}
    parts = "|".join([
        location.get("geohash7") or location.get("geohash5") or "",
        alert.get("type") or "",
        alert.get("text") or "",
    ])
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:32]


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


def _marker(detail: dict, expires_at: int) -> dict:
    return {
        "geohash5": DEDUP_PREFIX + fingerprint(detail),
        "sortKey": "marker",
        "eventId": detail["eventId"],      # ποιο event κράτησε τη θέση
        "expiresAt": expires_at,
    }


def handler(event, context):
    """EventBridge rule target: ένα event ανά invocation."""
    detail = event.get("detail") or {}

    if not detail.get("location", {}).get("geohash5") or not detail.get("eventId"):
        # Χωρίς κλειδί δεν γράφεται τίποτα. Σηκώνουμε εξαίρεση ώστε το
        # EventBridge να ξαναπροσπαθήσει και τελικά να το στείλει στο DLQ,
        # αντί να το καταπιούμε σιωπηλά.
        raise ValueError(f"event χωρίς geohash5/eventId: {detail.get('eventId')}")

    item = to_item(detail)
    expires_at = item.get(
        "expiresAt", int(time.time()) + FALLBACK_TTL_SECONDS
    )
    client = _get_client()

    try:
        client.transact_write_items(TransactItems=[
            {"Put": {
                "TableName": TABLE_NAME,
                "Item": _serialize(item),
            }},
            {"Put": {
                "TableName": TABLE_NAME,
                "Item": _serialize(_marker(detail, expires_at)),
                # Η μοναδική συνθήκη: αν το marker υπάρχει ήδη, ακυρώνεται
                # ΟΛΗ η transaction — άρα ούτε το alert γράφεται.
                "ConditionExpression": "attribute_not_exists(geohash5)",
            }},
        ])
    except client.exceptions.TransactionCanceledException as exc:
        reasons = [
            r.get("Code")
            for r in exc.response.get("CancellationReasons", [])
        ]
        if "ConditionalCheckFailed" not in reasons:
            raise                      # πραγματική αποτυχία, όχι διπλότυπο
        # Χωρίς αυτό δεν υπάρχει τρόπος να δεις πόσα κόβονται — ούτε αν ο
        # αποδιπλασιασμός δουλεύει, ούτε αν καταπίνει σωστές αναφορές.
        print(f"διπλότυπο: {detail['eventId']} -> {fingerprint(detail)}")
        return {"duplicate": detail["eventId"]}

    return {"stored": detail["eventId"]}
