# 05 — Security

Τέσσερα επίπεδα: **ταυτότητα**, **προστασία δεδομένων**, **ανίχνευση**,
**διακυβέρνηση**. Το Security pillar του Well-Architected τα εξετάζει με αυτή τη
σειρά, γιατί με αυτή τη σειρά καταρρέουν.

---

## 0. Τα σημερινά προβλήματα — πριν από κάθε AWS συζήτηση

Αυτά ισχύουν **τώρα**, στο repo, ανεξάρτητα από cloud:

| Εύρημα | Γιατί μετράει |
|---|---|
| TomTom API key μέσα στον κώδικα | Όποιος έχει το APK το έχει. Χρεώνεται ο λογαριασμός σου |
| Keystore password στο build script | Όποιος το έχει, υπογράφει APK ως εσύ |
| `SHARED_KEY` ένα για όλους | Δεν ανακαλείται ανά συσκευή. Διαρροή = αλλαγή σε όλους |
| `.git` ιστορικό | Το σβήσιμο ενός secret σε νέο commit **δεν** το αφαιρεί από το ιστορικό |

Το σημαντικό: ένα secret που μπήκε ποτέ σε git θεωρείται διαρρεύσαν. Η μόνη
πραγματική διόρθωση είναι **rotation στην πηγή** (νέο TomTom key, νέο keystore),
όχι διαγραφή του commit.

Σχετική AWS λύση: **Secrets Manager** (αυτόματο rotation) ή **SSM Parameter
Store SecureString** (δωρεάν, χωρίς rotation). Για ένα προσωπικό project το
Parameter Store επαρκεί.

---

## 1. Ταυτότητα

### Ο κανόνας που δεν παραβιάζεται ποτέ

**Καμία AWS credential σε εφαρμογή που εγκαθίσταται σε συσκευή χρήστη.** Ένα APK
αποσυμπιέζεται σε δευτερόλεπτα. Ό,τι είναι μέσα, είναι δημόσιο.

Η αλυσίδα:

```
Χρήστης → Cognito User Pool → JWT (1h) → API Gateway authorizer → Lambda
                                              ↑ επικυρώνει το token
                          Το κινητό δεν αγγίζει ποτέ IAM credentials
```

| | Σημερινό `SHARED_KEY` | Cognito JWT |
|---|---|---|
| Ταυτοποίηση | Καμία — όλοι ίδιοι | Ανά χρήστη |
| Ανάκληση | Αλλαγή σε όλες τις συσκευές | Ανά χρήστη, άμεσα |
| Λήξη | Ποτέ | 1 ώρα, με refresh token |
| Rate limit ανά χρήστη | Αδύνατο | Usage plan |
| Ποιος έστειλε τι | Άγνωστο | Στο `sub` claim |

### IAM: least privilege στην πράξη

Κάθε ρόλος βλέπει **έναν** πόρο. Στο [`iac/01-ingest-stack.yaml`](iac/01-ingest-stack.yaml)
ο FirehoseRole γράφει μόνο στο raw bucket, ο EventsToFirehoseRole κάνει μόνο
`PutRecord` σε ένα stream.

Πρακτικές:

- Ποτέ `"Resource": "*"` όταν μπορεί να γραφτεί συγκεκριμένο ARN.
- Ποτέ managed policy `*FullAccess` σε role υπηρεσίας.
- **IAM Access Analyzer policy generation**: παράγει least-privilege policy από
  πραγματικό CloudTrail ιστορικό. Ξεκινάς πλατιά σε dev, τρέχεις μια βδομάδα,
  παράγεις τη σφιχτή policy από τα δεδομένα. Υποχρησιμοποιείται σοβαρά.
- **Permission boundaries** όταν επιτρέπεις σε άλλους να φτιάχνουν roles.

### Root account

Πριν από οτιδήποτε άλλο, στο πρώτο 5λεπτο:

1. MFA με hardware key ή authenticator app
2. Καμία access key στο root — αν υπάρχει, διαγραφή
3. Καθημερινή χρήση μόνο μέσω IAM Identity Center
4. Alert σε κάθε root login (CloudTrail → EventBridge → SNS)

---

## 2. Προστασία δεδομένων

### Κρυπτογράφηση

**Σε ηρεμία:** S3 με KMS, DynamoDB με KMS, Firehose με KMS, CloudWatch Logs με
KMS. Στο template είναι όλα ενεργά.

