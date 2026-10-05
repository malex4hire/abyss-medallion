"""Content-addressed Bronze -> validated Silver -> reconciled Gold staging artifacts."""
import hashlib
import json
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from pathlib import Path

from .quality import cents, doc_key, validate
from .source import SCHEMAS, read_extracts
from .storage import digest, verify_run, write_json

VERSION = '1'


def run(source: Path, output: Path) -> Path:
    """Snapshot first; build privately; publish by rename. Identical batches reuse verified output."""
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.building-', dir=output) as temporary:
        work = Path(temporary)
        bronze = work / 'bronze'
        shutil.copytree(source, bronze)
        tables = read_extracts(bronze)
        hashes = {f'{name}.csv': digest(bronze / f'{name}.csv') for name in SCHEMAS}
        code_hashes = {p.name: digest(p) for p in Path(__file__).parent.glob('*.py')}
        identity = {'source': hashes, 'code': code_hashes, 'contract_version': VERSION}
        run_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        destination = output / run_id
        if destination.exists():
            verify_run(destination)
            return destination
        accepted, quarantine, dispositions = validate(tables)
        build(work, accepted, quarantine, dispositions, tables, run_id, hashes)
        files = {str(p.relative_to(work)): digest(p) for p in sorted(work.rglob('*')) if p.is_file()}
        write_json(work / 'manifest.json', {'run_id': run_id, 'identity': identity, 'files': files})
        verify_run(work)
        work.rename(destination)
        return destination


