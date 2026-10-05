"""Deterministic validation. Money is integer cents; invalid documents are indivisible."""
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

COUNTRIES = {'US', 'CA', 'DE'}  # deliberately bounded demo reference data
CURRENCIES = {'USD', 'EUR'}

def cents(value: str) -> int:
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal('.01')):
            raise ValueError('Money must be positive, finite and have at most two decimal places')
        return int(amount * 100)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'Invalid monetary amount: {value!r}') from exc


def doc_key(row: dict) -> tuple:
    return row['BUKRS'], row['BELNR'], row['GJAHR']


def validate(tables: dict) -> tuple[dict, list[dict], list[dict]]:
    """Return accepted rows, quarantine rows with all reasons, and document dispositions."""
    accepted = {name: [] for name in tables}
    quarantine = []
    masters = {}
    for table, field in [('KNA1', 'KUNNR'), ('LFA1', 'LIFNR')]:
        counts = Counter(row[field] for row in tables[table])
        masters[table] = set()
        for index, row in enumerate(tables[table], 2):
            reasons = []
            if not row[field].isdigit() or len(row[field]) != 10:
                reasons.append('INVALID_MASTER_ID')
            if counts[row[field]] != 1:
                reasons.append('DUPLICATE_MASTER_ID')
            if not row['NAME1'].strip():
                reasons.append('MISSING_NAME')
            if row['LAND1'] not in COUNTRIES:
                reasons.append('UNKNOWN_COUNTRY')
            if reasons:
                quarantine.append({'table': table, 'source_row': index, 'reasons': reasons, 'row': row})
            else:
                accepted[table].append((index, row))
                masters[table].add(row[field])
    headers, lines = defaultdict(list), defaultdict(list)
    for index, row in enumerate(tables['BKPF'], 2):
        headers[doc_key(row)].append((index, row))
    for index, row in enumerate(tables['BSEG'], 2):
        lines[doc_key(row)].append((index, row))
    dispositions = []
    for key in sorted(set(headers) | set(lines)):
        h, items = headers[key], lines[key]
        reasons = set()
        if len(h) != 1:
            reasons.add('MISSING_HEADER' if not h else 'DUPLICATE_HEADER')
        if not (key[0].isdigit() and len(key[0]) == 4 and key[1].isdigit() and len(key[1]) == 10 and key[2].isdigit() and len(key[2]) == 4):
            reasons.add('INVALID_DOCUMENT_KEY')
        for _, header in h:
            if header['WAERS'] not in CURRENCIES:
                reasons.add('UNKNOWN_CURRENCY')
            try:
                date = datetime.strptime(header['BUDAT'], '%Y%m%d')
                if date.strftime('%Y%m%d') != header['BUDAT'] or str(date.year) != header['GJAHR']:
                    reasons.add('INVALID_POSTING_DATE')
            except ValueError:
                reasons.add('INVALID_POSTING_DATE')
        if len(items) < 2:
            reasons.add('INSUFFICIENT_LINES')
        line_counts = Counter(row['BUZEI'] for _, row in items)
        debit = credit = 0
        for _, row in items:
            if not row['BUZEI'].isdigit() or len(row['BUZEI']) != 3 or row['BUZEI'] == '000':
                reasons.add('INVALID_LINE_NUMBER')
            if line_counts[row['BUZEI']] != 1:
                reasons.add('DUPLICATE_LINE')
            if not row['HKONT'].isdigit() or len(row['HKONT']) != 10:
                reasons.add('INVALID_ACCOUNT')
            if row['SHKZG'] not in {'S', 'H'}:
                reasons.add('INVALID_DEBIT_CREDIT')
            if row['KUNNR'] and row['KUNNR'] not in masters['KNA1']:
                reasons.add('UNKNOWN_CUSTOMER')
            if row['LIFNR'] and row['LIFNR'] not in masters['LFA1']:
                reasons.add('UNKNOWN_SUPPLIER')
            if row['KUNNR'] and row['LIFNR']:
                reasons.add('AMBIGUOUS_PARTNER')
            try:
                amount = cents(row['WRBTR'])
                if row['SHKZG'] == 'S':
                    debit += amount
                elif row['SHKZG'] == 'H':
                    credit += amount
            except ValueError:
                reasons.add('INVALID_AMOUNT')
        if debit != credit:
            reasons.add('UNBALANCED_DOCUMENT')
        dispositions.append({'key': list(key), 'status': 'REJECTED' if reasons else 'ACCEPTED',
                             'reasons': sorted(reasons), 'debit_cents': debit, 'credit_cents': credit})
        for table, records in [('BKPF', h), ('BSEG', items)]:
            for index, row in records:
                if reasons:
                    quarantine.append({'table': table, 'source_row': index, 'reasons': sorted(reasons), 'row': row})
                else:
                    accepted[table].append((index, row))
    return accepted, quarantine, dispositions
