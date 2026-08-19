# Lab — πρακτικές ασκήσεις με σειρά

Κάθε άσκηση έχει: **στόχο**, **βήματα**, **έλεγχο επιτυχίας**, **teardown**.

Το teardown δεν είναι προαιρετικό. Είναι βήμα της άσκησης.

---

## Οι κανόνες

1. Το [`00-account-setup.md`](00-account-setup.md) πρώτο. Καμία εξαίρεση.
2. Πριν από κάθε πόρο: *χρεώνεται ανά ώρα ή ανά χρήση;*
3. Κάθε 🟡 άσκηση σβήνεται την **ίδια ή την επόμενη μέρα**.
4. Region: `eu-central-1`. Πάντα το ίδιο.
5. Tags σε όλα: `Project=maps-traffic`, `Phase=N`.

---

## Φάση 0 — θεμέλια

### Lab 00 — Στήσιμο λογαριασμού ✅ υποχρεωτικό
[`00-account-setup.md`](00-account-setup.md) · 30′ · 0 €

### Lab 01 — S3 data lake
**Στόχος:** δύο buckets, κρυπτογράφηση, lifecycle, versioning.

1. Δημιούργησε `maps-traffic-raw-dev-<account-id>` και `-curated-`
2. Ενεργοποίησε KMS encryption και versioning
3. Lifecycle: Glacier IR στις 30 ημέρες
4. Ανέβασε ένα δείγμα JSON στο path `alerts/dt=2026-08-19/hh=12/`

**Έλεγχος:** `aws s3 ls` δείχνει το αρχείο· το console δείχνει «Encrypted».
**Teardown:** κράτα τα — τα χρειάζεσαι παρακάτω. Κόστος ~0.

### Lab 02 — Πρώτο Athena query
**Στόχος:** SQL πάνω σε αρχεία S3, χωρίς καμία βάση δεδομένων.

1. Τρέξε το [`../sql/01-create-tables.sql`](../sql/01-create-tables.sql)
2. `SELECT * FROM maps_traffic.alerts_raw LIMIT 10;`

**Έλεγχος:** το query επιστρέφει το δείγμα.
**Το μάθημα:** μόλις έκανες query σε δεδομένα χωρίς να σηκώσεις τίποτα. Αυτό
είναι όλη η ιδέα του data lake.
**Teardown:** lifecycle rule στον φάκελο `athena-results/`, αλλιώς μεγαλώνει
για πάντα.

---

## Φάση 1 — event-driven ροή

### Lab 03 — Deploy του ingest stack
**Στόχος:** το πλήρες ingest path, ως IaC.

```bash
cd docs/aws/iac
sam deploy --guided \
  --stack-name maps-traffic-ingest \
  --capabilities CAPABILITY_IAM \
  --region eu-central-1
```

**Έλεγχος:**

```bash
curl -X POST "<ApiEndpoint>/alerts" \
  -H "Content-Type: application/json" \
  -d @sample-event.json
```

Περιμένεις `202`, και μετά από ~15′ εμφανίζεται αρχείο στο raw bucket.

**Το μάθημα:** το buffering του Firehose (15′) είναι ο λόγος που αυτό είναι
*near*-real-time, όχι real-time. Αν χρειάζεσαι δευτερόλεπτα, θέλεις άλλο
σχεδιασμό.

**Teardown:** `sam delete --stack-name maps-traffic-ingest` (τα buckets έχουν
`DeletionPolicy: Retain`, μένουν).

### Lab 04 — EventBridge rules και φιλτράρισμα
**Στόχος:** content-based routing χωρίς κώδικα.

1. Φτιάξε rule με pattern μόνο για `ACCIDENT` + `MAJOR`
2. Target: SNS topic με το email σου
3. Στείλε δύο events: ένα `ACCIDENT/MAJOR`, ένα `CONGESTION/MINOR`

**Έλεγχος:** email μόνο για το πρώτο.
**Το μάθημα:** το φιλτράρισμα έγινε **στην υπηρεσία**. Δεν πλήρωσες Lambda για
να πεις «δεν με ενδιαφέρει».

### Lab 05 — EventBridge Archive & Replay
**Στόχος:** το χαρακτηριστικό που δικαιολογεί μόνο του το EventBridge.

1. Στείλε 10 events
2. Φτιάξε νέο rule με νέο target
3. **Replay** το archive της ημέρας στο νέο rule

**Έλεγχος:** ο νέος consumer βλέπει τα 10 παλιά events.
**Το μάθημα:** νέος consumer με πλήρες ιστορικό, χωρίς να αγγίξεις τον παραγωγό.

### Lab 06 — Step Functions
**Στόχος:** ενορχήστρωση με ορατότητα.

1. Deploy το [`../iac/step-functions-enrichment.asl.json`](../iac/step-functions-enrichment.asl.json)
2. Τρέξε ένα `TEXT` event και ένα `VOICE` event
3. Δες το γραφικό execution history

**Έλεγχος:** διαφορετικά μονοπάτια στο διάγραμμα.
**Το μάθημα:** δες πόσο εύκολα βλέπεις πού κόλλησε. Αυτό —όχι η ενορχήστρωση—
είναι ο κύριος λόγος που επιλέγεις Step Functions.

### Lab 07 — DynamoDB με geohash και TTL
**Στόχος:** το access pattern που αντικαθιστά το Cloudflare KV.

1. Γράψε 20 alerts με διαφορετικά `geohash5`
2. `Query` σε ένα κελί — δες ότι είναι ήδη χρονολογικά ταξινομημένα
3. Βάλε `expiresAt` σε +2 λεπτά και περίμενε

**Έλεγχος:** τα items εξαφανίζονται μόνα τους (το TTL αργεί έως 48 ώρες στην
πράξη — μη σε ανησυχήσει).
**Το μάθημα:** το `MAX_AGE_MS` του `relay/worker.js` έγινε ρύθμιση υπηρεσίας,
δωρεάν.

---

## Φάση 2 — analytics 🟡

### Lab 08 — DataBrew profile
**Στόχος:** τι πρόβλημα έχουν πραγματικά τα δεδομένα.

1. Dataset από το raw bucket
2. **Profile job** (όχι recipe job)
3. Διάβασε: null %, κατανομές, outliers

**Έλεγχος:** ξέρεις πόσα alerts έχουν κενό τύπο και πόσα coords εκτός Ελλάδας.
**Teardown:** τα profile jobs χρεώνονται ανά node-hour. Τρέξε, διάβασε,
**διάγραψε το project**.

### Lab 09 — Glue ETL: raw → curated
**Στόχος:** το βήμα που κάνει τα analytics φθηνά.

1. Glue Studio job: source raw, target curated
2. Μετασχηματισμοί: dedup, φίλτρο συντεταγμένων, παράγωγες στήλες
3. Output: Parquet + Snappy, partitioned by `dt`, `region`

**Έλεγχος:** τρέξε το ίδιο query σε raw και curated, σύγκρινε το «Data scanned».
**Το μάθημα:** αναμενόμενη διαφορά ~10-100×. Αυτό είναι το Cost Optimization
pillar σε μία μέτρηση.

### Lab 10 — Athena σε βάθος
**Στόχος:** όλα τα queries του [`../sql/02-analysis-queries.sql`](../sql/02-analysis-queries.sql).

Επιπλέον:
- Φτιάξε **workgroup** με `BytesScannedCutoffPerQuery = 100 MB`
- Τρέξε επίτηδες query χωρίς φίλτρο partition και δες το να κόβεται

**Το μάθημα:** το φράγμα που σε σώζει από το ατύχημα.

### Lab 11 — QuickSight 🟡 **18 $/μήνα**
**Στόχος:** dashboard πάνω στο Athena.

1. Enterprise trial, dataset από Athena, **SPICE** (όχι direct query)
2. Points-on-map, heat map ώρα×ημέρα, KPI
3. Ημερήσιο refresh schedule

**Teardown:** **Ακύρωσε τη συνδρομή** όταν τελειώσεις. Το QuickSight χρεώνει ανά
χρήστη ανά μήνα, όχι ανά χρήση — δεν σταματά μόνο του.

---

## Φάση 3 — AI 🟡

### Lab 12 — Comprehend vs κανόνες
**Η πιο διδακτική άσκηση όλου του lab.**

1. Μάζεψε 200 πραγματικά ελληνικά μηνύματα κίνησης
2. Χαρακτήρισέ τα χειροκίνητα (ground truth)
3. Τρέξε τον πίνακα κανόνων του [`../02-event-schema.md`](../02-event-schema.md)
   → μέτρα ακρίβεια
