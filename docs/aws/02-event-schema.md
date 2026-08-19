# 02 — Το canonical event

Η πρώτη απόφαση σε κάθε event-driven αρχιτεκτονική, και η πιο δύσκολη να αλλάξει
μετά. Όλα τα υπόλοιπα (EventBridge rules, Glue schema, Athena queries, QuickSight
fields) κρέμονται από εδώ.

## Τι στέλνει σήμερα η εφαρμογή

Από το [`relay/worker.js`](../../relay/worker.js):

```json
{
  "id": "viber-8823",
  "t": 1787142600000,
  "g": "Κίνηση Θεσσαλονίκη",
  "m": "Τροχαίο στην Εγνατία, κλειστή η δεξιά λωρίδα",
  "lat": 40.6401,
  "lon": 22.9444,
  "ico": "⚠️",
  "label": "Τροχαίο"
}
```

Προβλήματα αυτού του σχήματος:

| Πρόβλημα | Γιατί πονάει |
|---|---|
| Μονογράμματα κλειδιά (`t`, `g`, `m`) | Εξοικονομούν bytes που δεν χρειάζεται να εξοικονομηθούν, και κάνουν κάθε query δυσανάγνωστο |
| Το `label` είναι ελεύθερο κείμενο | «Τροχαίο», «τροχαιο», «ΤΡΟΧΑΙΟ» = τρεις διαφορετικές κατηγορίες στο `GROUP BY` |
| Χωρίς schema version | Δεν μπορείς ποτέ να αλλάξεις το σχήμα χωρίς να σπάσεις παλιούς clients |
| Χωρίς πηγή/εμπιστοσύνη | Δεν ξεχωρίζεις ανθρώπινη αναφορά από AI-εξαγόμενη |
| `ico` (emoji) μέσα στα δεδομένα | Παρουσίαση μέσα στο data model. Ανήκει στο UI |

## Το canonical event

```json
{
  "schemaVersion": "1.0",
  "eventId": "01JCXG7K2N8P4QVR9WYZ3MDFTA",
  "eventType": "traffic.alert.created",
  "occurredAt": "2026-08-19T12:30:00.000Z",
  "ingestedAt": "2026-08-19T12:30:01.412Z",

  "alert": {
    "type": "ACCIDENT",
    "severity": "MAJOR",
    "confidence": 0.91,
    "text": "Τροχαίο στην Εγνατία, κλειστή η δεξιά λωρίδα",
    "language": "el"
  },

  "location": {
    "lat": 40.6401,
    "lon": 22.9444,
    "geohash5": "sx0r4",
    "geohash7": "sx0r4n7",
    "accuracyM": 25,
    "adminArea": "Θεσσαλονίκη"
  },

  "provenance": {
    "source": "VIBER_GROUP",
    "sourceRef": "Κίνηση Θεσσαλονίκη",
    "inputType": "TEXT",
    "producer": "android_app/33.0",
    "deviceHash": "b9c1…",
    "enrichedBy": ["comprehend@2026-08-19"]
  },

  "ttl": {
    "expiresAt": 1787164200
  }
}
```

## Οι αποφάσεις πίσω από κάθε πεδίο

### `eventId` — ULID, όχι UUIDv4

Το ULID είναι lexicographically sortable κατά χρόνο. Αυτό σημαίνει ότι όταν
γίνεται sort key στο DynamoDB, τα events βγαίνουν ήδη σε χρονολογική σειρά χωρίς
δεύτερο index. Το UUIDv4 είναι τυχαίο και δεν σου δίνει τίποτα.

### `occurredAt` vs `ingestedAt` — δύο διαφορετικοί χρόνοι

Θεμελιώδης διάκριση σε κάθε σύστημα δεδομένων: **event time** και **processing
time**. Μια αναφορά Viber μπορεί να διαβαστεί 10 λεπτά αφού γράφτηκε. Αν κρατάς
έναν χρόνο, δεν μπορείς ποτέ να απαντήσεις «πόσο αργούν οι αναφορές μας;» και τα
time-window aggregations βγάζουν λάθος αποτέλεσμα.

