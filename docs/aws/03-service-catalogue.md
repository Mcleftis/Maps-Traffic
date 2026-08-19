# 03 — Κατάλογος υπηρεσιών

Όλες οι υπηρεσίες που αναφέρθηκαν, με ρόλο μέσα σε **αυτό** το project.

**Tier:**
🟢 Core — χτίσ' το · 🟡 Learning — lab και σβήσ' το · 🔴 Theory — μόνο μελέτη

Η στήλη «Πότε το προτείνεις» είναι η πιο σημαντική. Το exam ρωτά σενάρια, όχι
ορισμούς — δίνει μια περιγραφή πελάτη και ζητά την *καταλληλότερη* υπηρεσία.

---

## Analytics & Data

| Υπηρεσία | Tier | Ρόλος εδώ | Πότε το προτείνεις |
|---|---|---|---|
| **Athena** | 🟢 | SQL πάνω στα traffic events του S3 | Ad-hoc queries σε S3, χωρίς cluster, πληρωμή ανά query |
| **Glue** | 🟢 | Data Catalog + ETL raw→curated Parquet | Serverless ETL, schema discovery, catalog που τον μοιράζονται Athena/EMR/Redshift |
| **QuickSight** | 🟢 | Dashboards: hotspots, alerts/περιοχή/ώρα | BI χωρίς server, per-user χρέωση, embedding σε app |
| **DataBrew** | 🟡 | Profiling: πόσα null `alertType`, πόσα coords εκτός Ελλάδας | Data prep από αναλυτή χωρίς κώδικα, 250+ έτοιμοι μετασχηματισμοί |
| **Kinesis Data Streams** | 🟡 | Δεν χρειάζεται — ένας consumer | Πολλαπλοί ανεξάρτητοι consumers, ordering ανά shard, replay από σημείο |
| **Data Firehose** | 🟢 | Buffering + Parquet + partitioning προς S3 | Streaming σε S3/Redshift/OpenSearch χωρίς κώδικα, near-real-time (60s+) |
| **EMR** | 🟡 | Spark job για hotspot clustering σε 3 χρόνια δεδομένων | Petabyte-scale Spark/Hadoop, υπάρχων Spark κώδικας, ανάγκη για Spot |
| **Redshift** | 🟡 | Data warehouse αν τα events φτάσουν TB | Σύνθετα joins/aggregations, BI concurrency, >1TB, σταθερό workload |
| **OpenSearch** | 🟡 | `geo_distance` queries, ελληνικό full-text, geo heatmap | Full-text search, log analytics, geospatial queries, sub-second σε αυθαίρετα filters |
| **Neptune** | 🔴 | — | Graph traversals: κοινωνικά δίκτυα, fraud rings, knowledge graphs |

**Athena vs Redshift** — η κλασική ερώτηση. Athena: ad-hoc, σπάνιο, δεδομένα ήδη
στο S3, μηδέν διαχείριση. Redshift: επαναλαμβανόμενο, σύνθετο, πολλοί ταυτόχρονοι
χρήστες, αξίζει το προ-φορτωμένο columnar storage. Εδώ Athena, με τεράστια
διαφορά.

**EMR vs Glue** — Glue: serverless, Python/Scala Spark, δεν διαχειρίζεσαι
τίποτα. EMR: πλήρης έλεγχος cluster, custom Spark/Hadoop/Presto/HBase, Spot
instances για 70% έκπτωση. Ο κανόνας: Glue μέχρι να χρειαστείς κάτι που το Glue
δεν κάνει.

---

## Application Integration & Compute

| Υπηρεσία | Tier | Ρόλος εδώ | Πότε το προτείνεις |
|---|---|---|---|
| **EventBridge** | 🟢 | Router: ingest → enrichment/archive/live | Fan-out με content-based routing, SaaS integrations, scheduled rules, archive+replay |
| **Step Functions** | 🟢 | Ενορχήστρωση enrichment με branching + retries | Πολυβηματικά workflows, ορατότητα, retry/catch ανά βήμα, human approval |
| **Batch** | 🟡 | Νυχτερινό DBSCAN clustering σε hotspots | Batch compute με ουρά, Spot, εργασίες που ξεπερνούν τα 15′ της Lambda |
| **EKS** | 🔴 | — | Υπάρχον Kubernetes, multi-cloud portability, ώριμη πλατφορμική ομάδα |
| **IRSA** | 🔴 | — | Το σωστό pattern για IAM σε EKS pods — ποτέ node-level credentials |