- **SSE-S3 vs SSE-KMS:** το SSE-S3 είναι δωρεάν αλλά δεν ελέγχεις το κλειδί ούτε
  βλέπεις ποιος αποκρυπτογράφησε. Το SSE-KMS δίνει audit trail στο CloudTrail
  και δυνατότητα να *ανακαλέσεις* την πρόσβαση σβήνοντας το κλειδί.
- **Customer managed key** αντί για AWS managed: 1 $/μήνα, αλλά επιτρέπει key
  policy, rotation και cross-account έλεγχο.

**Σε μεταφορά:** TLS 1.2+ παντού. Bucket policy που απορρίπτει non-TLS:

```json
{
  "Effect": "Deny",
  "Principal": "*",
  "Action": "s3:*",
  "Resource": ["arn:aws:s3:::bucket/*"],
  "Condition": { "Bool": { "aws:SecureTransport": "false" } }
}
```

### Ιδιωτικότητα — το πιο σοβαρό θέμα αυτού του project

Δεδομένα τοποθεσίας είναι **προσωπικά δεδομένα** υπό GDPR. Η διαδρομή ενός
ανθρώπου αποκαλύπτει σπίτι, δουλειά, ιατρό, θρήσκευμα, σχέσεις.

Οι τεχνικοί κανόνες που αυτό επιβάλλει:

1. **Salted, εναλλασσόμενο `deviceHash`.** Salt που αλλάζει μηνιαία, ώστε ο ίδιος
   χρήστης να μη συσχετίζεται διαχρονικά. Ένα σταθερό hash είναι
   ψευδωνυμοποίηση, όχι ανωνυμοποίηση — και το GDPR το αντιμετωπίζει ως
   προσωπικό δεδομένο.
2. **Στρογγυλοποίηση συντεταγμένων στο ιστορικό.** Το geohash7 (~150m) αρκεί για
   hotspots. Οι πλήρεις συντεταγμένες δεν χρειάζεται να μείνουν για πάντα.
3. **Ρητό retention.** Raw: 90 ημέρες. Aggregated (χωρίς device link): επ'
   αόριστον. Lifecycle rules, όχι καλές προθέσεις.
4. **Διαγραφή κατ' αίτηση.** Άρθρο 17. Πρέπει να μπορείς να βρεις και να
   σβήσεις τα δεδομένα ενός χρήστη — γι' αυτό υπάρχει το `deviceHash`.
5. **Καθόλου face/plate recognition** αν μπουν φωτογραφίες. Blur πριν την
   αποθήκευση, σύντομο retention, ρητή συγκατάθεση.

**Το Macie** γίνεται σχετικό τη στιγμή που μπαίνει ελεύθερο κείμενο χρηστών ή
φωτογραφίες στο S3 — σαρώνει buckets για PII. Σήμερα όχι.

---

## 3. Ανίχνευση

| Υπηρεσία | Τι απαντά | Κόστος |
|---|---|---|
| **CloudTrail** | «Ποιος έκανε τι, πότε, από πού;» | Πρώτο trail δωρεάν |
| **GuardDuty** | «Συμβαίνει κάτι κακόβουλο;» | ~1-3 €/μήνα σε μικρό account |
| **AWS Config** | «Άλλαξε κάτι σε μη συμμορφούμενη κατάσταση;» | ~0.003 $/config item |
| **Security Hub** | «Πόσο καλά τα πάμε συνολικά;» | ~0.001 $/έλεγχο |
| **Access Analyzer** | «Τι είναι εκτεθειμένο προς τα έξω;» | **Δωρεάν** |

### CloudTrail — πάντα πρώτο

Καταγράφει κάθε API call. Χωρίς αυτό δεν υπάρχει έρευνα περιστατικού, μόνο
εικασίες.

Σωστή ρύθμιση:

- Multi-region trail (αλλιώς ο επιτιθέμενος δουλεύει σε άλλο region)
- **Log file validation** — ανιχνεύει αλλοίωση των ίδιων των logs
- Ξεχωριστό bucket, ιδανικά σε ξεχωριστό account, με **Object Lock**
- Ένα CloudTrail που μπορεί να σβήσει ο επιτιθέμενος δεν είναι audit trail

### GuardDuty

Managed threat detection χωρίς agents. Διαβάζει CloudTrail, VPC Flow Logs, DNS
logs και εντοπίζει: crypto mining, credentials που χρησιμοποιούνται από ασυνήθιστη
IP, επικοινωνία με γνωστά κακόβουλα endpoints, ανώμαλα API patterns.

