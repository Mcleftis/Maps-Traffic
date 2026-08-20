"""Geohash encode + γείτονες, χωρίς εξαρτήσεις.

Το geohash μετατρέπει 2D συντεταγμένες σε 1D string όπου το κοινό πρόθεμα
σημαίνει γεωγραφική εγγύτητα. Μήκος 5 -> κελί ~4.9km, μήκος 7 -> ~153m.

Η παγίδα: δύο σημεία εκατέρωθεν ορίου κελιού έχουν τελείως διαφορετικό hash
παρότι απέχουν 10 μέτρα. Γι' αυτό υπάρχει η neighbours().
"""

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def encode(lat: float, lon: float, precision: int = 7) -> str:
    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    out, bit, ch, even = [], 0, 0, True

    while len(out) < precision:
        if even:                                    # εναλλάξ: γεωγραφικό μήκος, μετά πλάτος
            mid = (lon_lo + lon_hi) / 2
            if lon > mid:
                ch = (ch << 1) | 1
                lon_lo = mid
            else:
                ch <<= 1
                lon_hi = mid
        else:
            mid = (lat_lo + lat_hi) / 2
            if lat > mid:
                ch = (ch << 1) | 1
                lat_lo = mid
            else:
                ch <<= 1
                lat_hi = mid

        even = not even
        bit += 1
        if bit == 5:                                # 5 bits ανά χαρακτήρα base32
            out.append(_BASE32[ch])
            bit, ch = 0, 0

    return "".join(out)


def _decode_bbox(gh: str):
    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    even = True
    for c in gh:
        idx = _BASE32.index(c)
        for shift in (4, 3, 2, 1, 0):
            bit = (idx >> shift) & 1
            if even:
                mid = (lon_lo + lon_hi) / 2
                lon_lo, lon_hi = (mid, lon_hi) if bit else (lon_lo, mid)
            else:
                mid = (lat_lo + lat_hi) / 2
                lat_lo, lat_hi = (mid, lat_hi) if bit else (lat_lo, mid)
            even = not even
    return lat_lo, lat_hi, lon_lo, lon_hi


def neighbours(gh: str) -> list:
    """Το κελί και οι 8 γείτονές του.

    Ένα proximity query ΠΡΕΠΕΙ να ρωτά και τα εννέα. Αν ρωτήσεις μόνο το κελί
    του χρήστη, χάνεις alerts που είναι 10 μέτρα μακριά αλλά στο διπλανό κελί.
    """
    lat_lo, lat_hi, lon_lo, lon_hi = _decode_bbox(gh)
    lat_c, lon_c = (lat_lo + lat_hi) / 2, (lon_lo + lon_hi) / 2
    d_lat, d_lon = lat_hi - lat_lo, lon_hi - lon_lo

    cells = []
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            lat = max(-90.0, min(90.0, lat_c + i * d_lat))
            lon = lon_c + j * d_lon
            lon = ((lon + 180.0) % 360.0) - 180.0        # τύλιγμα στον 180ό μεσημβρινό
            cells.append(encode(lat, lon, len(gh)))

    return sorted(set(cells))