def build(work, accepted, quarantine, dispositions, raw, run_id, hashes):
    silver, gold, evidence = work / 'silver', work / 'gold', work / 'evidence'
    silver.mkdir(); gold.mkdir(); evidence.mkdir()
    for table, records in accepted.items():
        write_json(silver / f'{table}.json', [{'source_row': n, **row} for n, row in records])
    write_json(evidence / 'quarantine.json', quarantine)
    write_json(evidence / 'documents.json', dispositions)
    lineage = []
    partners = []
    partner_lookup = {}
    for table, field, role in [('KNA1', 'KUNNR', 'CUSTOMER'), ('LFA1', 'LIFNR', 'SUPPLIER')]:
        for row_number, row in accepted[table]:
            # Separate namespaces deliberately avoid claiming customer/vendor entity resolution.
            bp = ('C' if role == 'CUSTOMER' else 'S') + row[field]
            partner_lookup[(role, row[field])] = bp
            partners.append({'business_partner_id': bp, 'source_id': row[field], 'role': role,
                             'name': row['NAME1'].strip(), 'country': row['LAND1']})
            lineage.append({'target': 'business_partner', 'target_key': bp,
                            'sources': [reference(table, row_number, hashes)],
                            'mapping': 'BP-1', 'run_id': run_id})
    header_lookup = {doc_key(row): (n, row) for n, row in accepted['BKPF']}
    journal = []
    totals = defaultdict(lambda: {'debit_cents': 0, 'credit_cents': 0, 'lines': 0})
    for n, row in accepted['BSEG']:
        hn, header = header_lookup[doc_key(row)]
        amount = cents(row['WRBTR'])
        signed = amount if row['SHKZG'] == 'S' else -amount
        partner = partner_lookup.get(('CUSTOMER', row['KUNNR'])) if row['KUNNR'] else partner_lookup.get(('SUPPLIER', row['LIFNR']))
        target_key = '/'.join(doc_key(row) + (row['BUZEI'],))
        journal.append({'line_id': target_key, 'company_code': row['BUKRS'], 'document': row['BELNR'],
                        'fiscal_year': row['GJAHR'], 'posting_date': header['BUDAT'],
                        'account': row['HKONT'], 'currency': header['WAERS'],
                        'signed_amount_cents': signed, 'business_partner_id': partner})
        total = totals[(row['BUKRS'], header['WAERS'])]
        total['debit_cents' if signed > 0 else 'credit_cents'] += amount
        total['lines'] += 1
        refs = [reference('BKPF', hn, hashes), reference('BSEG', n, hashes)]
        if partner:
            table, field = ('KNA1', 'KUNNR') if row['KUNNR'] else ('LFA1', 'LIFNR')
            mn = next(index for index, master in accepted[table] if master[field] == row[field])
            refs.append(reference(table, mn, hashes))
        lineage.append({'target': 'journal_staging', 'target_key': target_key, 'sources': refs,
                        'mapping': 'UJ-1', 'run_id': run_id})
    summary = [{'company_code': company, 'currency': currency, **values,
                'net_cents': values['debit_cents'] - values['credit_cents']}
               for (company, currency), values in sorted(totals.items())]
    write_json(gold / 'business_partner.json', partners)
    write_json(gold / 'journal_staging.json', journal)
    write_json(gold / 'financial_summary.json', summary)
    write_json(evidence / 'lineage.json', lineage)
    counts = {table: {'source': len(raw[table]), 'accepted': len(accepted[table]),
                      'quarantined': sum(q['table'] == table for q in quarantine)} for table in SCHEMAS}
    # Monetary reconciliation compares non-zero gross debit/credit, never only net-zero totals.
    monetary = []
    for (company, currency), values in sorted(totals.items()):
        source_totals = {'debit_cents': 0, 'credit_cents': 0}
        for _, row in accepted['BSEG']:
            header = header_lookup[doc_key(row)][1]
            if row['BUKRS'] == company and header['WAERS'] == currency:
                source_totals['debit_cents' if row['SHKZG'] == 'S' else 'credit_cents'] += cents(row['WRBTR'])
        target = [j for j in journal if j['company_code'] == company and j['currency'] == currency]
        target_debit = sum(j['signed_amount_cents'] for j in target if j['signed_amount_cents'] > 0)
        target_credit = -sum(j['signed_amount_cents'] for j in target if j['signed_amount_cents'] < 0)
        monetary.append({'company_code': company, 'currency': currency, 'silver': source_totals,
                         'gold': {'debit_cents': target_debit, 'credit_cents': target_credit},
                         'passed': source_totals == {'debit_cents': target_debit, 'credit_cents': target_credit}})
    controls = {
        'row_conservation': all(c['source'] == c['accepted'] + c['quarantined'] for c in counts.values()),
        'line_conservation': len(journal) == len(accepted['BSEG']),
        'partner_conservation': len(partners) == len(accepted['KNA1']) + len(accepted['LFA1']),
        'gross_amount_reconciliation': all(m['passed'] for m in monetary),
        'document_balance': all(d['debit_cents'] == d['credit_cents'] for d in dispositions if d['status'] == 'ACCEPTED'),
        'no_quarantine': not quarantine,
        'nonempty_batch': bool(journal) and bool(partners),
    }
    ready = all(controls.values())
    reconciliation = {'run_id': run_id, 'status': 'READY' if ready else 'BLOCKED',
                      'controls': controls, 'rows': counts, 'monetary': monetary,
                      'scope': 'Synthetic staging readiness only; no SAP load or cutover approval.'}
    write_json(evidence / 'reconciliation.json', reconciliation)
    # Curated datasets remain inspectable even when the batch gate blocks release.
    write_json(evidence / 'release.json', {'decision': 'ALLOW_STAGING_RELEASE' if ready else 'DENY_STAGING_RELEASE',
               'failed_controls': [k for k, v in controls.items() if not v], 'run_id': run_id})
    database(work / 'warehouse.sqlite', partners, journal, summary)
    from .report import render
    render(work / 'report.html', reconciliation, quarantine, summary, dispositions)


def reference(table, row, hashes):
    return {'file': f'bronze/{table}.csv', 'row': row, 'sha256': hashes[f'{table}.csv']}


def database(path, partners, journal, summary):
    with sqlite3.connect(path) as connection:
        connection.executescript('''
        PRAGMA foreign_keys = ON;
        CREATE TABLE business_partner (business_partner_id TEXT PRIMARY KEY, source_id TEXT, role TEXT, name TEXT, country TEXT);
        CREATE TABLE journal_staging (line_id TEXT PRIMARY KEY, company_code TEXT, document TEXT, fiscal_year TEXT,
          posting_date TEXT, account TEXT, currency TEXT, signed_amount_cents INTEGER,
          business_partner_id TEXT REFERENCES business_partner(business_partner_id));
        CREATE TABLE financial_summary (company_code TEXT, currency TEXT, debit_cents INTEGER, credit_cents INTEGER,
          lines INTEGER, net_cents INTEGER, PRIMARY KEY(company_code, currency));
        ''')
        for table, rows in [('business_partner', partners), ('journal_staging', journal), ('financial_summary', summary)]:
            if rows:
                columns = ','.join(rows[0])
                placeholders = ','.join('?' for _ in rows[0])
                connection.executemany(f'INSERT INTO {table} ({columns}) VALUES ({placeholders})', [tuple(row.values()) for row in rows])
