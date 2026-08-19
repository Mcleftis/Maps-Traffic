"""Lambda query — «δώσε μου τα ενεργά alerts κοντά μου».

Αντικαθιστά το GET του relay/worker.js. Η κρίσιμη διαφορά: το relay επιστρέφει
ΟΛΑ τα alerts (ένα KV κλειδί για τα πάντα)· εδώ ρωτάμε μόνο τα γεωγραφικά
σχετικά κελιά.
"""

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "ingest"))
import geohash                                     # noqa: E402

TABLE_NAME = os.environ.get("TABLE_NAME", "maps-traffic-alerts-dev")
MAX_ITEMS = 200


def _to_number(value):
    return float(value) if value is not None else None


def query_nearby(table, lat: float, lon: float, limit: int = MAX_ITEMS) -> list:
    """Ρωτά το κελί του χρήστη ΚΑΙ τους 8 γείτονες.

    Χωρίς τους γείτονες χάνονται alerts που απέχουν 10 μέτρα αλλά έτυχε να
    πέσουν στο διπλανό κελί — η βασική παγίδα του geohash.
    """
    from boto3.dynamodb.conditions import Key

    cell = geohash.encode(lat, lon, 5)
    items = []

    for neighbour in geohash.neighbours(cell):
        response = table.query(
            KeyConditionExpression=Key("geohash5").eq(neighbour),
            ScanIndexForward=False,                # νεότερα πρώτα: το sortKey
            Limit=limit,                           # ξεκινά με το occurredAt
        )
        items.extend(response.get("Items", []))

    # Το DynamoDB ταξινομεί μέσα σε κάθε partition, όχι μεταξύ partitions.
    items.sort(key=lambda i: i.get("sortKey", ""), reverse=True)
    return items[:limit]


def handler(event, context):
    params = event.get("queryStringParameters") or {}

    try:
        lat = float(params["lat"])
        lon = float(params["lon"])
    except (KeyError, TypeError, ValueError):
        return _response(400, {"error": "απαιτούνται αριθμητικά lat και lon"})

    limit = min(int(params.get("limit", MAX_ITEMS)), MAX_ITEMS)

    import boto3
    table = boto3.resource("dynamodb").Table(TABLE_NAME)
    items = query_nearby(table, lat, lon, limit)

    # Το DynamoDB επιστρέφει Decimal· δεν σειριοποιείται σε JSON.
    payload = [{
        "eventId": i.get("sortKey", "").split("#")[-1],
        "alertType": i.get("alertType"),
        "text": i.get("text"),
        "lat": _to_number(i.get("lat")),
        "lon": _to_number(i.get("lon")),
        "confidence": _to_number(i.get("confidence")),
        "occurredAt": i.get("sortKey", "").split("#")[0],
    } for i in items]

    return _response(200, {"items": payload, "count": len(payload)})


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            # Επιτρέπει στο CloudFront να κάνει cache τα GET — δες 07-cost.md:
            # κόβει ~95% των requests προς το origin.
            "Cache-Control": "public, max-age=60",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }
