-- =====================================================================
-- Glue Data Catalog — ορισμός πινάκων πάνω από το S3 data lake
-- Εκτελείται στο Athena query editor.
--
-- ΔΕΝ μετακινεί δεδομένα. Ορίζει μόνο "πώς διαβάζονται" τα αρχεία S3.
--
-- ΠΡΙΝ ΤΟ ΤΡΕΞΕΙΣ: αντικατέστησε το REPLACE_ME με τα πραγματικά ονόματα
-- buckets. Το iac/01-ingest-stack.yaml τα φτιάχνει ως
--   maps-traffic-raw-<env>-<account-id>
-- και τα επιστρέφει στα Outputs (RawBucketName):
--   aws cloudformation describe-stacks --stack-name maps-traffic-ingest \
--     --query 'Stacks[0].Outputs' --output table
-- =====================================================================

CREATE DATABASE IF NOT EXISTS maps_traffic
COMMENT 'Traffic alerts data lake — Maps-Traffic project';


-- ---------------------------------------------------------------------
-- RAW — ό,τι γράφει το Firehose, αυτούσιο.
-- Partition projection: το Athena υπολογίζει μόνο του τα partitions από
-- το path, χωρίς MSCK REPAIR TABLE και χωρίς Glue crawler.
-- Γλιτώνει χρόνο και κόστος crawler.
-- ---------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS maps_traffic.alerts_raw (
    schemaversion   string,
    eventid         string,
    eventtype       string,
    occurredat      string,
    ingestedat      string,
    alert           struct<
                        type:       string,
                        severity:   string,
                        confidence: double,
                        text:       string,
                        language:   string
                    >,   -- προσοχή: `text` είναι reserved στο Athena -> backticks στα queries
    location        struct<
                        lat:        double,
                        lon:        double,
                        geohash5:   string,
                        geohash7:   string,
                        accuracym:  int,
                        adminarea:  string
                    >,
    provenance      struct<
                        source:     string,
                        sourceref:  string,
                        inputtype:  string,
                        producer:   string,
                        devicehash: string,
                        enrichedby: array<string>
                    >
)
PARTITIONED BY (
    dt  string,   -- ημερομηνία, μορφή YYYY-MM-DD
    hh  string    -- ώρα, μορφή HH
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
    -- Ο Hive ΠΑΝΤΑ πεζοποιεί τα ονόματα στηλών. Τα κλειδιά του JSON είναι
    -- camelCase (schemaVersion, deviceHash). Με case.insensitive=TRUE ο SerDe
    -- τα ταιριάζει αγνοώντας πεζά/κεφαλαία. Χωρίς αυτό, οι στήλες βγαίνουν NULL
    -- ΧΩΡΙΣ σφάλμα — από τα πιο χρονοβόρα λάθη σε data lake.
    'case.insensitive'      = 'TRUE',
    'ignore.malformed.json' = 'TRUE'
)
LOCATION 's3://REPLACE_ME-maps-traffic-raw/alerts/'
TBLPROPERTIES (
    'projection.enabled'      = 'true',
    'projection.dt.type'      = 'date',
    'projection.dt.range'     = '2026-01-01,NOW',
    'projection.dt.format'    = 'yyyy-MM-dd',
    'projection.dt.interval'  = '1',
    'projection.dt.interval.unit' = 'DAYS',
    'projection.hh.type'      = 'integer',
    'projection.hh.range'     = '0,23',
    'projection.hh.digits'    = '2',
    'storage.location.template' =
        's3://REPLACE_ME-maps-traffic-raw/alerts/dt=${dt}/hh=${hh}/'
);


-- ---------------------------------------------------------------------
-- CURATED — Parquet, καθαρισμένο, dedup-αρισμένο από το Glue ETL.
-- Αυτό ρωτάει το QuickSight. ~10x φθηνότερο και ταχύτερο από το raw.
-- ---------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS maps_traffic.alerts_curated (
    event_id        string,
    occurred_at     timestamp,
    ingested_at     timestamp,
    lag_seconds     int,        -- ingested_at - occurred_at, δείκτης καθυστέρησης
    alert_type      string,
    severity        string,
    confidence      double,
    alert_text      string,
    lat             double,
    lon             double,
    geohash5        string,
    geohash7        string,
    admin_area      string,
    source          string,
    input_type      string,
    device_hash     string,
    hour_of_day     int,        -- προϋπολογισμένα για να μη γίνονται σε κάθε query
    day_of_week     int,
    is_rush_hour    boolean
)
PARTITIONED BY (
    dt      string,
    region  string    -- π.χ. thessaloniki, attiki
)
STORED AS PARQUET
LOCATION 's3://REPLACE_ME-maps-traffic-curated/alerts/'
TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

-- Το curated γράφεται από Glue job -> τα partitions πρέπει να δηλωθούν.
-- Το Glue job κάνει enableUpdateCatalog, οπότε δεν χρειάζεται χειροκίνητα.
-- Αν χρειαστεί: MSCK REPAIR TABLE maps_traffic.alerts_curated;