4. Τρέξε Comprehend → μέτρα ακρίβεια
5. **Σύγκρινε**

**Το μάθημα:** πολύ πιθανά οι κανόνες κερδίζουν στα ελληνικά. Αν συμβεί, το
σωστό συμπέρασμα είναι *οι κανόνες μένουν* — και αυτό είναι πιο πολύτιμο
αποτέλεσμα από ένα λειτουργικό Comprehend integration. Το baseline πριν από το
ML είναι το βήμα που παραλείπεται πιο συχνά σε πραγματικά έργα.

### Lab 13 — Transcribe
1. Ηχογράφησε 5 φωνητικές αναφορές στα ελληνικά
2. `el-GR`, από S3
3. Μέτρα word error rate σε ονόματα δρόμων

**Το μάθημα:** τα τοπωνύμια είναι το αδύνατο σημείο. Δες τα **custom
vocabularies** — εκεί λύνεται.

### Lab 14 — Rekognition, με όρια
1. `DetectLabels` σε 20 φωτογραφίες δρόμων
2. **ΠΟΤΕ** face/celebrity APIs

**Το μάθημα:** τα labels είναι γενικά (`Road`, `Vehicle`, `Traffic`). Για
«κλειστή λωρίδα» χρειάζεται custom model. Και σκέψου την ιδιωτικότητα *πριν*
γραφτεί η πρώτη γραμμή.

---

## Φάση 4 — batch 🟡

### Lab 15 — AWS Batch με Spot
1. Compute environment με **Spot**, max vCPU 4
2. Container με DBSCAN clustering
3. Scheduled EventBridge rule `cron(0 3 * * ? *)`

**Έλεγχος:** το job τρέχει, γράφει hotspots στο curated.
**Teardown:** **σβήσε το compute environment.** Ένα με min vCPU > 0 κρατά
instances ζωντανά επ' αόριστον.

### Lab 16 — EMR 🔴🔴 **~430 $/μήνα αν ξεχαστεί**
Μόνο αν θες την εμπειρία. `--auto-terminate` **υποχρεωτικά**.

Ένα ξεχασμένο cluster ένα Σαββατοκύριακο = ~65 $.

---

## Φάση 5 — resilience 🟡

### Lab 17 — DynamoDB Global Tables
1. Πρόσθεσε replica σε `eu-west-1`
2. Γράψε στο ένα, διάβασε από το άλλο, μέτρα την καθυστέρηση
3. Γράψε **ταυτόχρονα** στο ίδιο item και στα δύο

**Το μάθημα:** το βήμα 3 δείχνει last-writer-wins — δηλαδή **χαμένη εγγραφή**.
Αυτό είναι το πραγματικό κόστος του active-active, και δεν φαίνεται σε κανένα
διάγραμμα αρχιτεκτονικής.
**Teardown:** αφαίρεσε το replica.

### Lab 18 — Global Accelerator 🟡 **26 $/μήνα**
1. Accelerator με δύο endpoint groups
2. Ρίξε το primary επίτηδες
3. Χρονομέτρησε το failover

**Teardown:** **σβήσε το σήμερα.** Χρεώνει 0.025 $/ώρα ασταμάτητα.

### Lab 19 — Άσκηση DR
1. Προσποιήσου απώλεια region
2. `sam deploy` σε `eu-west-1` από το IaC
3. Restore δεδομένων
4. **Χρονομέτρησε** και σύγκρινε με το δηλωμένο RTO των 4 ωρών

**Το μάθημα:** αν δεν βγήκε ο χρόνος, ο αριθμός στο χαρτί ήταν λάθος. Διόρθωσέ
τον. Ένα DR σχέδιο που δεν δοκιμάστηκε είναι ευχή.

---

## Μετά το lab

Σβήσε τα πάντα εκτός από:

- Τα S3 buckets (λίγα λεπτά τον μήνα, κρατούν την ιστορία)
- CloudTrail, Access Analyzer (δωρεάν)
- Budget alarm (δωρεάν, και σε προστατεύει)

Τελικός έλεγχος:

```bash
aws ce get-cost-and-usage \
  --time-period Start=2026-08-01,End=2026-08-31 \
  --granularity MONTHLY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

Αν εμφανίζεται υπηρεσία που δεν περιμένεις, κάτι έμεινε ανοιχτό.