**Batch vs Lambda:** το όριο είναι τα 15 λεπτά και τα 10 GB μνήμης. Πάνω από
αυτά, Batch (ή Fargate task).

**Το EKS εδώ θα ήταν λάθος** και αξίζει να ξέρεις γιατί: control plane 72 €/μήνα
σταθερά, συν nodes, συν λειτουργικό κόστος αναβαθμίσεων — για μια εφαρμογή που
τρέχει σε serverless με ~0 €. Το «γιατί όχι Kubernetes» είναι εξίσου έγκυρη
αρχιτεκτονική απάντηση με το «γιατί ναι».

---

## Machine Learning

| Υπηρεσία | Tier | Ρόλος εδώ | Πότε το προτείνεις |
|---|---|---|---|
| **Comprehend** | 🟡 | Ελληνικό κείμενο → `alertType` + entities | NLP χωρίς ML ομάδα: sentiment, entities, PII detection, custom classification |
| **Transcribe** | 🟡 | Φωνητική αναφορά οδηγού → κείμενο | Speech-to-text: call centers, υποτιτλισμός, φωνητικές εντολές |
| **Rekognition** | 🟡 | Φωτογραφία συμβάντος → labels | Image/video analysis: moderation, object detection, OCR σε εικόνα |
| **Textract** | 🔴 | — | Δομημένη εξαγωγή από έγγραφα: φόρμες, τιμολόγια, πίνακες σε PDF |

**Η ειλικρινής προειδοποίηση για τα ελληνικά.** Το Comprehend υποστηρίζει
περιορισμένο σύνολο γλωσσών για τις προ-εκπαιδευμένες λειτουργίες, και τα
ελληνικά δεν είναι από τις καλύτερα καλυμμένες. Η άσκηση εδώ είναι:

1. Φτιάξε το baseline με τον πίνακα κανόνων του [`02-event-schema.md`](02-event-schema.md).
2. Μέτρα την ακρίβειά του σε 200 πραγματικά μηνύματα Viber.
3. Τρέξε Comprehend στα ίδια 200.
4. **Σύγκρινε.** Αν οι κανόνες κερδίζουν, οι κανόνες μένουν.

Αυτή η διαδικασία —baseline πριν από ML— είναι πιο πολύτιμη από το ίδιο το
Comprehend. Είναι επίσης ο πιο συχνά παραλειπόμενος έλεγχος σε πραγματικά έργα.

**Rekognition και ιδιωτικότητα:** αν επιτραπούν φωτογραφίες, μπαίνουν άνθρωποι
και πινακίδες κυκλοφορίας στο κάδρο. Αυτό είναι βιομετρικά και προσωπικά δεδομένα
υπό GDPR. Ο σχεδιασμός πρέπει να προβλέπει: καθόλου face APIs, blur πριν την
αποθήκευση, σύντομο retention, ρητή συγκατάθεση. Το «θα το δούμε μετά» δεν είναι
επιλογή όταν το πρόστιμο υπολογίζεται σε ποσοστό τζίρου.

---

## Databases & Caching

| Υπηρεσία | Tier | Ρόλος εδώ | Πότε το προτείνεις |
|---|---|---|---|
| **DynamoDB** | 🟢 | Live alerts, geohash PK, TTL 6h | Γνωστά access patterns, single-digit ms, απεριόριστο scale, serverless |
| **DAX** | 🔴 | — | DynamoDB read-heavy με microsecond απαιτήσεις — write-through cache |
| **ElastiCache Memcached** | 🔴 | — | Απλό caching αντικειμένων, multi-threaded, χωρίς persistence/replication |
| **Aurora** | 🔴 | — | Σχεσιακά δεδομένα, MySQL/PostgreSQL συμβατότητα, 5x throughput, 15 replicas |
| **RDS Proxy** | 🔴 | — | Lambda + RDS: pooling συνδέσεων, αλλιώς εξαντλείς τα connections |
| **Global Tables** | 🔴 | — | Multi-region active-active DynamoDB με τοπικές εγγραφές παντού |

**Το RDS Proxy αξίζει να το ξέρεις ακόμα κι αν δεν το στήσεις.** Είναι το
κλασικό «γιατί έπεσε η βάση»: κάθε Lambda invocation ανοίγει δική της σύνδεση,
1000 concurrent Lambdas = 1000 συνδέσεις, η RDS σηκώνει μερικές εκατοντάδες. Το
Proxy κάνει pooling. Εμφανίζεται σε exam και σε πραγματικά incidents.

