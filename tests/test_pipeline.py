"""Behavior and negative controls, using isolated sources and output directories."""
import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from medallion.cli import main
from medallion.pipeline import run
from medallion.quality import cents
from medallion.source import generate
from medallion.storage import verify_run


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        generate(self.source, 'clean')

    def execute(self):
        return run(self.source, self.root / 'runs')

    def load(self, directory, name):
        return json.loads((directory / name).read_text())

    def mutate(self, table, operation):
        path = self.source / f'{table}.csv'
        with path.open(newline='') as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            rows = list(reader)
        operation(rows)
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)

    def test_clean_batch_reconciles_gross_amounts_and_currency(self):
        directory = self.execute()
        result = self.load(directory, 'evidence/reconciliation.json')
        self.assertEqual(result['status'], 'READY')
        self.assertTrue(all(result['controls'].values()))
        amounts = {m['currency']: m for m in result['monetary']}
        self.assertEqual(amounts['USD']['gold'], {'debit_cents': 195059, 'credit_cents': 195059})
        self.assertEqual(amounts['EUR']['gold'], {'debit_cents': 87525, 'credit_cents': 87525})
        with sqlite3.connect(directory / 'warehouse.sqlite') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM journal_staging').fetchone()[0], 10)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_defective_batch_blocks_release_and_conserves_every_row(self):
        generate(self.source, 'defective')
        directory = self.execute()
        result = self.load(directory, 'evidence/reconciliation.json')
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertTrue(result['controls']['row_conservation'])
        self.assertEqual(sum(c['quarantined'] for c in result['rows'].values()), 15)
        reasons = {r for q in self.load(directory, 'evidence/quarantine.json') for r in q['reasons']}
        self.assertTrue({'DUPLICATE_MASTER_ID', 'UNKNOWN_CUSTOMER', 'UNKNOWN_CURRENCY', 'UNBALANCED_DOCUMENT', 'MISSING_HEADER'} <= reasons)
        self.assertEqual(len(self.load(directory, 'gold/journal_staging.json')), 2)

    def test_one_cent_imbalance_rejects_whole_document(self):
        self.mutate('BSEG', lambda rows: rows[1].update(WRBTR='1250.49'))
        directory = self.execute()
        rejected = self.load(directory, 'evidence/quarantine.json')
        self.assertEqual(len(rejected), 3)  # header and BOTH lines
        self.assertTrue(all('UNBALANCED_DOCUMENT' in q['reasons'] for q in rejected))
        self.assertEqual(len(self.load(directory, 'gold/journal_staging.json')), 8)

    def test_duplicate_line_is_not_silently_deduplicated(self):
        self.mutate('BSEG', lambda rows: rows.append(dict(rows[0])))
        directory = self.execute()
        self.assertTrue(any('DUPLICATE_LINE' in q['reasons'] for q in self.load(directory, 'evidence/quarantine.json')))
        self.assertEqual(self.load(directory, 'evidence/release.json')['decision'], 'DENY_STAGING_RELEASE')

    def test_invalid_amounts_never_round_or_become_floats(self):
        for value in ['NaN', 'Infinity', '-1', '0', '1.001', 'garbage']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                cents(value)
        self.assertEqual(cents('399.99'), 39999)
        self.mutate('BSEG', lambda rows: rows[0].update(WRBTR='NaN'))
        directory = self.execute()
        self.assertEqual(self.load(directory, 'evidence/reconciliation.json')['status'], 'BLOCKED')

    def test_missing_header_quarantines_orphan_without_crashing(self):
        self.mutate('BKPF', lambda rows: rows.pop(0))
        directory = self.execute()
        self.assertTrue(any('MISSING_HEADER' in q['reasons'] for q in self.load(directory, 'evidence/quarantine.json')))

    def test_schema_drift_and_extra_files_fail_before_publication(self):
        path = self.source / 'BKPF.csv'
        original = path.read_text()
        path.write_text(original.replace('WAERS', 'CURRENCY'))
        with self.assertRaisesRegex(ValueError, 'schema drift'):
            self.execute()
        path.write_text(original)
        (self.source / 'unexpected.csv').write_text('x\n')
        with self.assertRaisesRegex(ValueError, 'file contract'):
            self.execute()
        self.assertEqual(list((self.root / 'runs').iterdir()), [])

    def test_rerun_is_idempotent_and_bronze_is_byte_exact(self):
        first = self.execute()
        before = (first / 'manifest.json').read_bytes()
        self.assertEqual(first, self.execute())
        self.assertEqual(before, (first / 'manifest.json').read_bytes())
        for path in self.source.glob('*.csv'):
            self.assertEqual(path.read_bytes(), (first / 'bronze' / path.name).read_bytes())

    def test_tampered_gold_is_detected_and_not_overwritten(self):
        directory = self.execute()
        target = directory / 'gold/journal_staging.json'
        target.write_text('[]\n')
        with self.assertRaisesRegex(ValueError, 'integrity failure'):
            verify_run(directory)
        with self.assertRaisesRegex(ValueError, 'integrity failure'):
            self.execute()
        self.assertEqual(target.read_text(), '[]\n')

    def test_missing_and_added_artifacts_are_detected(self):
        directory = self.execute()
        extra = directory / 'extra.txt'
        extra.write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'file set'):
            verify_run(directory)
        extra.unlink()
        (directory / 'evidence/lineage.json').unlink()
        with self.assertRaisesRegex(ValueError, 'file set'):
            verify_run(directory)

    def test_lineage_resolves_to_exact_source_rows_and_hashes(self):
        import hashlib
        directory = self.execute()
        lineage = self.load(directory, 'evidence/lineage.json')
        self.assertEqual(len(lineage), 13)
        journal = {j['line_id']: j for j in self.load(directory, 'gold/journal_staging.json')}
        for entry in lineage:
            for ref in entry['sources']:
                path = directory / ref['file']
                self.assertEqual(ref['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
                with path.open(newline='') as stream:
                    rows = list(csv.DictReader(stream))
                row = rows[ref['row'] - 2]
                if entry['target'] == 'journal_staging' and 'BSEG' in ref['file']:
                    target = journal[entry['target_key']]
                    self.assertEqual(target['account'], row['HKONT'])
                    self.assertEqual(abs(target['signed_amount_cents']), cents(row['WRBTR']))

    def test_repair_creates_new_batch_and_preserves_rejected_evidence(self):
        generate(self.source, 'defective')
        bad = self.execute()
        before = (bad / 'manifest.json').read_bytes()
        generate(self.source, 'repaired')
        good = self.execute()
        self.assertNotEqual(good, bad)
        self.assertEqual(self.load(good, 'evidence/reconciliation.json')['status'], 'READY')
        self.assertEqual(self.load(bad, 'evidence/reconciliation.json')['status'], 'BLOCKED')
        self.assertEqual((bad / 'manifest.json').read_bytes(), before)
        verify_run(bad)

    def test_empty_batch_is_blocked(self):
        for table in ['KNA1', 'LFA1', 'BKPF', 'BSEG']:
            self.mutate(table, lambda rows: rows.clear())
        directory = self.execute()
        self.assertFalse(self.load(directory, 'evidence/reconciliation.json')['controls']['nonempty_batch'])

    def test_cli_returns_nonzero_for_blocked_batch(self):
        generate(self.source, 'defective')
        self.assertEqual(main(['run', '--source', str(self.source), '--output', str(self.root / 'runs')]), 2)

    def test_html_escapes_source_values(self):
        self.mutate('BKPF', lambda rows: rows[0].update(BELNR='<script>'))
        directory = self.execute()
        html = (directory / 'report.html').read_text()
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_partner_namespaces_remain_distinct(self):
        self.mutate('LFA1', lambda rows: rows[0].update(LIFNR='0000001001'))
        self.mutate('BSEG', lambda rows: [row.update(LIFNR='0000001001') for row in rows if row['LIFNR']])
        directory = self.execute()
        ids = {p['business_partner_id'] for p in self.load(directory, 'gold/business_partner.json')}
        self.assertTrue({'C0000001001', 'S0000001001'} <= ids)

    def test_duplicate_headers_reject_entire_document(self):
        self.mutate('BKPF', lambda rows: rows.append(dict(rows[0])))
        directory = self.execute()
        rejected = self.load(directory, 'evidence/quarantine.json')
        self.assertEqual(len(rejected), 4)
        self.assertTrue(all('DUPLICATE_HEADER' in q['reasons'] for q in rejected))

    def test_unknown_master_country_blocks_dependent_document(self):
        self.mutate('KNA1', lambda rows: rows[1].update(LAND1='XX'))
        directory = self.execute()
        rejected = self.load(directory, 'evidence/quarantine.json')
        self.assertTrue(any('UNKNOWN_COUNTRY' in q['reasons'] for q in rejected))
        self.assertTrue(any('UNKNOWN_CUSTOMER' in q['reasons'] for q in rejected))

    def test_invalid_date_and_direction_are_visible(self):
        self.mutate('BKPF', lambda rows: rows[0].update(BUDAT='20260230'))
        self.mutate('BSEG', lambda rows: rows[0].update(SHKZG='X'))
        directory = self.execute()
        reasons = {reason for q in self.load(directory, 'evidence/quarantine.json') for reason in q['reasons']}
        self.assertTrue({'INVALID_POSTING_DATE', 'INVALID_DEBIT_CREDIT'} <= reasons)

    def test_failure_during_build_publishes_nothing(self):
        from unittest.mock import patch
        with patch('medallion.pipeline.database', side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):
                self.execute()
        self.assertEqual(list((self.root / 'runs').iterdir()), [])

    def test_malformed_csv_is_not_published(self):
        path = self.source / 'KNA1.csv'
        path.write_text(path.read_text() + 'too,many,columns,here\n')
        with self.assertRaisesRegex(ValueError, 'malformed CSV'):
            self.execute()
