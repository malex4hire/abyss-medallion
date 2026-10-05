# Mapping assumptions, not a migration specification

## BP-1: customer/supplier to illustrative business partner

`KNA1.KUNNR` becomes `C` + the original ten-character ID. `LFA1.LIFNR` becomes `S` + the ID. Name whitespace is trimmed, country must exist in the small explicit reference set, and the customer/supplier role is retained. Duplicate keys invalidate all rows for that key; there is no latest-wins assumption or name-based entity merge.

The prefixes are **demo identifiers**, not approved SAP number ranges. Customer and supplier records that represent one legal entity would require governed matching, CVI customizing, grouping, number ranges, role assignment, tax/address/contact validation, company-code and sales/purchasing organizational data. Those are not represented here. `CUSTOMER` and `SUPPLIER` are conceptual labels, not SAP role codes or an API contract.

## UJ-1: FI-like lines to journal staging

The join key is `(BUKRS, BELNR, GJAHR)`. `BUZEI` identifies a line. IDs and accounts remain strings. `BUDAT` must be an eight-digit calendar date within the fixture fiscal year. **That calendar-year rule is a demo assumption:** real fiscal-year variants can differ and require configured SAP semantics.

`WRBTR` represents a positive document-currency amount; `BKPF.WAERS` supplies that currency. `SHKZG=S` creates positive debit cents and `H` negative credit cents. Supported currencies have two decimal places. No local-currency amount is inferred. Every accepted document must balance exactly in its document currency. The Gold summary groups company and currency independently.

This does **not** recreate ACDOCA from BSEG. Real Universal Journal migration semantics include ledger, controlling integration, currencies and valuation views, account assignments, asset accounting, document splitting, profitability dimensions, extension fields, fiscal variants, and release-dependent transformations. ACDOCA identifiers and line numbering must not be inferred from this toy model. No HKONT-to-RACCT compatibility claim is made; `account` merely retains the synthetic source account.

## Extraction and loading boundary

CSV fixtures use a few familiar field labels but are not full SAP table schemas or certified extracts. A real engagement must select supported extraction and migration interfaces for the deployment model and release, profile actual data, validate SAP simplification items, agree authoritative mapping rules with functional owners, and rehearse load/reconciliation/cutover using target-system evidence. A local READY result establishes only the bounded staging contract.

## Repair boundary

The repaired fixture restores the originally intended source values. That demonstrates a corrected new extract, not an automated business decision. The failed batch stays unchanged. In real work, remediation would require accountable source owners, an approved mapping version, and evidence connecting the correction to the relevant defect.