**Memcached vs Redis:** Memcached είναι multi-threaded και απλό — μόνο key/value.
Redis έχει δομές (sorted sets, geospatial!), persistence, replication, pub/sub.
Για geo queries το Redis `GEORADIUS` θα ήταν ενδιαφέρον εδώ· το Memcached δεν
έχει τίποτα αντίστοιχο.

---

## Networking & Content Delivery

| Υπηρεσία | Tier | Ρόλος εδώ | Πότε το προτείνεις |
|---|---|---|---|
| **CloudFront** | 🟢 | Edge cache των GET, TLS, WAF frontend | Στατικό+δυναμικό caching παγκοσμίως, DDoS απορρόφηση |
| **Global Accelerator** | 🟡 | Σταθερές anycast IP + failover σε δευτερόλεπτα | Non-HTTP πρωτόκολλα, σταθερές IP για allowlists, failover χωρίς DNS TTL |
| **PrivateLink** | 🔴 | — | Πρόσβαση σε υπηρεσία χωρίς έξοδο στο internet — VPC endpoints |
| **VPC Peering** | 🔴 | — | Δύο VPC να μιλήσουν, 1-προς-1, χωρίς transitive routing |
| **Transit Gateway** | 🔴 | — | Δεκάδες VPC + on-prem σε hub-and-spoke αντί για mesh peering |
| **Direct Connect** | 🔴 | — | Αφιερωμένη γραμμή προς AWS: σταθερό latency, μεγάλος όγκος, όχι internet |
| **Site-to-Site VPN** | 🔴 | — | Κρυπτογραφημένη σύνδεση on-prem↔AWS πάνω από internet· backup του DX |

**Το networking κομμάτι είναι 🔴 όχι επειδή είναι άχρηστο, αλλά επειδή δεν
στήνεται χωρίς εταιρικό περιβάλλον.** Πρέπει όμως να το ξέρεις — είναι μεγάλο
ποσοστό του SA exam. Το ελάχιστο που πρέπει να απαντάς αμέσως:

- **Peering vs Transit Gateway:** το peering δεν είναι transitive. A↔B και B↔C
  δεν σημαίνει A↔C. Με N VPC χρειάζεσαι N(N-1)/2 συνδέσεις. Το TGW είναι hub.
- **Direct Connect vs VPN:** DX = σταθερό latency, αφιερωμένο εύρος, εβδομάδες
  για να στηθεί, ακριβό. VPN = λεπτά για να στηθεί, φθηνό, latency του internet.
  Το production pattern είναι **DX με VPN ως backup**.
- **PrivateLink vs VPC endpoint gateway:** Gateway endpoints μόνο για S3 και
  DynamoDB, δωρεάν, μέσω route table. Interface endpoints (PrivateLink) για όλα
  τα υπόλοιπα, με ENI στο subnet σου, χρεώνονται ανά ώρα.

---

## Storage & Migration

| Υπηρεσία | Tier | Ρόλος εδώ | Πότε το προτείνεις |
|---|---|---|---|
| **S3** | 🟢 | Data lake: raw + curated | Αντικείμενα, 11 nines durability, lifecycle, event notifications |
| **S3 Object Lock** | 🟡 | WORM στο raw bucket αν χρειαστεί compliance | Αμετάβλητα δεδομένα: SEC 17a-4, ransomware protection |
| **EBS** | 🔴 | — | Block storage για EC2 — ένα instance τη φορά (πλην io2 Multi-Attach) |
| **FSx** | 🔴 | — | Διαμοιραζόμενο filesystem: Windows (SMB), Lustre (HPC), NetApp, OpenZFS |
| **Storage Gateway** | 🔴 | — | Hybrid: on-prem βλέπει το S3 ως NFS/SMB/iSCSI |
| **DataSync** | 🔴 | — | Μεταφορά TB από on-prem σε AWS πάνω από δίκτυο, με επαλήθευση |
| **Snowball** | 🔴 | — | Petabytes όπου το δίκτυο θα χρειαζόταν μήνες — φυσική συσκευή |
| **Transfer Family** | 🔴 | — | SFTP/FTPS/AS2 endpoint μπροστά από S3, για εταιρικούς συνεργάτες |
| **Backup** | 🟡 | Κεντρικά backup plans DynamoDB + S3 | Ενιαία πολιτική backup σε πολλές υπηρεσίες, cross-region, compliance |
| **Vault Lock** | 🔴 | — | Αμετάβλητη πολιτική backup που ούτε ο root δεν αλλάζει |

