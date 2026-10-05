"""CLI entry point and one-command three-scenario demonstration."""
import argparse
import json
from pathlib import Path
from .pipeline import run
from .source import generate
from .storage import verify_run


def main(argv=None):
    parser = argparse.ArgumentParser(description='Abyss Medallion: synthetic ERP data, explicit staging controls')
    commands = parser.add_subparsers(dest='command', required=True)
    demo = commands.add_parser('demo', help='Run clean, defective and repaired scenarios')
    demo.add_argument('--output', type=Path, default=Path('runs'))
    execute = commands.add_parser('run', help='Process extracts; exit 2 when release is blocked')
    execute.add_argument('--source', type=Path, required=True)
    execute.add_argument('--output', type=Path, default=Path('runs'))
    fixture = commands.add_parser('generate', help='Generate synthetic extracts')
    fixture.add_argument('--scenario', choices=['clean', 'defective', 'repaired'], default='clean')
    fixture.add_argument('--destination', type=Path, required=True)
    verify = commands.add_parser('verify', help='Verify a run against its local manifest')
    verify.add_argument('directory', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'generate':
            generate(args.destination, args.scenario)
            return 0
        if args.command == 'verify':
            verify_run(args.directory)
            print('PASS: all run files match the local manifest')
            return 0
        if args.command == 'run':
            destination = run(args.source, args.output)
            result = json.loads((destination / 'evidence/reconciliation.json').read_text())
            print(f"{result['status']}: {destination / 'report.html'}")
            return 0 if result['status'] == 'READY' else 2
        print('\nABYSS MEDALLION\nSynthetic ERP data. Evidence before release.\n')
        outcomes = []
        for scenario in ['clean', 'defective', 'repaired']:
            source = args.output / '_sources' / scenario
            generate(source, scenario)
            destination = run(source, args.output / 'batches')
            result = json.loads((destination / 'evidence/reconciliation.json').read_text())
            rejected = sum(v['quarantined'] for v in result['rows'].values())
            print(f"{scenario.upper():12} {result['status']:8} {rejected:2} quarantined rows")
            outcomes.append((scenario, result['status'], destination))
        expected = ['READY', 'BLOCKED', 'READY']
        if [status for _, status, _ in outcomes] != expected:
            raise ValueError('Scenario results differ from the demonstration contract')
        links = '\n'.join(f'<li><a href="{destination.relative_to(args.output)}/report.html">{scenario}: {status}</a></li>' for scenario, status, destination in outcomes)
        (args.output / 'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Abyss Medallion runs</title><body style="font:20px system-ui;background:#0b1220;color:#edf3fa;padding:3rem"><h1>Abyss Medallion</h1><p>Clean → defective → repaired. Open a report to inspect its evidence.</p><ul>' + links + '</ul></body></html>')
        print(f'\nReports: {args.output.resolve() / "index.html"}')
        print('PASS: defective batch blocked; corrected extract reconciled; original evidence retained.')
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f'ERROR: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
