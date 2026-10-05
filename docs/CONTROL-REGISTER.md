# Control register

| Control | Evidence | Failure behavior |
|---|---|---|
| CSV schema and file contract | Input loader; tests | Stop before publishing a batch |
| Unique master and line IDs | Quarantine with reason codes | Reject all ambiguous master rows; reject whole affected documents |
| Parent and reference integrity | Document dispositions; SQLite foreign-key check | Reject orphan and dependent documents |
| Exact monetary representation | Integer cents and Decimal parser | Reject invalid/negative/zero/nonfinite/overprecision values |
| Whole-document balance | `evidence/documents.json` | Reject header and every line |
| Row conservation | `evidence/reconciliation.json` | Block release if any row is unaccounted for |
| Gold line/partner conservation | `evidence/reconciliation.json` | Block release on count mismatch |
| Gross amount conservation | Per-company/currency Silver and Gold debits/credits | Block release on mismatch |
| No unresolved quarantine | `evidence/release.json` | Deny even when accepted data reconciles |
| Nonempty output | `nonempty_batch` | Deny vacuous READY for empty data |
| Artifact integrity | `manifest.json`; `verify` | Refuse changed, missing or added files |
| Idempotent rerun | Input + code + contract content identity | Verify and reuse existing run; do not overwrite corruption |
| Record provenance | `evidence/lineage.json` | File/CSV row/digest, transformation ID, batch identity |

## Known limitations

- Full datasets reside in memory; fixture volumes are deliberately small. No scale/performance claim.
- The filesystem is not immutable. An attacker can rewrite a manifest; it has no external trust anchor.
- Private-build/rename publication assumes a local filesystem and one writer per batch. Concurrent writers may fail safely with a filesystem error; there is no distributed locking or object-store transaction protocol.
- JSON Gold and the SQLite copy are created together; there is no independent target-system reconciliation. SQLite is for exploration, not SAP load approval.
- Gross reconciliation begins with accepted Silver. Raw rejected values remain in quarantine; malformed and unknown-currency amounts are not silently included in totals.
- No CDC, deletes, SCD type 2, incremental watermark, historical master validity, cross-company posting, FX, currency decimal configuration or partial release workflow.
- Unrecognized source fields/files fail closed. References use intentionally small allowlists rather than live SAP customizing.
- Code hashes identify this local implementation, not an independently signed release. Python version is not part of the content identity; cross-version byte-identical SQLite output is not promised.
- Local readiness gates provide evidence only. No real destination write exists to enforce.

## Extension path

1. Replace fixtures with an approved extraction adapter while preserving source snapshots and contracts.
2. Obtain functional-owner-approved mappings for the selected SAP release and migration strategy.
3. Externalize reference data and version the transformation contract.
4. Introduce scalable columnar layers and a catalog when volume and operating requirements justify them.
5. Add authenticated target adapters, business-key reconciliation against target results, controlled publication and recovery.
6. Anchor evidence externally; add operational monitoring, permissions, retention and accountable remediation.

Each step should add new tests that can fail for a real defect rather than merely assert a configured label.
