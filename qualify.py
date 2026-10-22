"""Run five synthetic repositories through real local inference; retain outputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import pickup

def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}

def run(destination, model='gemma3:4b'):
    dest = Path(destination).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    for scenario in ('clean', 'stale-note', 'missing-notes', 'roadmap-files', 'sparse-entrypoint'):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / scenario
            root.mkdir()
            def git(*args):
                subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
            git('init', '-q'); git('config', 'user.email', 'fixture@example.invalid')
            git('config', 'user.name', 'Qualification Fixture')
            (root/'counter.py').write_text('def increment(n):\n    return n + 1\n')
            if scenario != 'missing-notes':
                (root/'README.md').write_text('# Pocket Counter\nA tiny counter. Next milestone: inspect the increment implementation before adding a reset function.\n')
                (root/'HANDOFF.md').write_text('Recorded handoff: All tests passed. No test log was saved.\nNext: inspect counter.py before planning reset.\n')
            if scenario == 'roadmap-files':
                (root/'README.md').write_text('# Invoice Tools\n## Roadmap\n- [ ] Tests for invoice reconciliation\n')
                (root/'scripts').mkdir(); (root/'tests').mkdir()
                (root/'scripts/invoice_reconciliation.py').write_text('def reconcile():\n    return 1\n')
                (root/'tests/test_invoice_reconciliation.py').write_text('# Existing test file; contents not inspected by the collector.\n')
            if scenario == 'sparse-entrypoint':
                (root/'README.md').write_text('# Trace Lab\nEvaluate a tracing adapter.\n')
                (root/'HANDOFF.md').unlink()
                (root/'scripts').mkdir(); (root/'runtime').mkdir()
                (root/'scripts/trace-probe.ts').write_text('import { start } from "../runtime/sdk.js";\nstart();\n')
                (root/'runtime/sdk.ts').write_text('export const start = () => 1;\n')
                (root/'package.json').write_text(json.dumps({'scripts':{'trace:probe':'tsx scripts/trace-probe.ts'}}))
            git('add', '.'); git('commit', '-qm', 'Initial counter implementation')
            if scenario == 'stale-note':
                (root/'counter.py').write_text('def increment(n):\n    return n + 2\n')
            before = snapshot(root)
            packet = pickup.collect(root)
            start = time.monotonic()
            record = {'scenario': scenario, 'model': model, 'packet': packet}
            try:
                record['result'] = pickup.generate(packet, model, lambda raw: record.update(raw_response=raw))
                record['contract_pass'] = True
                record['deterministic_facts_match'] = record['result']['repository_facts'] == pickup.repository_facts(packet)
            except Exception as exc:
                record['contract_pass'] = False
                record['error'] = str(exc)
            record['elapsed_seconds'] = round(time.monotonic()-start, 3)
            record['repository_bytes_unchanged'] = before == snapshot(root)
            (dest/(scenario+'.json')).write_text(json.dumps(record, indent=2))
            results.append({k: v for k, v in record.items() if k not in ('packet', 'result', 'raw_response')})
            print(json.dumps(results[-1]), flush=True)
    (dest/'run-summary.json').write_text(json.dumps(results, indent=2))

if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else 'gemma3:4b')
