# Three-minute evidence walkthrough

**0:00 — State the workflow.** This is a synthetic migration-readiness data pipeline. The objective is to preserve what arrived, make every defect visible, and prevent a clean-looking report from authorizing a bad batch.

**0:30 — Run `./demo`.** Tests run first. The demo produces READY, BLOCKED, READY. Open `runs/index.html`, then the defective report. Fifteen rejected rows are explicit; two valid lines remain queryable. Accepted-data monetary reconciliation can pass while release is still blocked.

**1:00 — Show the document boundary.** A one-cent imbalance rejects the header and both lines. Duplicate customer IDs are not resolved by a guess; all duplicates and affected documents are quarantined. Each source row is accepted or quarantined exactly once.

**1:30 — Show the money.** Open the clean report. USD gross debit and credit are each 1,950.59; EUR gross debit and credit are each 875.25. Currencies are separate. A zero net alone could conceal dropped balanced documents, so gross amounts and counts are checked too.

**2:00 — Show lineage and replay.** A journal key points to its BSEG line, BKPF header and relevant partner source row, including each source digest. Repeating an identical batch verifies and reuses it. Corrected source creates a separate clean batch; rejected evidence remains available.

**2:30 — Name the boundary.** The partner and unified-journal models are illustrative staging concepts. This does not execute SAP CVI, reconstruct complete ACDOCA, or perform a migration. My demonstrated contribution is data architecture, code, validation, provenance and controls. SAP functional specialists would approve actual target semantics.

## Questions worth anticipating

| Question | Concrete answer |
|---|---|
| Why a local pipeline? | It makes the controls runnable and inspectable without platform setup. A distributed engine is a deployment choice driven by volume and requirements. |
| Why block the batch if clean rows exist? | This contract permits no unresolved quarantine. Partial release would need an explicit business-approved policy and separate reconciliation scope. |
| Why not deduplicate automatically? | Conflicting identities require an authoritative rule or owner; selecting a row conceals a business decision. |
| Why no LLM? | Parsing, money, referential checks and release decisions are deterministic. An LLM could explain defects but must not waive them. |
| What would you build next? | Approved SAP adapters, release-specific mappings, externally anchored evidence, target-system reconciliation, and a governed cutover rehearsal. |
| Have you migrated SAP ECC to S/4HANA? | This project does not establish that experience. It demonstrates the transferable architecture and controls I can show directly. |
