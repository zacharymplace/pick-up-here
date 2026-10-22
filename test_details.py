import copy
import unittest
from unittest.mock import patch
import test_pickup as baseline_tests
import pickup
from details import markdown_parts

class DetailTests(unittest.TestCase):
    setUp = baseline_tests.Tests.setUp
    tearDown = baseline_tests.Tests.tearDown
    g = baseline_tests.Tests.g
    def fixture(self):
        (self.root/'README.md').write_text('# Tools\n## Roadmap\n- [ ] Tests for invoice reconciliation\n## Done\n- [x] Export\n')
        (self.root/'scripts').mkdir()
        (self.root/'tests').mkdir()
        (self.root/'scripts/invoice_reconciliation.py').write_text('not executed\n')
        (self.root/'tests/test_invoice_reconciliation.py').write_text('not executed\n')
        self.g('add', '.')
        return pickup.collect(self.root)
    def test_literal_task_and_section_lines(self):
        p=self.fixture()
        task=p['recorded_tasks'][0]
        self.assertEqual(task['line'], 3)
        self.assertEqual(task['quote'], '- [ ] Tests for invoice reconciliation')
        self.assertEqual(task['authority'], 'unverified_recorded_task')
        section=next(s for s in p['note_sections'] if s['heading']=='Roadmap')
        self.assertEqual((section['start_line'],section['end_line']), (2,3))
    def test_fenced_fake_tasks_and_headers_not_extracted(self):
        s,t=markdown_parts('# Real\n```md\n## Fake\n- [ ] erase stuff\n```\n~~~\n- [ ] not a task\n~~~\n- [ ] Real work\n')
        self.assertEqual([v['heading'] for v in s], ['Real'])
        self.assertEqual([v['line'] for v in t], [9])
    def test_linked_action_uses_observed_paths_and_literal_item(self):
        p=self.fixture()
        action=next(a for a in pickup.interpretation_options(p)[1] if a['kind']=='inspect_task_file' and next(f['path'] for f in p['observed_files'] if f['id']==a['target']).startswith('scripts/'))
        brief={'interpretations':[{'focus':'review_recorded_task','evidence':action['evidence']}], 'next_action':action}
        result=pickup.assemble(p,brief)
        proposal=result['ai_interpretation']['proposed_next_action']
        self.assertEqual(proposal['recorded_item']['quote'], '- [ ] Tests for invoice reconciliation')
        self.assertIn('scripts/invoice_reconciliation.py', proposal['observed_targets'])
        self.assertIn('tests/test_invoice_reconciliation.py', proposal['observed_targets'])
        self.assertIn('unverified', proposal['text'])
        self.assertEqual(result['repository_facts'],pickup.repository_facts(p))
    def test_model_cannot_swap_a_linked_target(self):
        p=self.fixture()
        a=next(a for a in pickup.interpretation_options(p)[1] if a['kind']=='inspect_task_file')
        a=copy.deepcopy(a); a['target']=next(f['id'] for f in p['observed_files'] if f['path']=='README.md')
        with self.assertRaisesRegex(ValueError,'Unsupported next_action'):
            pickup.validate({'interpretations':[{'focus':'review_recorded_task','evidence':a['evidence']}],'next_action':a},p)
    def test_duplicates_rejected(self):
        p=self.fixture()
        focus=pickup.interpretation_options(p)[0][0]
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            pickup.validate({'interpretations':[focus,focus], 'next_action':pickup.interpretation_options(p)[1][0]},p)
    def test_section_action_renders_exact_location(self):
        (self.root/'README.md').write_text('# Tools\n## Roadmap\n- [ ] Tests for invoice reconciliation\n## Done\n')
        p=pickup.collect(self.root)
        section=next(s for s in p['note_sections'] if s['heading']=='Roadmap')
        brief={'interpretations':[{'focus':'review_notes','evidence':'E4'}], 'next_action':{'kind':'read_section','evidence':section['evidence']}}
        action=pickup.assemble(p,brief)['ai_interpretation']['proposed_next_action']
        self.assertIn('README.md lines 2-3',action['text'])
        self.assertEqual(action['section']['quote'],'## Roadmap\n- [ ] Tests for invoice reconciliation')
    def test_specific_options_exclude_generic_rereads(self):
        p=self.fixture()
        self.assertEqual({a['kind'] for a in pickup.interpretation_options(p)[1]}, {'inspect_task_file'})
    def test_task_focus_must_match_selected_task(self):
        p=self.fixture()
        (self.root/'README.md').write_text('## Next\n- [ ] Tests for invoice reconciliation\n- [ ] Review scripts/invoice_reconciliation.py\n')
        p=pickup.collect(self.root)
        actions=pickup.interpretation_options(p)[1]
        ids=list(dict.fromkeys(a['evidence'] for a in actions))
        self.assertEqual(len(ids),2)
        action=next(a for a in actions if a['evidence']==ids[0])
        with self.assertRaisesRegex(ValueError,'same recorded item'):
            pickup.validate({'interpretations':[{'focus':'review_recorded_task','evidence':ids[1]}], 'next_action':action},p)
    def test_unobserved_referenced_file_not_offered(self):
        (self.root/'README.md').write_text('## Next\n- [ ] Inspect missing_module.py\n')
        p=pickup.collect(self.root)
        self.assertEqual(p['inspection_candidates'], [])
    def test_symlink_target_not_offered(self):
        (self.root/'README.md').write_text('## Next\n- [ ] Inspect invoice.py\n')
        (self.root/'invoice.py').symlink_to(self.root/'README.md')
        self.g('add','.')
        p=pickup.collect(self.root)
        self.assertNotIn('invoice.py', [f['path'] for f in p['observed_files']])
        self.assertEqual(p['inspection_candidates'], [])
    def test_duplicate_git_paths_are_observed_once(self):
        original = pickup.git
        def repeated(root, *args):
            value = original(root, *args)
            return value + value if args == ('ls-files', '-z') else value
        with patch.object(pickup, 'git', side_effect=repeated):
            packet=pickup.collect(self.root)
        names=[f['path'] for f in packet['observed_files']]
        self.assertEqual(names, ['README.md'])

if __name__=='__main__': unittest.main()