**Ο κανόνας του Snowball:** αν η μεταφορά με το διαθέσιμο εύρος ζώνης θέλει
πάνω από **μία εβδομάδα**, στέλνεις συσκευή. 100 TB σε γραμμή 1 Gbps ≈ 10 μέρες
με τέλεια αξιοποίηση, που δεν συμβαίνει ποτέ. Απλός υπολογισμός που εμφανίζεται
συχνά ως ερώτηση.

**Object Lock vs Vault Lock:** Object Lock προστατεύει *αντικείμενα S3*. Vault
Lock προστατεύει την *πολιτική* του backup vault. Το δεύτερο είναι αμετάκλητο —
μόλις κλειδώσει, δεν ξεκλειδώνει με κανέναν τρόπο. Ούτε το AWS support.

---

## Compute purchasing & infrastructure

| Υπηρεσία | Tier | Ρόλος εδώ | Πότε το προτείνεις |
|---|---|---|---|
| **EC2 Spot** | 🟡 | Compute environment του Batch για τα νυχτερινά jobs | Fault-tolerant, διακοπτόμενα workloads — έως 90% έκπτωση |
| **Savings Plans** | 🔴 | — | Δέσμευση $/ώρα για 1-3 χρόνια — ευέλικτο σε family/region |
| **Reserved Instances** | 🔴 | — | Δέσμευση σε συγκεκριμένο instance type — πλέον σχεδόν πάντα προτιμάς SP |
| **Dedicated Hosts** | 🔴 | — | Φυσικός server αποκλειστικά δικός σου: BYOL licensing, compliance |
| **Outposts** | 🔴 | — | AWS hardware στο δικό σου datacenter: data residency, <10ms σε on-prem |

**Spot και Batch ταιριάζουν τέλεια** και είναι η μία θέση όπου το Spot έχει
πραγματικό νόημα εδώ: το clustering job μπορεί να διακοπεί και να ξανατρέξει.
Αυτός είναι ακριβώς ο ορισμός του κατάλληλου Spot workload.

**Savings Plans vs RI, σε μια γραμμή:** τα Compute Savings Plans καλύπτουν EC2 +
Fargate + Lambda, σε οποιοδήποτε region και family. Τα RI είναι δεσμευμένα και
πιο άκαμπτα. Με μηδέν σταθερό compute εδώ, και τα δύο είναι 🔴 — αλλά ο
υπολογισμός break-even είναι κλασικό exam θέμα.

**Outposts:** ο μοναδικός λόγος ύπαρξης είναι «τα δεδομένα ΔΕΝ επιτρέπεται να
φύγουν από το κτίριο» ή «χρειάζομαι <10ms σε μηχάνημα παραγωγής». Αν το σενάριο
δεν λέει ένα από τα δύο, η απάντηση δεν είναι Outposts.

---

## Identity & Governance

| Υπηρεσία | Tier | Ρόλος εδώ | Πότε το προτείνεις |
|---|---|---|---|
| **IAM Identity Center** | 🟡 | SSO αντί για IAM users | Κεντρική πρόσβαση σε πολλά accounts, ενσωμάτωση με IdP |
| **Organizations** | 🟡 | Χωριστά accounts: dev / prod / logging | Πολλαπλά accounts, consolidated billing, SCPs |
| **SCP** | 🟡 | «Καμία υπηρεσία εκτός eu-*» — φράγμα κόστους | Guardrails που ούτε ο account admin παρακάμπτει |
| **Control Tower** | 🔴 | — | Landing zone με best practices έτοιμη, account factory |
| **Directory Service** | 🔴 | — | Managed Active Directory ή σύνδεση με υπάρχον on-prem AD |

**Το SCP είναι το πιο πρακτικά χρήσιμο εδώ** και το συνιστώ ακόμα και σε
προσωπικό account με Organizations: ένα SCP που απαγορεύει τα πάντα εκτός
`eu-central-1`/`eu-west-1` σε προστατεύει από το κλασικό «άνοιξα κάτι σε
us-east-1 πέρσι και πληρώνω από τότε».

**Προσοχή στη σημασιολογία των SCP:** δεν *δίνουν* δικαιώματα, μόνο ορίζουν το
μέγιστο επιτρεπτό. Χρειάζεσαι και IAM policy που να επιτρέπει. Ένα SCP που λέει
`Allow: *` δεν δίνει σε κανέναν τίποτα.

