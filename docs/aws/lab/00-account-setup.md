# Lab 00 — Στήσιμο λογαριασμού

**Πρώτη άσκηση. Καμία άλλη δεν ξεκινά πριν ολοκληρωθεί αυτή.**

Χρόνος: ~30 λεπτά. Κόστος: 0 €.

Ο λόγος που είναι πρώτη: κάθε ιστορία «μου ήρθε λογαριασμός 2.000 $» ξεκινά από
λογαριασμό χωρίς budget alarm και χωρίς MFA.

---

## 1. Root account — τα πρώτα 5 λεπτά

- [ ] **MFA στο root.** Authenticator app ή hardware key. Χωρίς εξαίρεση.
- [ ] **Καμία access key στο root.** Αν υπάρχει, διαγραφή τώρα. Μια root access
      key που διαρρέει δίνει πλήρη, μη περιοριζόμενο έλεγχο — τα SCP δεν
      εφαρμόζονται στο root του management account.
- [ ] **Alternate contacts** (billing, security, operations) — εκεί στέλνει το
      AWS τις ειδοποιήσεις κατάχρησης.
- [ ] Μετά από αυτό, **μη ξανασυνδεθείς ως root** παρά μόνο για τις ελάχιστες
      εργασίες που το απαιτούν (κλείσιμο λογαριασμού, αλλαγή billing).

---

## 2. Budget alarm — πριν από κάθε πόρο

**Billing → Budgets → Create budget → Cost budget**

```
Όνομα:     maps-traffic-monthly
Ποσό:      10 USD/μήνα
Ειδοποιήσεις:
  - Actual    > 50%   → email
  - Actual    > 80%   → email
  - Actual    > 100%  → email
  - FORECASTED > 100% → email     ← το πιο σημαντικό
```

Το **forecasted** alert σε προειδοποιεί όταν ο *ρυθμός* δείχνει υπέρβαση, δηλαδή
μέρες πριν συμβεί. Τα υπόλοιπα σε ενημερώνουν αφού έχεις ήδη ξοδέψει.

**Έλεγχος:** το email πρέπει να έχει επιβεβαιωθεί. Ένα budget που στέλνει σε
ανεπιβεβαίωτη διεύθυνση δεν στέλνει πουθενά.

---

## 3. Cost Anomaly Detection

**Billing → Cost Anomaly Detection → Create monitor → AWS services**

Δωρεάν. Μαθαίνει το κανονικό σου μοτίβο δαπανών και ειδοποιεί σε απόκλιση.
Πιάνει το ξεχασμένο cluster σε 1-2 ημέρες αντί για το τέλος του μήνα.

---

## 4. CloudTrail

**CloudTrail → Create trail**

```
Όνομα:               maps-traffic-audit
Multi-region:        ΝΑΙ            ← αλλιώς δεν βλέπεις άλλα regions
Log file validation: ΝΑΙ            ← ανιχνεύει αλλοίωση των logs
S3 bucket:           νέο, ξεχωριστό
KMS encryption:      ΝΑΙ
```

Το πρώτο trail είναι δωρεάν. Το `multi-region` είναι απαραίτητο: ένας
επιτιθέμενος που ξέρει ότι παρακολουθείς μόνο το `eu-central-1` απλά δουλεύει
αλλού.

---

## 5. Account-level Block Public Access

**S3 → Block Public Access settings for this account → Ενεργοποίηση και των 4**

Αυτό είναι σε επίπεδο **account**, όχι bucket. Σημαίνει ότι ακόμα κι αν κάποιος
κάνει λάθος σε ένα bucket policy, το S3 το αγνοεί.

Ο πιο συχνός τρόπος διαρροής δεδομένων στο AWS είναι το δημόσιο bucket. Αυτή η
μία ρύθμιση τον κλείνει καθολικά.

---

## 6. IAM Identity Center

**IAM Identity Center → Enable → Create user → Permission set: AdministratorAccess**

Δωρεάν, και αντικαθιστά τους IAM users με προσωρινά credentials που λήγουν.

Σύνδεση του CLI:

```bash
aws configure sso
# SSO start URL: από το Identity Center dashboard
# Region: eu-central-1
# Profile name: maps-traffic

aws sso login --profile maps-traffic
aws sts get-caller-identity --profile maps-traffic
```

**Γιατί όχι IAM user με access key:** το access key είναι μόνιμο. Αν διαρρεύσει,
ισχύει μέχρι να το ανακαλέσεις — και συνήθως το μαθαίνεις από τον λογαριασμό.
Το SSO δίνει credentials που λήγουν σε ώρες.

---

## 7. Access Analyzer

**IAM → Access Analyzer → Create analyzer → Zone of trust: Account**

Δωρεάν. Θα σου πει ποιοι πόροι είναι προσβάσιμοι από έξω. Στην αρχή τα ευρήματα
πρέπει να είναι μηδέν — και κάθε νέο εύρημα αργότερα αξίζει έλεγχο.

---

## 8. Περιορισμός regions (αν έχεις Organizations)

**Organizations → Policies → Service control policies**

Η πολιτική είναι στο [`../05-security.md`](../05-security.md#scp--το-πιο-πρακτικό-εργαλείο-κόστους).

Χωρίς Organizations, το ισοδύναμο είναι πειθαρχία: δούλευε πάντα με
`--region eu-central-1` και έλεγχε το Cost Explorer ανά region μία φορά τον μήνα.

---

## 9. Το τελικό checklist

```
[ ] MFA στο root
[ ] Μηδέν root access keys
[ ] Alternate contacts συμπληρωμένα
[ ] Budget alarm 10 $ με forecasted alert
[ ] Email επιβεβαιωμένο
[ ] Cost Anomaly Detection ενεργό
[ ] CloudTrail multi-region + log validation
[ ] S3 Block Public Access σε επίπεδο account
[ ] IAM Identity Center, CLI συνδεδεμένο
[ ] Access Analyzer ενεργό, μηδέν ευρήματα
[ ] Region περιορισμένο (SCP ή πειθαρχία)
```

---

## Η συνήθεια που πρέπει να αποκτηθεί εδώ

Πριν δημιουργήσεις **οποιονδήποτε** πόρο, τρεις ερωτήσεις:

1. **Χρεώνεται ανά ώρα ή ανά χρήση;** Δες τον πίνακα στο
   [`../07-cost.md`](../07-cost.md#-χρεώνουν-ακόμα-κι-όταν-κοιμάσαι).
2. **Πότε θα το σβήσω;** Γράψ' το στο ημερολόγιο **τώρα**, όχι μετά.
3. **Έχει tags;** `Project=maps-traffic`, `Environment=dev`, `Phase=N`.

Αν δεν μπορείς να απαντήσεις και στις τρεις, μη δημιουργήσεις τον πόρο.
