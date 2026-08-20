"""Tests χωρίς εξαρτήσεις: python3 docs/aws/src/test_pipeline.py

Δεν χρειάζεται AWS, boto3 ή pytest. Επαληθεύει ότι ο adapter, ο ελληνικός
κανονικοποιητής, το geohash και το proximity query συμφωνούν με όσα λένε τα
docs — και ότι το sample-event.json ταιριάζει με το event-schema.json.
"""

import json
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "common", "python"))
sys.path.insert(0, os.path.join(HERE, "ingest"))
sys.path.insert(0, os.path.join(HERE, "query"))


def _stub_boto3():
    """Το query.py χρειάζεται boto3 μόνο για τον τύπο Key. Το υποκαθιστούμε."""
    class Key:
        def __init__(self, name):
            self.name = name

        def eq(self, value):
            return types.SimpleNamespace(name=self.name, value=value)

    boto3 = types.ModuleType("boto3")
    ddb = types.ModuleType("boto3.dynamodb")
    cond = types.ModuleType("boto3.dynamodb.conditions")
    cond.Key = Key
    boto3.dynamodb = ddb
    ddb.conditions = cond
    sys.modules.update({
        "boto3": boto3,
        "boto3.dynamodb": ddb,
        "boto3.dynamodb.conditions": cond,
    })


_stub_boto3()

import geohash                                       # noqa: E402
from ingest import to_canonical, validate, ValidationError, _ulid   # noqa: E402
from normalize import classify, fold                 # noqa: E402
from query import query_nearby                       # noqa: E402

PASSED, FAILED = [], []


def check(name, condition, detail=""):
    (PASSED if condition else FAILED).append(name)
    print(f"  {'✓' if condition else '✗'} {name}{'  ' + detail if detail and not condition else ''}")


# ---------------------------------------------------------------- geohash
print("\ngeohash")
GH5, GH7 = "sx0r4", "sx0r4n7"
LAT, LON = 40.6401, 22.9444

check("Θεσσαλονίκη -> geohash5 " + GH5, geohash.encode(LAT, LON, 5) == GH5)
check("Θεσσαλονίκη -> geohash7 " + GH7, geohash.encode(LAT, LON, 7) == GH7)

lat_lo, lat_hi, lon_lo, lon_hi = geohash._decode_bbox(GH7)
check("το κελί περιέχει το σημείο", lat_lo <= LAT <= lat_hi and lon_lo <= LON <= lon_hi)
check("κελί precision 7 ≈ 153m (docs)", abs((lat_hi - lat_lo) * 111_320 - 153) < 5)
check("γείτονες = 9 κελιά", len(geohash.neighbours(GH5)) == 9)
check("οι γείτονες περιέχουν το ίδιο το κελί", GH5 in geohash.neighbours(GH5))
check("Αθήνα σε άλλο κελί", geohash.encode(37.9838, 23.7275, 5) != GH5)

# ------------------------------------------------------- ελληνικοί κανόνες
print("\nκανονικοποίηση ελληνικών (baseline πριν το Comprehend)")
check("το fold αφαιρεί τόνους + τελικό σίγμα", fold("Κλειστός") == "κλειστοσ")

for text, label, expected in [
    ("Τροχαίο στην Εγνατία", "Τροχαίο", "ACCIDENT"),
    ("ΤΡΟΧΑΙΟ ΜΕ ΚΕΦΑΛΑΙΑ", "", "ACCIDENT"),
    ("τροχαιο χωρις τονους", "", "ACCIDENT"),
    ("Μεγάλο μποτιλιάρισμα", "", "CONGESTION"),
    ("Κλειστός ο δρόμος", "", "ROAD_CLOSED"),
    ("Αστυνομικός έλεγχος", "", "POLICE"),
    ("Αστυνομία στον κόμβο", "", "POLICE"),
    ("Πάγος στην άσφαλτο", "", "WEATHER"),
    ("Λάδια στο οδόστρωμα", "", "HAZARD"),
    ("Ακινητοποιημένο όχημα", "", "VEHICLE_STOPPED"),
    ("Καλημέρα σε όλους", "", "OTHER"),
]:
    got, _ = classify(text, label)
    check(f"{expected:<16} <- {text[:32]}", got == expected, f"πήρα {got}")

# ------------------------------------------------------------ relay adapter
print("\nadapter: relay/worker.js -> canonical event")
RELAY = {
    "id": "viber-8823", "t": 1787142600000, "g": "Κίνηση Θεσσαλονίκη",
    "m": "Τροχαίο στην Εγνατία, κλειστή η δεξιά λωρίδα",
    "lat": LAT, "lon": LON, "ico": "⚠️", "label": "Τροχαίο",
}
ev = to_canonical(RELAY, now_ms=1787142601412)
validate(ev)

