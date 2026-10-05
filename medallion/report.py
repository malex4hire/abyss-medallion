"""Self-contained, escaped HTML evidence report; no CDN, server or external assets."""
from html import escape
from pathlib import Path


def render(path: Path, reconciliation: dict, quarantine: list, summary: list, documents: list) -> None:
    def table(headers, rows):
        heading = ''.join(f'<th>{escape(str(h))}</th>' for h in headers)
        body = ''.join('<tr>' + ''.join(f'<td>{escape(str(cell))}</td>' for cell in row) + '</tr>' for row in rows)
        return f'<div class="scroll"><table><thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table></div>'
    status = reconciliation['status']
    controls = table(['Control', 'Result'], [(k.replace('_', ' ').title(), 'PASS' if v else 'FAIL') for k, v in reconciliation['controls'].items()])
    counts = table(['Extract', 'Bronze', 'Silver', 'Quarantine'], [(k, v['source'], v['accepted'], v['quarantined']) for k, v in reconciliation['rows'].items()])
    amounts = table(['Company', 'Currency', 'Debit', 'Credit', 'Net', 'Lines'],
                   [(s['company_code'], s['currency'], f"{s['debit_cents']/100:,.2f}", f"{s['credit_cents']/100:,.2f}", f"{s['net_cents']/100:,.2f}", s['lines']) for s in summary])
    errors = table(['Extract / CSV row', 'Reasons'], [(f"{q['table']} / {q['source_row']}", ', '.join(q['reasons'])) for q in quarantine]) if quarantine else '<p>No rejected rows.</p>'
    docs = table(['Document', 'Disposition', 'Reasons'], [('/'.join(d['key']), d['status'], ', '.join(d['reasons']) or 'Balanced and valid') for d in documents])
    path.write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Abyss Medallion · Evidence</title><style>
:root{{color-scheme:dark;--bg:#0b1220;--panel:#121e30;--text:#edf3fa;--muted:#9fb0c8;--accent:#53d4d1}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:48px 24px}}header{{border-bottom:1px solid #30425b;padding-bottom:28px}}.eyebrow{{color:var(--accent);letter-spacing:.16em;font-size:12px;font-weight:700}}h1{{font-size:clamp(30px,5vw,54px);line-height:1.15;margin:12px 0}}h2{{font-size:23px}}p{{color:var(--muted)}}.badge{{display:inline-block;padding:7px 16px;border:1px solid {'#53d4d1' if status == 'READY' else '#ffb86b'};border-radius:30px;color:{'#53d4d1' if status == 'READY' else '#ffb86b'};font-weight:700}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin:28px 0}}.card,section{{background:var(--panel);border:1px solid #253751;border-radius:12px;padding:22px;margin-bottom:20px}}.card strong{{display:block;font-size:24px}}.card p{{margin-bottom:0}}.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:14px;text-align:left}}th{{color:var(--muted);font-weight:600}}td,th{{padding:12px 10px;border-bottom:1px solid #253751;vertical-align:top}}code{{overflow-wrap:anywhere;font-size:12px;color:var(--muted)}}a{{color:var(--accent)}}footer{{margin-top:30px;color:var(--muted);font-size:13px}}
</style></head><body><main><header><div class="eyebrow">ABYSS APPLIED / EXECUTABLE REFERENCE ARCHITECTURE</div><h1>Preserve. Validate. Reconcile.</h1><p>Synthetic ERP data · Medallion layers · S/4HANA-oriented staging</p><span class="badge">{status} · staging release</span><p>Batch fingerprint <code>{reconciliation['run_id']}</code></p></header>
<div class="grid"><div class="card"><strong>Bronze</strong><p>Exact CSV snapshot. File digests preserve the connection to evidence.</p></div><div class="card"><strong>Silver</strong><p>Validated identities and whole accounting documents. Explicit quarantine.</p></div><div class="card"><strong>Gold</strong><p>Illustrative partners, signed journal lines and per-currency summaries.</p></div></div>
<section><h2>Release controls</h2>{controls}<p>Passing reconciliation does not waive rejected records. Any quarantine blocks the batch.</p></section>
<section><h2>Every source row has a disposition</h2>{counts}</section><section><h2>Financial evidence</h2>{amounts}<p>Gross debit and credit are reconciled separately by company and currency. Currencies are never added together.</p></section>
<section><h2>Document decisions</h2>{docs}</section><section><h2>Quarantine</h2>{errors}</section>
<section><h2>Inspect the evidence</h2><p><a href="evidence/reconciliation.json">Reconciliation</a> · <a href="evidence/lineage.json">Record lineage</a> · <a href="evidence/quarantine.json">Rejected source rows</a> · <a href="manifest.json">SHA-256 manifest</a></p><p>Evidence links work when opening this report from its extracted run directory.</p></section>
<footer>Demonstrates data engineering and controls using synthetic SAP ECC-like fields. No SAP connection, certified migration tooling, real CVI conversion, complete ACDOCA model or production migration experience is claimed.</footer></main></body></html>''', encoding='utf-8')
