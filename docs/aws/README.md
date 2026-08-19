# AWS Solutions Architect — μελέτη πάνω στο Maps-Traffic

Αυτός ο φάκελος είναι **εκπαιδευτικό υλικό**, όχι περιγραφή του τι τρέχει σήμερα.

## Τι τρέχει σήμερα (πραγματικότητα)

```
[Android app] ──POST/GET──► [Cloudflare Worker + KV] ◄──GET── [Android app]
                             relay/worker.js
                             κρατά 200 alerts / 6 ώρες, μετά τα σβήνει
```

Μηδέν AWS. Μηδέν μόνιμο ιστορικό. Κάθε alert χάνεται μετά από 6 ώρες.

## Τι μελετάμε εδώ

Πώς θα έμοιαζε το ίδιο project αν χτιζόταν στο AWS ως **production-grade,
multi-region, event-driven σύστημα** — και τι μαθαίνει κανείς από κάθε κομμάτι.

Ο σκοπός είναι διπλός:

1. Να μάθουμε τις υπηρεσίες με ένα πραγματικό domain (traffic alerts), όχι με
   αφηρημένα παραδείγματα «Foo Service → Bar Queue».
2. Να μάθουμε **πότε ΔΕΝ** τις βάζουμε. Το SA exam και η πραγματική δουλειά
   ρωτούν «ποια είναι η *πιο κατάλληλη*», όχι «ποια *μπορεί* να δουλέψει».

## Χάρτης αρχείων

| Αρχείο | Τι καλύπτει |
|---|---|
| [`01-architecture.md`](01-architecture.md) | Η συνολική ροή end-to-end, με διαγράμματα |
| [`02-event-schema.md`](02-event-schema.md) | Το canonical event, mapping από το σημερινό relay |
| [`03-service-catalogue.md`](03-service-catalogue.md) | Και οι ~60 υπηρεσίες: ρόλος, tier, κόστος, τι μαθαίνεις |
| [`04-analytics.md`](04-analytics.md) | Glue → Athena → QuickSight, με πραγματικά queries |
| [`05-security.md`](05-security.md) | Identity, detection, data protection, governance |
| [`06-resilience.md`](06-resilience.md) | Multi-region, DR στρατηγικές, RTO/RPO |
| [`07-cost.md`](07-cost.md) | Τι κοστίζει κάθε φάση στα αλήθεια |
| [`iac/`](iac/) | CloudFormation template + Step Functions ASL + JSON Schema |
| [`src/`](src/) | Ο κώδικας των Lambda + [tests](src/test_pipeline.py) που τρέχουν χωρίς AWS |
| [`sql/`](sql/) | Glue DDL + Athena queries έτοιμα για copy-paste |
| [`lab/`](lab/) | Πρακτικές ασκήσεις με σειρά, από το μηδέν |

## Οι 6 φάσεις

Κάθε φάση είναι αυτοτελής: μπορείς να σταματήσεις σε οποιαδήποτε και να έχεις
κάτι που δουλεύει.

| Φάση | Τι χτίζεις | Κύριες υπηρεσίες | Κόστος/μήνα* |
|---|---|---|---|
| **0** | Ingest + storage | API Gateway, Lambda, S3 | ~0 € |
| **1** | Event-driven pipeline | EventBridge, Step Functions, Firehose, DynamoDB | ~1 € |
| **2** | Analytics | Glue, Athena, QuickSight | ~1 € + 18 €/author QuickSight |
| **3** | AI enrichment | Comprehend, Transcribe, Rekognition | ~5 € |
| **4** | Batch + data prep | Batch, DataBrew, EMR, Redshift | ~20 € (σβήνεις μετά) |
| **5** | Multi-region + governance | Global Accelerator, Organizations, Control Tower | ~50 €+ |

\* Με τον όγκο του project (μερικές δεκάδες alerts/μέρα). Δες [`07-cost.md`](07-cost.md)
για το τι *πραγματικά* χρεώνεται ανά ώρα ακόμα κι όταν δεν το χρησιμοποιείς.

## Τα τρία tiers των υπηρεσιών

Στο [`03-service-catalogue.md`](03-service-catalogue.md) κάθε υπηρεσία παίρνει tier:

- 🟢 **Core** — έχει πραγματικό ρόλο σε αυτό το project. Χτίσ' το.
- 🟡 **Learning** — δεν το χρειάζεται το project, αλλά το χρειάζεται το exam και
  η καριέρα. Χτίσ' το σε lab, σβήσ' το μετά.
- 🔴 **Theory** — μόνο μελέτη. Ή κοστίζει εκατοντάδες €/μήνα, ή χρειάζεται
  εταιρικό περιβάλλον (dedicated line, on-prem datacenter, multi-account org).
  Πρέπει να ξέρεις **τι λύνει** και **πότε το προτείνεις**, χωρίς να το στήσεις.

Αυτός ο διαχωρισμός είναι το πιο χρήσιμο πράγμα εδώ μέσα. Το να στήσεις Outposts
δεν σε κάνει καλύτερο αρχιτέκτονα· το να ξέρεις ότι το Outposts είναι η απάντηση
όταν ο πελάτης λέει «data residency + <10ms σε on-prem σύστημα», σε κάνει.

## Κανόνες που ισχύουν παντού εδώ μέσα

1. **Κανένα AWS credential στην εφαρμογή.** Ούτε access key, ούτε secret. Το
   κινητό μιλάει μόνο σε HTTPS endpoint. Ό,τι άλλο είναι κενό ασφαλείας.
2. **Καμία σύνδεση θέσης με ταυτότητα.** Το `deviceId` είναι salted hash, με
   salt που εναλλάσσεται. Δεδομένα θέσης = προσωπικά δεδομένα υπό GDPR.
3. **Budget alarm πριν από οτιδήποτε άλλο.** Η πρώτη άσκηση στο
   [`lab/00-account-setup.md`](lab/00-account-setup.md), όχι η τελευταία.
4. **Τίποτα εδώ δεν είναι deployed.** Αν κάτι μπει σε βιογραφικό, γράφεται ως
   *proposed architecture*, όχι ως υλοποιημένο.

## Τα παραδείγματα είναι επαληθευμένα

Οι τιμές μέσα στα κείμενα δεν είναι επινοημένες. Τρέξε:

```bash
python3 docs/aws/src/test_pipeline.py
```

45 έλεγχοι, χωρίς AWS και χωρίς εξαρτήσεις: τα geohash της Θεσσαλονίκης, τα
μεγέθη κελιών, ο πίνακας αντιστοίχισης από το `relay/worker.js`, η
ταξινομησιμότητα των ULID, και η συμφωνία `sample-event.json` ↔ `event-schema.json`.
