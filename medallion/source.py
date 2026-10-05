"""Deterministic ECC-like extracts, including intentionally defective batches."""
import csv
from pathlib import Path

SCHEMAS = {
    'KNA1': ['KUNNR', 'NAME1', 'LAND1'],
    'LFA1': ['LIFNR', 'NAME1', 'LAND1'],
    'BKPF': ['BUKRS', 'BELNR', 'GJAHR', 'BUDAT', 'WAERS'],
    'BSEG': ['BUKRS', 'BELNR', 'GJAHR', 'BUZEI', 'HKONT', 'SHKZG', 'WRBTR', 'KUNNR', 'LIFNR'],
}

def generate(destination: Path, scenario: str) -> None:
    """Write a repeatable fixture. 'repaired' represents a corrected new extract."""
    if scenario not in ('clean', 'defective', 'repaired'):
        raise ValueError(f'Unknown scenario: {scenario}')
    destination.mkdir(parents=True, exist_ok=True)
    tables = {
        'KNA1': [['0000001001', 'Aster Clinic', 'US'], ['0000001002', 'Beacon Labs', 'US']],
        'LFA1': [['0000002001', 'Cedar Supply', 'US']],
        'BKPF': [], 'BSEG': [],
    }
    for i, (currency, amount, customer, supplier) in enumerate([
        ('USD', '1250.50', '0000001001', ''),
        ('USD', '399.99', '0000001002', ''),
        ('EUR', '875.25', '', '0000002001'),
        ('USD', '210.10', '0000001001', ''),
        ('USD', '90.00', '0000001001', ''),
    ], 1):
        key = ['1000', f'{i:010}', '2026']
        tables['BKPF'].append(key + ['20261001', currency])
        tables['BSEG'].extend([
            key + ['001', '0000140000', 'S', amount, customer, supplier],
            key + ['002', '0000400000', 'H', amount, '', ''],
        ])
    if scenario == 'defective':
        tables['KNA1'].append(['0000001002', 'Conflicting legal name', 'US'])
        tables['BKPF'][2][-1] = 'ZZZ'
        tables['BSEG'][1][6] = '1250.49'  # one-cent imbalance; whole document rejected
        tables['BSEG'][6][7] = '9999999999'  # unknown customer
        tables['BSEG'].append(['1000', '9999999999', '2026', '001', '0000140000', 'S', '5.00', '', ''])
    for table, rows in tables.items():
        with (destination / f'{table}.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream, lineterminator='\n')
            writer.writerow(SCHEMAS[table])
            writer.writerows(rows)


def read_extracts(directory: Path) -> dict[str, list[dict[str, str]]]:
    """Strict contract: reject missing/extra files and changed columns before processing."""
    expected = {f'{table}.csv' for table in SCHEMAS}
    actual = {p.name for p in directory.iterdir() if p.is_file()}
    if actual != expected:
        raise ValueError(f'Extract file contract mismatch: expected {sorted(expected)}, got {sorted(actual)}')
    result = {}
    for table, columns in SCHEMAS.items():
        with (directory / f'{table}.csv').open(newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != columns:
                raise ValueError(f'{table}: schema drift; expected {columns}')
            rows = list(reader)
            if any(None in row or any(value is None for value in row.values()) for row in rows):
                raise ValueError(f'{table}: malformed CSV row')
            result[table] = rows
    return result