check("alert.type = ACCIDENT", ev["alert"]["type"] == "ACCIDENT")
check("alert.severity = MAJOR", ev["alert"]["severity"] == "MAJOR")
check("occurredAt = event time", ev["occurredAt"] == "2026-08-19T12:30:00.000Z")
check("ingestedAt = processing time", ev["ingestedAt"] == "2026-08-19T12:30:01.412Z")
check("occurredAt != ingestedAt", ev["occurredAt"] != ev["ingestedAt"])
check("TTL = +6 ώρες", ev["ttl"]["expiresAt"] - 1787142601 == 6 * 3600)
check("το emoji ico ΔΕΝ μπαίνει στο data model", "⚠️" not in json.dumps(ev))
check("sourceId διατηρεί το id του relay", ev["provenance"]["sourceId"] == "viber-8823")
check("sourceRef διατηρεί την ομάδα", ev["provenance"]["sourceRef"] == "Κίνηση Θεσσαλονίκη")
check("canonical event περνά αναλλοίωτο", to_canonical(ev) is ev)

print("\nαπόρριψη άκυρων δεδομένων")
for bad, why in [
    ({"lat": 51.5, "lon": -0.12, "m": "Λονδίνο"}, "συντεταγμένες εκτός Ελλάδας"),
    ({"lat": "40.6", "lon": 22.9, "m": "x"}, "lat ως string"),
    ({"m": "χωρίς συντεταγμένες"}, "λείπουν lat/lon"),
]:
    try:
        to_canonical(bad)
        check(why, False, "πέρασε ενώ έπρεπε να απορριφθεί")
    except ValidationError:
        check(why, True)

# -------------------------------------------------------------------- ULID
print("\nULID")
ulids = [_ulid(1787142600000 + i * 1000) for i in range(20)]
check("26 χαρακτήρες, Crockford base32",
      all(re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", u) for u in ulids))
check("lexicographically sortable κατά χρόνο", ulids == sorted(ulids))
check("μοναδικά", len(set(_ulid() for _ in range(500))) == 500)

# --------------------------------------------------------- proximity query
print("\nproximity query (DynamoDB)")


class FakeTable:
    def __init__(self):
        self.queried = []

    def query(self, **kw):
        cell = kw["KeyConditionExpression"].value
        self.queried.append(cell)
        n = len(self.queried)
        return {"Items": [{"geohash5": cell,
                           "sortKey": f"2026-08-19T12:{n:02d}:00Z#EVT{n}"}]}


table = FakeTable()
items = query_nearby(table, LAT, LON)
check("ρωτά 9 κελιά (κέντρο + 8 γείτονες)", len(table.queried) == 9)
check("περιλαμβάνει το κελί του χρήστη", GH5 in table.queried)
check("ταξινόμηση νεότερα-πρώτα μεταξύ partitions",
      items == sorted(items, key=lambda i: i["sortKey"], reverse=True))

# ------------------------------------------- sample-event vs JSON Schema
print("\nsample-event.json vs event-schema.json")
iac = os.path.join(HERE, "..", "iac")
sample = json.load(open(os.path.join(iac, "sample-event.json"), encoding="utf-8"))
schema = json.load(open(os.path.join(iac, "event-schema.json"), encoding="utf-8"))

check("όλα τα required πεδία υπάρχουν",
      all(f in sample for f in schema["required"]))
check("κανένα άγνωστο πεδίο (additionalProperties: false)",
      set(sample) <= set(schema["properties"]))
check("alert.type είναι στο enum",
      sample["alert"]["type"] in schema["properties"]["alert"]["properties"]["type"]["enum"])
check("eventId ταιριάζει με το ULID pattern",
      re.fullmatch(schema["properties"]["eventId"]["pattern"], sample["eventId"]) is not None)
check("geohash5 ταιριάζει με το pattern",
      re.fullmatch(schema["properties"]["location"]["properties"]["geohash5"]["pattern"],
                   sample["location"]["geohash5"]) is not None)
check("geohash του sample συμφωνεί με τα coords",
      geohash.encode(sample["location"]["lat"], sample["location"]["lon"], 5)
      == sample["location"]["geohash5"])
check("provenance χωρίς άγνωστα πεδία",
      set(sample["provenance"]) <= set(schema["properties"]["provenance"]["properties"]))

# ------------------------------------------------------------------ σύνοψη
print(f"\n{'=' * 58}")
print(f"πέρασαν: {len(PASSED)}   απέτυχαν: {len(FAILED)}")
if FAILED:
    for name in FAILED:
        print("  ✗", name)
    sys.exit(1)
print("ΟΛΑ ΠΕΡΑΣΑΝ")