---

## Security & Detection

| Υπηρεσία | Tier | Ρόλος εδώ | Πότε το προτείνεις |
|---|---|---|---|
| **CloudTrail** | 🟢 | Ποιος έκανε τι, πότε, από ποια IP | Πάντα. Πρώτο πράγμα σε κάθε account |
| **GuardDuty** | 🟡 | Ανίχνευση: crypto mining, ύποπτα API calls | Managed threat detection χωρίς agents |
| **AWS Config** | 🟡 | «Έγινε public το bucket;» — συνεχής έλεγχος | Compliance drift, ιστορικό αλλαγών, auto-remediation |
| **Security Hub** | 🟡 | Συγκέντρωση findings + CIS/AWS FSBP scoring | Ενιαία εικόνα ασφάλειας σε πολλά accounts |
| **IAM Access Analyzer** | 🟢 | «Ποιος πόρος είναι εκτεθειμένος έξω;» | Εντοπισμός external access, δημιουργία least-privilege policies |
| **Inspector** | 🔴 | — | CVE scanning σε EC2, ECR images, Lambda |
| **Macie** | 🔴 | — | Εντοπισμός PII σε S3 buckets |
| **Shield Advanced** | 🔴 | — | DDoS >L4, 24/7 response team, cost protection — 3.000 $/μήνα |
| **Firewall Manager** | 🔴 | — | Κεντρική διαχείριση WAF/Shield/SG σε όλο τον οργανισμό |

**Το Access Analyzer είναι 🟢 και δωρεάν** — από τα λίγα security εργαλεία με
μηδέν κόστος και άμεση αξία. Η λειτουργία *policy generation* (παράγει
least-privilege policy από πραγματικό CloudTrail ιστορικό) είναι εξαιρετική και
υποχρησιμοποιείται.

**Το Macie θα γινόταν 🟢 τη στιγμή που μπουν φωτογραφίες ή ελεύθερο κείμενο
χρηστών στο S3** — γιατί τότε υπάρχει πραγματικός κίνδυνος PII. Σήμερα όχι.

**Shield Advanced:** 3.000 $/μήνα ανά organization. Το Shield *Standard* είναι
δωρεάν και ενεργό ήδη σε CloudFront/ALB/Route 53. Το Advanced το προτείνεις μόνο
σε πελάτη με πραγματική έκθεση σε DDoS και κόστος downtime που το δικαιολογεί.

---

## Resilience

| Υπηρεσία | Tier | Ρόλος εδώ | Πότε το προτείνεις |
|---|---|---|---|
| **Multi-Region** | 🟡 | S3 CRR + deploy σε δεύτερο region | RTO/RPO που ένα region δεν καλύπτει, data residency, latency |
| **Disaster Recovery** | 🟡 | Pilot Light: δεδομένα ζωντανά, compute σβηστό | Πάντα ως *στρατηγική*· η υλοποίηση εξαρτάται από RTO/RPO |
| **AWS Backup** | 🟡 | Κεντρικό plan, cross-region αντίγραφα | Ενιαία πολιτική, compliance reporting |

Αναλυτικά στο [`06-resilience.md`](06-resilience.md).

---

## Σύνοψη: τι χτίζεται πραγματικά

**🟢 Core (11)** — API Gateway, Lambda, EventBridge, Step Functions, DynamoDB,
Firehose, S3, Glue, Athena, QuickSight, CloudFront, CloudTrail, Access Analyzer.
Αυτά είναι το σύστημα.

**🟡 Learning (20)** — στήνονται σε lab, μένουν μια-δυο μέρες, σβήνονται. Το
[`lab/`](lab/) τα καλύπτει με σειρά και με ρητό βήμα teardown.

**🔴 Theory (25)** — μελετώνται από την τεκμηρίωση και τα whitepapers. Για κάθε
μία, ο στόχος είναι να μπορείς να απαντήσεις σε δύο ερωτήσεις χωρίς σκέψη:
*τι πρόβλημα λύνει* και *ποια είναι η πλησιέστερη εναλλακτική και γιατί όχι αυτή*.

Το να έχεις στήσει 60 υπηρεσίες δεν σε κάνει Solutions Architect. Το να μπορείς
να πεις «όχι, εδώ δεν χρειάζεσαι Kubernetes, και να γιατί» — σε κάνει.
