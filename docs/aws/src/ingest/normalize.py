"""Κανονικοποίηση ελληνικού κειμένου -> κλειστό enum alertType.

Αυτό είναι το BASELINE. Πριν μπει Comprehend στη ροή, μετριέται η ακρίβεια
αυτού του αρχείου σε πραγματικά δεδομένα (lab/README.md, Lab 12). Αν οι
κανόνες κερδίζουν, το Comprehend δεν μπαίνει.
"""

import unicodedata

# Οι λέξεις-κλειδιά γράφονται ΧΩΡΙΣ τόνους: το fold() αφαιρεί τους τόνους
# και από το κείμενο εισόδου πριν το ταίριασμα.
RULES = [
    ("ACCIDENT",        ["τροχαιο", "ατυχημα", "συγκρουση", "καραμπολα", "συγκρουστηκ"]),
    ("ROAD_CLOSED",     ["κλειστ", "διακοπη κυκλοφοριας", "αποκλεισμ", "αποκλεισμενος"]),
    ("ROADWORKS",       ["εργα", "εργασιες", "οδικα εργα"]),
    ("POLICE",          ["αστυνομ", "τροχαια", "αλκοτεστ", "μπλοκο", "ελεγχ"]),
    ("WEATHER",         ["χιον", "παγοσ", "παγωμ", "ομιχλ", "χαλαζ", "καταιγιδ", "ολισθηρ"]),
    ("HAZARD",          ["λαδια", "χαλικι", "εμποδιο", "ζωο", "πτωση", "αντικειμενο"]),
    ("VEHICLE_STOPPED", ["ακινητοποιημεν", "χαλασμεν", "σταματημεν"]),
    ("CONGESTION",      ["κινηση", "μποτιλιαρισμα", "κυκλοφοριακο", "ουρα", "καθυστερησ"]),
]

SEVERITY = [
    ("CRITICAL", ["νεκρ", "σοβαρο τροχαιο", "πολλαπλ"]),
    ("MAJOR",    ["κλειστ", "τροχαιο", "αποκλεισμ", "τραυματ"]),
    ("MINOR",    ["ελαφρ", "μικρο"]),
]


def fold(text: str) -> str:
    """Πεζά + αφαίρεση τόνων + κανονικοποίηση τελικού σίγμα.

    Χωρίς αυτό, «Τροχαίο» και «τροχαιο» είναι διαφορετικά strings — και το
    τελικό σίγμα (ς/σ) σπάει το ταίριασμα σε λέξεις που τελειώνουν σε -ος.
    """
    if not text:
        return ""
    lowered = text.lower().replace("ς", "σ")
    decomposed = unicodedata.normalize("NFD", lowered)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", stripped)


# Οι λέξεις-κλειδιά περνούν από το ΙΔΙΟ fold() με το κείμενο εισόδου. Χωρίς
# αυτό, κάθε keyword με τελικό «ς» αποτυγχάνει σιωπηλά — δεν πετάει σφάλμα,
# απλώς δεν ταιριάζει ποτέ και όλα καταλήγουν OTHER.
_RULES = [(t, [fold(k) for k in kws]) for t, kws in RULES]
_SEVERITY = [(lvl, [fold(k) for k in kws]) for lvl, kws in SEVERITY]


def classify(text: str, label: str = "") -> tuple:
    """Επιστρέφει (alertType, confidence).

    Το `label` του relay ελέγχεται πρώτο: αν ο χρήστης διάλεξε ρητά κατηγορία,
    την εμπιστευόμαστε περισσότερο από το ελεύθερο κείμενο.
    """
    for haystack, confidence in ((fold(label), 0.95), (fold(text), 0.75)):
        if not haystack:
            continue
        for alert_type, keywords in _RULES:
            if any(k in haystack for k in keywords):
                return alert_type, confidence

    return "OTHER", 0.3


def severity_of(text: str, alert_type: str) -> str:
    folded = fold(text)
    for level, keywords in _SEVERITY:
        if any(k in folded for k in keywords):
            return level
    return "MAJOR" if alert_type in ("ACCIDENT", "ROAD_CLOSED") else "MODERATE"