Και τα δύο σε **ISO 8601 UTC**, όχι epoch millis. Το `1787142600000` δεν
διαβάζεται από άνθρωπο σε ένα query result, δεν συγκρίνεται σε SQL χωρίς cast, και
ανοίγει τη συζήτηση «δευτερόλεπτα ή χιλιοστά;» σε κάθε client.

### `alert.type` — κλειστό enum

```
ACCIDENT · CONGESTION · ROAD_CLOSED · POLICE · HAZARD
ROADWORKS · WEATHER · VEHICLE_STOPPED · OTHER
```

Κλειστό σύνολο. Ό,τι δεν ταιριάζει → `OTHER`, με το πρωτότυπο κείμενο να
διατηρείται στο `alert.text`. Ποτέ ελεύθερο κείμενο σε πεδίο πάνω στο οποίο
κάνεις `GROUP BY`.

### `alert.confidence` — πάντα παρόν

`1.0` για ανθρώπινη αναφορά, το score του μοντέλου για AI. Χωρίς αυτό δεν
μπορείς ούτε να φιλτράρεις («δείξε μόνο >0.8») ούτε να μετρήσεις πόσο καλά τα
πάει το Comprehend στα ελληνικά.

### `location.geohash5` / `geohash7`

Το geohash μετατρέπει 2D συντεταγμένες σε 1D string όπου το κοινό πρόθεμα
σημαίνει γεωγραφική εγγύτητα.

| Μήκος | Ακρίβεια κελιού |
|---|---|
| 5 | ~4.9 km |
| 6 | ~1.2 km |
| 7 | ~153 m |

- **`geohash5`** = partition key στο DynamoDB. Αρκετά μεγάλο κελί ώστε ένα query
  να επιστρέφει χρήσιμα αποτελέσματα, αρκετά μικρό ώστε να μη γίνει hot partition.
- **`geohash7`** = deduplication. Δύο `ACCIDENT` στο ίδιο `geohash7` μέσα σε 10
  λεπτά είναι το ίδιο συμβάν αναφερμένο δύο φορές.

**Η παγίδα του geohash:** δύο σημεία εκατέρωθεν ενός ορίου κελιού έχουν τελείως
διαφορετικό hash παρότι απέχουν 10 μέτρα. Γι' αυτό ένα σωστό proximity query
ελέγχει το κελί **και τους 8 γείτονές του**. Αν αυτό ενοχλεί, το OpenSearch
`geo_distance` κάνει τη σωστή δουλειά — αλλά κοστίζει cluster.

### `provenance` — η πιο υποτιμημένη ενότητα

Όταν το QuickSight δείξει κάτι παράξενο, η πρώτη ερώτηση είναι «από πού ήρθε
αυτό;». Χωρίς provenance δεν υπάρχει απάντηση.

- `source` — `VIBER_GROUP · USER_REPORT · WAZE · TOMTOM · SYSTEM`
- `inputType` — `TEXT · VOICE · IMAGE` (καθορίζει το branch στο Step Functions)
- `deviceHash` — **salted** hash. Το salt εναλλάσσεται μηνιαία, ώστε ο ίδιος
  χρήστης να μην είναι συσχετίσιμος διαχρονικά. Δεδομένα θέσης + σταθερό
  αναγνωριστικό = παρακολούθηση, ανεξάρτητα από το αν το λες pseudonymous.
- `enrichedBy` — ποια μοντέλα το άγγιξαν. Όταν αναβαθμιστεί το Comprehend
  classifier, θέλεις να ξέρεις ποια events βγήκαν από ποια έκδοση.

### `ttl.expiresAt` — Unix seconds, μόνο εδώ

Το DynamoDB TTL απαιτεί epoch **seconds** ως number. Είναι η μοναδική εξαίρεση
στον κανόνα του ISO 8601, και υπάρχει επειδή το επιβάλλει η υπηρεσία.

## Το event στο EventBridge

Το EventBridge τυλίγει το payload σε δικό του envelope. Το canonical event πάει
ολόκληρο στο `detail`:

```json
{
  "version": "0",
  "id": "…",
  "detail-type": "traffic.alert.created",
  "source": "maps-traffic.ingest",
  "account": "123456789012",
  "time": "2026-08-19T12:30:01Z",
  "region": "eu-central-1",
  "resources": [],
  "detail": { "…το canonical event…" }
}
```

