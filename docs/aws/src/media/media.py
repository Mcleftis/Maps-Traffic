"""Media enrichment — ήχος και εικόνα γίνονται alerts.

ΜΕΛΛΟΝΤΙΚΗ ΔΥΝΑΤΟΤΗΤΑ. Κλειστή by default (EnableMediaPath=false): χωρίς
client που ανεβάζει αρχεία, οι πόροι θα ήταν νεκροί και θα κόστιζαν.

Η υπάρχουσα ροή δεν αγγίζεται πουθενά. Το media path είναι απλώς ένας
ακόμη ΠΑΡΑΓΩΓΟΣ alerts: καταλήγει στην IngestFunction, που παραμένει το
μοναδικό σημείο όπου γίνεται validation και κανονικοποίηση.

    S3 audio/  -> Transcribe -> S3 transcripts/ -> IngestFunction
    S3 image/  -> Rekognition                   -> IngestFunction

Οι συντεταγμένες ταξιδεύουν ως S3 object metadata (x-amz-meta-lat/lon):
ένα αρχείο χωρίς αυτές δεν είναι alert, είναι σκέτο media.
"""

import json
import os
import urllib.parse

import boto3

INGEST_FUNCTION = os.environ["INGEST_FUNCTION_NAME"]
TRANSCRIBE_LANGUAGE = os.environ.get("TRANSCRIBE_LANGUAGE", "el-GR")

AUDIO_PREFIX = "audio/"
IMAGE_PREFIX = "image/"
TRANSCRIPT_PREFIX = "transcripts/"

MIN_LABEL_CONFIDENCE = 80.0

# Το classify() του normalize.py ταιριάζει ΜΟΝΟ ελληνικές λέξεις-κλειδιά,
# ενώ το Rekognition επιστρέφει αγγλικά labels. Χωρίς αυτόν τον χάρτη κάθε
# φωτογραφία θα κατέληγε OTHER. Μεταφράζονται μόνο όσα αντιστοιχούν σε
# υπαρκτό κανόνα — τα υπόλοιπα labels είναι θόρυβος.
LABEL_TO_GREEK = {
    "car accident": "τροχαίο",
    "accident": "τροχαίο",
    "collision": "σύγκρουση",
    "wreck": "τροχαίο",
    "police": "αστυνομία",
    "police car": "αστυνομία",
    "traffic jam": "κίνηση",
    "traffic congestion": "κίνηση",
    "roadworks": "έργα",
    "construction": "έργα",
    "snow": "χιόνι",
    "fog": "ομίχλη",
    "ice": "πάγος",
}

_clients = {}


def _client(service: str):
    """Lazy + cached: ένα container εξυπηρετεί πολλά αρχεία, και η
    κατασκευή client είναι από τα ακριβότερα πράγματα στο boto3."""
    if service not in _clients:
        _clients[service] = boto3.client(service)
    return _clients[service]


def _coords(bucket: str, key: str) -> tuple:
    """lat/lon από το S3 metadata του αρχείου."""
    metadata = _client("s3").head_object(
        Bucket=bucket, Key=key
    ).get("Metadata", {})
    try:
        return float(metadata["lat"]), float(metadata["lon"])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"το {key} δεν έχει x-amz-meta-lat/lon")


def _submit(lat: float, lon: float, text: str, producer: str, label: str = ""):
    """Στέλνει το alert στην IngestFunction.

    Async invoke: το media path δεν περιμένει απάντηση, και έτσι η
    IngestFunction παραμένει το μόνο σημείο που ξέρει το σχήμα του event.
    """
    item = {"lat": lat, "lon": lon, "m": text, "producer": producer}
    if label:
        item["label"] = label
    _client("lambda").invoke(
        FunctionName=INGEST_FUNCTION,
        InvocationType="Event",
        Payload=json.dumps({"body": json.dumps([item], ensure_ascii=False)}),
    )


def handle_image(bucket: str, key: str) -> dict:
    """Rekognition DetectLabels -> ελληνικό κείμενο -> alert."""
    lat, lon = _coords(bucket, key)

    response = _client("rekognition").detect_labels(
        Image={"S3Object": {"Bucket": bucket, "Name": key}},
        MaxLabels=20,
        MinConfidence=MIN_LABEL_CONFIDENCE,
    )
    names = [label["Name"].lower() for label in response.get("Labels", [])]
    greek = [LABEL_TO_GREEK[n] for n in names if n in LABEL_TO_GREEK]

    if not greek:
        # Γενικά labels («Car», «Road») δεν περιγράφουν συμβάν. Καλύτερα
        # κανένα alert παρά ένα OTHER που θα λερώσει τον χάρτη.
        return {"skipped": key, "labels": names[:5]}

    _submit(lat, lon, " ".join(greek), "rekognition", label=greek[0])
    return {"submitted": key, "text": greek}


def handle_audio(bucket: str, key: str) -> dict:
    """Ξεκινά Transcribe job· η συνέχεια γίνεται στο transcripts/ event."""
    job = "mt-" + key[len(AUDIO_PREFIX):].replace("/", "-").replace(".", "-")
    _client("transcribe").start_transcription_job(
        TranscriptionJobName=job,
        LanguageCode=TRANSCRIBE_LANGUAGE,
        Media={"MediaFileUri": f"s3://{bucket}/{key}"},
        OutputBucketName=bucket,
        OutputKey=f"{TRANSCRIPT_PREFIX}{job}.json",
    )
    return {"started": job}


def handle_transcript(bucket: str, key: str) -> dict:
    """Διαβάζει το αποτέλεσμα και το στέλνει ως alert."""
    body = json.load(_client("s3").get_object(Bucket=bucket, Key=key)["Body"])
    text = body["results"]["transcripts"][0]["transcript"].strip()
    if not text:
        return {"skipped": key, "reason": "κενή μεταγραφή"}

    # Το job κρατά το URI του αρχικού ήχου — από εκεί έρχονται οι
    # συντεταγμένες, χωρίς να κωδικοποιηθούν στο όνομα του αρχείου.
    job_name = key[len(TRANSCRIPT_PREFIX):].rsplit(".", 1)[0]
    job = _client("transcribe").get_transcription_job(
        TranscriptionJobName=job_name
    )["TranscriptionJob"]
    audio_key = job["Media"]["MediaFileUri"].split(f"{bucket}/", 1)[1]

    lat, lon = _coords(bucket, audio_key)
    _submit(lat, lon, text[:500], "transcribe")
    return {"submitted": key, "text": text[:80]}


ROUTES = (
    (TRANSCRIPT_PREFIX, handle_transcript),   # πριν το audio/: πιο ειδικό
    (AUDIO_PREFIX, handle_audio),
    (IMAGE_PREFIX, handle_image),
)


def handler(event, context):
    results = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        for prefix, route in ROUTES:
            if key.startswith(prefix):
                outcome = route(bucket, key)
                break
        else:
            outcome = {"ignored": key}

        # Σε ασύγχρονη κλήση από S3 το return value δεν το διαβάζει κανείς·
        # χωρίς log δεν υπάρχει τρόπος να δεις τι έγινε με ένα αρχείο.
        print(json.dumps(outcome, ensure_ascii=False))
        results.append(outcome)

    return {"results": results}
