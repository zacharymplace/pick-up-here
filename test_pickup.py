import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import pickup

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.g("init", "-q")
        self.g("config", "user.email", "fixture@example.invalid")
        self.g("config", "user.name", "Fixture")
        (self.root/"README.md").write_text("# Example\nBuild a tiny counter.\n")
        self.g("add", ".")
        self.g("commit", "-qm", "Initial fixture")
    def tearDown(self): self.tmp.cleanup()
    def g(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)
    def test_clean(self):
        packet = pickup.collect(self.root)
        self.assertEqual(packet["evidence"][1]["text"], "")
        self.assertIn("1: # Example", packet["evidence"][3]["text"])
    def test_stale_claim_is_preserved_as_evidence_not_test_result(self):
        (self.root/"HANDOFF.md").write_text("All tests passed.\n")
        self.g("add", "."); self.g("commit", "-qm", "Handoff")
        (self.root/"counter.py").write_text("broken\n")
        packet = pickup.collect(self.root)
        self.assertIn("counter.py", packet["evidence"][1]["text"])
        self.assertIn("No tests executed", packet["limits"])
        self.assertIn("All tests passed", next(e['text'] for e in packet['evidence'] if e['source']=='HANDOFF.md'))
    def test_missing_notes(self):
        (self.root/"README.md").unlink()
        packet = pickup.collect(self.root)
        self.assertEqual(len(packet['evidence']), 5)
        self.assertEqual(set(packet['note_inventory'].values()), {'missing'})
        inventory = next(e for e in packet['evidence'] if e['source']=='collection:notes')
        self.assertIn('handoff context is missing', inventory['text'])
    def test_partial_notes_inventory(self):
        packet = pickup.collect(self.root)
        self.assertEqual(packet['note_inventory']['README.md'], 'collected')
        self.assertEqual(packet['note_inventory']['HANDOFF.md'], 'missing')
        self.assertIn('Collected 1 nonempty', next(e['text'] for e in packet['evidence'] if e['source']=='collection:notes'))
    def test_collection_preserves_repository_bytes(self):
        def snapshot():
            return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        before = snapshot()
        pickup.collect(self.root)
        self.assertEqual(before, snapshot())
    def test_empty_notes_are_not_handoff_context(self):
        (self.root/'README.md').write_text(' \n')
        packet = pickup.collect(self.root)
        self.assertEqual(packet['note_inventory']['README.md'], 'empty')
        self.assertIn('No readable nonempty', next(e['text'] for e in packet['evidence'] if e['source']=='collection:notes'))
    def test_oversize_notes_distinguished_from_missing(self):
        (self.root/'README.md').write_text('a'*64001)
        packet = pickup.collect(self.root)
        self.assertEqual(packet['note_inventory']['README.md'], 'skipped_size_limit')
        self.assertIn('No readable nonempty', next(e['text'] for e in packet['evidence'] if e['source']=='collection:notes'))
    def test_secret_and_symlink_excluded(self):
        (self.root/".env").write_text("SECRET=never-include")
        (self.root/"HANDOFF.md").symlink_to(self.root/".env")
        self.assertNotIn("never-include", json.dumps(pickup.collect(self.root)))
        self.assertEqual(pickup.collect(self.root)['note_inventory']['HANDOFF.md'], 'skipped_symlink')
    def test_reject_unknown_citation(self):
        brief = self.selection()
        brief['next_action']['evidence'] = 'E999'
        with self.assertRaisesRegex(ValueError, 'Unsupported next_action'): pickup.validate(brief, pickup.collect(self.root))
    def selection(self):
        return {'interpretations': [{'focus': 'review_notes', 'evidence': 'E4'}], 'next_action': {'kind': 'review_history', 'evidence': 'E3'}}
    def test_reject_multiple_actions(self):
        brief = self.selection()
        brief['next_action'] = [brief['next_action']]*2
        with self.assertRaisesRegex(ValueError, 'next_action'): pickup.validate(brief, pickup.collect(self.root))
    def test_reject_empty_section(self):
        brief = self.selection()
        brief['interpretations'] = []
        with self.assertRaisesRegex(ValueError, 'count'): pickup.validate(brief, pickup.collect(self.root))
    def test_valid_citation(self):
        brief = self.selection()
        self.assertEqual(pickup.validate(brief, pickup.collect(self.root)), brief)
    def test_model_cannot_supply_facts(self):
        brief = self.selection()
        brief['repository_facts'] = {'working_tree': 'changed'}
        with self.assertRaisesRegex(ValueError, 'facts are forbidden'): pickup.assemble(pickup.collect(self.root), brief)
    def test_reject_changed_focus_on_clean_tree(self):
        brief = self.selection()
        brief['interpretations'] = [{'focus': 'review_changes', 'evidence': 'E2'}]
        with self.assertRaisesRegex(ValueError, 'Unsupported interpretive'): pickup.validate(brief, pickup.collect(self.root))
    def test_reject_missing_context_when_notes_exist(self):
        packet = pickup.collect(self.root)
        brief = self.selection()
        brief['interpretations'] = [{'focus': 'missing_handoff_context', 'evidence': packet['evidence'][-1]['id']}]
        with self.assertRaisesRegex(ValueError, 'Unsupported interpretive'): pickup.validate(brief, packet)
    def test_reject_model_prose_or_path(self):
        brief = self.selection()
        brief['next_action']['path'] = 'HOFF.md'
        with self.assertRaisesRegex(ValueError, 'Unsupported next_action'): pickup.validate(brief, pickup.collect(self.root))
    def test_facts_identical_across_different_model_selections(self):
        packet = pickup.collect(self.root)
        first = self.selection()
        second = self.selection()
        second['next_action'] = {'kind': 'read_note', 'evidence': 'E4'}
        a, b = pickup.assemble(packet, first), pickup.assemble(packet, second)
        self.assertEqual(a['repository_facts'], b['repository_facts'])
        self.assertEqual(a['repository_facts']['working_tree']['state'], 'clean')
        self.assertIn('README.md', b['ai_interpretation']['proposed_next_action']['text'])
        self.assertFalse(b['ai_interpretation']['proposed_next_action']['executed'])
    def test_missing_notes_are_deterministic_facts(self):
        (self.root/'README.md').unlink()
        packet = pickup.collect(self.root)
        brief = {'interpretations': [{'focus': 'missing_handoff_context', 'evidence': 'E4'}], 'next_action': {'kind': 'review_history', 'evidence': 'E3'}}
        self.assertEqual(pickup.assemble(packet, brief)['repository_facts']['notes']['context'], 'missing_from_packet')
    def test_non_repository_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaises(ValueError): pickup.collect(path)
    def test_facts_only_cli_requires_no_model(self):
        result = subprocess.run([sys.executable, str(Path(pickup.__file__)), str(self.root), '--facts-only', '--model', 'not-installed'], capture_output=True, text=True, check=True)
        facts = json.loads(result.stdout)
        self.assertEqual(facts['working_tree']['state'], 'clean')
        self.assertEqual(facts['notes']['inventory']['README.md'], 'collected')
        self.assertNotIn('ai_interpretation', facts)
    def test_repository_fsmonitor_hook_not_executed(self):
        hook = self.root/'monitor.sh'
        hook.write_text('#!/bin/sh\ntouch "'+str(self.root/'hook-ran')+'"\n')
        hook.chmod(0o755)
        self.g('config', 'core.fsmonitor', str(hook))
        pickup.collect(self.root)
        self.assertFalse((self.root/'hook-ran').exists())

if __name__ == "__main__": unittest.main()