Τα rules φιλτράρουν πάνω στο `detail`. Παράδειγμα — μόνο σοβαρά συμβάντα προς
ειδοποίηση:

```json
{
  "source": ["maps-traffic.ingest"],
  "detail-type": ["traffic.alert.created"],
  "detail": {
    "alert": {
      "type": ["ACCIDENT", "ROAD_CLOSED"],
      "severity": ["MAJOR", "CRITICAL"]
    }
  }
}
```

Αυτό το φιλτράρισμα τρέχει **στην υπηρεσία**, όχι σε δικό σου κώδικα. Δεν
πληρώνεις Lambda invocation για να πεις «δεν με ενδιαφέρει αυτό». Είναι το κύριο
επιχείρημα υπέρ του EventBridge έναντι μιας ουράς που καταναλώνεις μόνος σου.

## Mapping από το σημερινό relay

Ένας adapter, ώστε το υπάρχον Android app να μη χρειαστεί άμεση αλλαγή:

| Πεδίο relay | Canonical | Μετασχηματισμός |
|---|---|---|
| `id` | `provenance.sourceId` | Το αρχικό id της πηγής· νέο ULID ως `eventId` |
| `t` | `occurredAt` | epoch ms → ISO 8601 UTC |
| `g` | `provenance.sourceRef` | Όνομα ομάδας Viber |
| `m` | `alert.text` | Αυτούσιο |
| `lat`/`lon` | `location.lat`/`lon` | + υπολογισμός geohash |
| `ico` | — | **Απορρίπτεται.** Παρουσίαση, ανήκει στο UI |
| `label` | `alert.type` | Κανονικοποίηση σε enum, με fallback `OTHER` |

Ο πίνακας κανονικοποίησης (μια πραγματικά χρήσιμη άσκηση σε ελληνικά δεδομένα):

```
τροχαίο, ατύχημα, σύγκρουση, καραμπόλα     → ACCIDENT
κίνηση, μποτιλιάρισμα, κυκλοφοριακό, ουρά  → CONGESTION
κλειστός, διακοπή, αποκλεισμός             → ROAD_CLOSED
αστυνομία, τροχαία, έλεγχος, αλκοτέστ      → POLICE
έργα, εργασίες                             → ROADWORKS
λάδια, χαλίκι, εμπόδιο, ζώο                → HAZARD
χιόνι, πάγος, ομίχλη, χαλάζι               → WEATHER
```

**Σημείωση για τα ελληνικά:** η κανονικοποίηση πρέπει να αφαιρεί τόνους και να
πέφτει σε lowercase πριν το ταίριασμα, αλλιώς «Τροχαίο» και «τροχαιο» δεν
ταιριάζουν. Το τελικό σίγμα (`ς` vs `σ`) είναι ξεχωριστή παγίδα. Αυτός ο πίνακας
είναι επίσης το **baseline** με το οποίο θα συγκριθεί το Comprehend: αν οι
κανόνες πιάνουν 85% και το Comprehend 80%, το Comprehend δεν μπαίνει.

## Schema evolution

Το `schemaVersion` δεν είναι διακοσμητικό. Οι κανόνες:

1. **Προσθήκη προαιρετικού πεδίου** → minor bump (`1.0` → `1.1`). Οι παλιοί
   consumers το αγνοούν. Επιτρέπεται ελεύθερα.
2. **Αφαίρεση ή μετονομασία πεδίου** → major bump (`2.0`). Απαιτεί περίοδο
   συνύπαρξης όπου παράγονται και τα δύο.
3. **Αλλαγή σημασίας υπάρχοντος πεδίου** → το χειρότερο. Πάντα νέο πεδίο.

Το **EventBridge Schema Registry** μπορεί να ανακαλύψει το schema αυτόματα από
τα events που περνούν και να παράγει code bindings. Αξίζει η άσκηση, γιατί
δείχνει πώς λύνεται το contract management σε event-driven συστήματα — το
αντίστοιχο του OpenAPI για async.

## Αναφορές

- Πλήρες JSON Schema: [`iac/event-schema.json`](iac/event-schema.json)
- Glue table DDL: [`sql/01-create-tables.sql`](sql/01-create-tables.sql)