Η αξία του: **δεν χρειάζεται να ξέρεις τι ψάχνεις**. Το κλασικό σενάριο —
διαρροή access key από GitHub και χρήση για mining— το πιάνει σε λεπτά.

### AWS Config

Συνεχής αξιολόγηση. Τα κρίσιμα rules εδώ:

```
s3-bucket-public-read-prohibited
s3-bucket-server-side-encryption-enabled
dynamodb-table-encrypted-kms
cloudtrail-enabled
iam-root-access-key-check
iam-user-mfa-enabled
lambda-function-public-access-prohibited
```

Με **auto-remediation**: αν ένα bucket γίνει public, το SSM document το κλείνει
αυτόματα σε δευτερόλεπτα. Αυτό είναι το πραγματικό όφελος — όχι η αναφορά, η
αυτόματη διόρθωση.

### Security Hub

Συγκεντρώνει findings από GuardDuty, Inspector, Macie, Config και τα βαθμολογεί
έναντι προτύπων (AWS Foundational Security Best Practices, CIS Benchmark). Ένα
σκορ συμμόρφωσης και μια λίστα ιεραρχημένων ευρημάτων.

Σε ένα account η αξία είναι μέτρια. Σε οργανισμό με 50 accounts είναι
απαραίτητο — και αυτή είναι η σωστή απάντηση όταν το ρωτούν σε σενάριο.

---

## 4. Διακυβέρνηση

### SCP — το πιο πρακτικό εργαλείο κόστους

Ένα Service Control Policy που κλειδώνει τα regions είναι η καλύτερη προστασία
από ξεχασμένους πόρους:

```json
{
  "Effect": "Deny",
  "NotAction": ["iam:*", "organizations:*", "route53:*",
                "cloudfront:*", "support:*", "budgets:*"],
  "Resource": "*",
  "Condition": {
    "StringNotEquals": {
      "aws:RequestedRegion": ["eu-central-1", "eu-west-1"]
    }
  }
}
```

Τα εξαιρούμενα (`NotAction`) είναι global υπηρεσίες που ζουν στο `us-east-1` —
χωρίς αυτή την εξαίρεση κλειδώνεσαι έξω από το ίδιο σου το IAM.

**Η σημασιολογία των SCP** είναι κλασική παγίδα εξετάσεων: δεν *δίνουν*
δικαιώματα, ορίζουν μόνο το **μέγιστο επιτρεπτό**. Χρειάζεσαι *και* IAM policy
που να επιτρέπει. Ένα SCP `Allow: *` δεν δίνει σε κανέναν τίποτα.

### Διαχωρισμός accounts

Το production pattern:

```
Organization root
├── Security OU     → log-archive (CloudTrail, αμετάβλητο), security-tooling
├── Workloads OU    → maps-traffic-dev, maps-traffic-prod
└── Sandbox OU      → πειραματισμός, με αυστηρό SCP και budget
```

Το `log-archive` account είναι το σημαντικό: ακόμα κι αν το prod παραβιαστεί
πλήρως, τα logs είναι σε άλλο account όπου ο επιτιθέμενος δεν έχει πρόσβαση.

Το **Control Tower** στήνει ακριβώς αυτή τη δομή αυτόματα (landing zone +
account factory + guardrails). Είναι 🔴 για προσωπικό project, αλλά ξέρεις τι
λύνει.

---

## Checklist

**Πριν από κάθε deploy:**

- [ ] Budget alarm ενεργό ([`lab/00-account-setup.md`](lab/00-account-setup.md))
- [ ] MFA στο root, μηδέν root access keys
- [ ] CloudTrail multi-region με log validation
- [ ] Block Public Access σε επίπεδο **account**, όχι μόνο bucket
- [ ] Κρυπτογράφηση σε όλα τα data stores
- [ ] SCP περιορισμού regions (αν υπάρχει Organizations)
- [ ] Κανένα secret σε git — έλεγχος με `git-secrets` ή `gitleaks`

**Μηνιαία:**

- [ ] Access Analyzer findings
- [ ] Αχρησιμοποίητα IAM roles και κλειδιά
- [ ] Config compliance
- [ ] Πραγματικό κόστος vs budget

**Τα τρία που δεν παραβιάζονται:**

1. Καμία AWS credential σε client εφαρμογή. Ποτέ.
2. Καμία σύνδεση θέσης με σταθερή ταυτότητα.
3. Κανένα secret σε git — και ό,τι μπήκε ποτέ, θεωρείται διαρρεύσαν.
