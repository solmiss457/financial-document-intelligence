"""Local S1 feasibility probe; never treats detected tables as verified facts."""
import hashlib
import json
import platform
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/pdf-probe'


def compact(value):
    return ''.join((value or '').split())


def run():
    manifest = json.loads((ROOT / 'eval/manifests/s1_reports.json').read_text())
    cases = json.loads((ROOT / 'eval/configs/pdf_probe.json').read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for source in manifest:
        path = ROOT / source['local_path']
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != source['sha256']:
            raise ValueError(f"Hash mismatch: {source['document_id']}")
        with pymupdf.open(path) as doc:
            if len(doc) != source['page_count']:
                raise ValueError('Page count mismatch')
            # Text and coordinates stay in ignored local artifacts, never stdout.
            with (OUT / f"{source['document_id']}-pages.jsonl").open('w') as stream:
                for i, page in enumerate(doc):
                    stream.write(json.dumps({'page': i + 1, 'text': page.get_text(),
                                             'words': page.get_text('words')}) + '\n')
            for case in cases:
                if case['document_id'] != source['document_id']:
                    continue
                page = doc[case['pdf_page'] - 1]
                page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(OUT / f"{case['id']}.png")
                text = compact(page.get_text())
                for strategy in ('lines', 'text'):
                    finder = page.find_tables(strategy=strategy)
                    tables = [{'bbox': list(t.bbox), 'cells': t.cells,
                               'rows': t.extract()} for t in finder.tables]
                    (OUT / f"{case['id']}-{strategy}.json").write_text(json.dumps(tables, indent=2))
                    rows = [compact(' '.join(v or '' for v in row)) for t in tables for row in t['rows']]
                    checks = {
                        'page_years': all(y in text for y in case['years']),
                        'page_unit': compact(case['unit']) in text,
                        'page_label': compact(case['printed_page']) in text,
                        'table_year_header': any(all(y in r for y in case['years']) for r in rows),
                        'table_unit': any(compact(case['unit']) in r for r in rows),
                    }
                    for anchor in case['anchors']:
                        values = [compact(v) for v in anchor['values']]
                        label = compact(anchor['row'])
                        # Order as well as row association is checked; no number normalization.
                        matching = [r for r in rows if label in r]
                        checks[anchor['id']] = any(
                            all(v in r for v in values) and
                            [r.find(v) for v in values] == sorted(r.find(v) for v in values)
                            for r in matching)
                    results.append({'case': case['id'], 'strategy': strategy,
                                    'tables': len(tables), 'shapes': [[len(t['rows']), len(t['rows'][0])] for t in tables],
                                    'checks': checks})
    summary = {'python': platform.python_version(), 'pymupdf': pymupdf.VersionBind,
               'platform': platform.platform(), 'results': results,
               'note': 'Anchor checks only; visual review required. Not an extraction accuracy metric.'}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    run()
