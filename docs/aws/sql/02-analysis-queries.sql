-- =====================================================================
-- Athena — τα ερωτήματα που τροφοδοτούν το QuickSight
--
-- Κανόνας κόστους: το Athena χρεώνει ανά TB που ΣΑΡΩΝΕΙ. Κάθε query εδώ
-- φιλτράρει σε partition (dt / region) ΠΡΩΤΑ. Ένα query χωρίς φίλτρο
-- partition σαρώνει ολόκληρο το bucket.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Hotspots — πού συμβαίνουν τα περισσότερα, τον τελευταίο μήνα
--    Ομαδοποίηση σε κελιά geohash7 (~150m).
-- ---------------------------------------------------------------------
SELECT
    geohash7,
    admin_area,
    alert_type,
    COUNT(*)                         AS total,
    ROUND(AVG(lat), 5)               AS center_lat,
    ROUND(AVG(lon), 5)               AS center_lon,
    ROUND(AVG(confidence), 2)        AS avg_confidence,
    MAX(occurred_at)                 AS last_seen
FROM maps_traffic.alerts_curated
WHERE dt >= CAST(current_date - interval '30' day AS varchar)
  AND alert_type IN ('ACCIDENT', 'ROAD_CLOSED')
GROUP BY geohash7, admin_area, alert_type
HAVING COUNT(*) >= 3          -- ένα μεμονωμένο συμβάν δεν είναι hotspot
ORDER BY total DESC
LIMIT 100;


-- ---------------------------------------------------------------------
-- 2. Χρονικό μοτίβο — ποια ώρα κάθε μέρας, ανά τύπο
--    Τροφοδοτεί heatmap ώρα x ημέρα στο QuickSight.
-- ---------------------------------------------------------------------
SELECT
    day_of_week,
    hour_of_day,
    alert_type,
    COUNT(*) AS total
FROM maps_traffic.alerts_curated
WHERE dt >= CAST(current_date - interval '90' day AS varchar)
GROUP BY day_of_week, hour_of_day, alert_type
ORDER BY day_of_week, hour_of_day;


-- ---------------------------------------------------------------------
-- 3. Ποιότητα δεδομένων ανά πηγή — πόσο αξιόπιστη είναι κάθε πηγή;
--    Ο πιο χρήσιμος πίνακας για να αποφασίσεις αν το Comprehend αξίζει.
-- ---------------------------------------------------------------------
SELECT
    source,
    input_type,
    COUNT(*)                                             AS total,
    ROUND(AVG(confidence), 3)                            AS avg_confidence,
    SUM(CASE WHEN alert_type = 'OTHER' THEN 1 ELSE 0 END) AS unclassified,
    ROUND(100.0 * SUM(CASE WHEN alert_type = 'OTHER' THEN 1 ELSE 0 END)
          / COUNT(*), 1)                                 AS unclassified_pct,
    ROUND(AVG(lag_seconds), 0)                           AS avg_lag_sec,
    approx_percentile(lag_seconds, 0.95)                 AS p95_lag_sec
FROM maps_traffic.alerts_curated
WHERE dt >= CAST(current_date - interval '30' day AS varchar)
GROUP BY source, input_type
ORDER BY total DESC;
-- unclassified_pct ψηλό => ο πίνακας κανόνων χρειάζεται συμπλήρωση,
-- ή η πηγή στέλνει κείμενο που δεν καταλαβαίνουμε.


-- ---------------------------------------------------------------------
-- 4. Duplicate detection — πόσο διπλογράφονται οι αναφορές;
--    Ίδιος τύπος, ίδιο κελί ~150m, μέσα σε 10 λεπτά.
-- ---------------------------------------------------------------------
WITH windowed AS (
    SELECT
        event_id,
        geohash7,
        alert_type,
        occurred_at,
        source,
        LAG(occurred_at) OVER (
            PARTITION BY geohash7, alert_type
            ORDER BY occurred_at
        ) AS prev_at
    FROM maps_traffic.alerts_curated
    WHERE dt >= CAST(current_date - interval '7' day AS varchar)
)
SELECT
    geohash7,
    alert_type,
    COUNT(*) AS likely_duplicates
FROM windowed
WHERE prev_at IS NOT NULL
  AND date_diff('minute', prev_at, occurred_at) <= 10
GROUP BY geohash7, alert_type
ORDER BY likely_duplicates DESC
LIMIT 50;


-- ---------------------------------------------------------------------
-- 5. Ημερήσια τάση ανά περιοχή — το βασικό γράφημα του dashboard
-- ---------------------------------------------------------------------
SELECT
    dt,
    region,
    alert_type,
    COUNT(*)                    AS total,
    COUNT(DISTINCT device_hash) AS reporting_devices
FROM maps_traffic.alerts_curated
WHERE dt >= CAST(current_date - interval '60' day AS varchar)
GROUP BY dt, region, alert_type
ORDER BY dt DESC, total DESC;


-- ---------------------------------------------------------------------
-- 6. Έλεγχος υγείας — τι μπήκε τις τελευταίες 24 ώρες
--    Τρέξ' το πρώτο όταν κάτι φαίνεται χαλασμένο.
-- ---------------------------------------------------------------------
SELECT
    dt,
    COUNT(*)                                     AS events,
    COUNT(DISTINCT source)                       AS sources,
    MIN(occurred_at)                             AS earliest,
    MAX(occurred_at)                             AS latest,
    SUM(CASE WHEN lat IS NULL OR lon IS NULL THEN 1 ELSE 0 END) AS missing_coords,
    SUM(CASE WHEN lat NOT BETWEEN 34.5 AND 42.0
              OR lon NOT BETWEEN 19.0 AND 30.0 THEN 1 ELSE 0 END) AS outside_greece
FROM maps_traffic.alerts_curated
WHERE dt >= CAST(current_date - interval '1' day AS varchar)
GROUP BY dt;
