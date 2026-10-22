import json
import unittest
import test_pickup as baseline_tests
import pickup

class EntrypointTests(unittest.TestCase):
    setUp=baseline_tests.Tests.setUp
    tearDown=baseline_tests.Tests.tearDown
    g=baseline_tests.Tests.g
    def fixture(self, scripts=None):
        (self.root/'scripts').mkdir()
        (self.root/'runtime').mkdir()
        (self.root/'scripts/trace-probe.ts').write_text('import { start } from "../runtime/sdk.js";\nstart();\n')
        (self.root/'runtime/sdk.ts').write_text('export const start = () => 1;\n')
        (self.root/'package.json').write_text(json.dumps({'scripts':scripts or {'trace:probe':'tsx scripts/trace-probe.ts'}},indent=2))
        self.g('add','.')
        return pickup.collect(self.root,'trace')
    def test_manifest_source_and_local_import_lead(self):
        p=self.fixture(); e=p['entrypoints'][0]
        self.assertEqual(e['path'],'scripts/trace-probe.ts')
        self.assertEqual(e['local_import_leads'][0]['path'],'runtime/sdk.ts')
        self.assertEqual(e['local_import_leads'][0]['resolution'],'static_resolution_candidate_not_runtime_verified')
        self.assertEqual(e['local_import_leads'][0]['line'],1)
        raw=(self.root/'package.json').read_text().splitlines()[e['manifest_line']-1]
        self.assertIn(e['script_name'],raw)
    def test_entrypoint_is_specific_and_read_only(self):
        p=self.fixture(); f,a=pickup.interpretation_options(p)
        self.assertEqual({v['kind'] for v in a},{'inspect_entrypoint'})
        r=pickup.assemble(p,{'interpretations':[f[0]],'next_action':a[0]})
        text=r['ai_interpretation']['proposed_next_action']['text']
        self.assertIn('scripts/trace-probe.ts',text)
        self.assertIn('runtime/sdk.ts',text)
        self.assertIn('do not run',text)
        self.assertEqual(r['repository_facts'],pickup.repository_facts(p))
    def test_missing_script_target_not_offered(self):
        p=self.fixture({'probe':'tsx scripts/not-present.ts'})
        self.assertEqual(p['entrypoints'],[])
    def test_symlinked_source_not_opened(self):
        self.fixture()
        (self.root/'scripts/trace-probe.ts').unlink()
        (self.root/'scripts/trace-probe.ts').symlink_to(self.root/'README.md')
        self.assertEqual(pickup.collect(self.root)['entrypoints'],[])
    def test_untracked_manifest_not_opened(self):
        self.fixture()
        self.g('reset','--','package.json')
        self.assertEqual(pickup.collect(self.root)['entrypoint_scope']['status'],'not_observed')
    def test_environment_file_not_opened(self):
        self.fixture({'probe':'cat .env'})
        (self.root/'.env').write_text('NEVER_READ=this-secret')
        self.g('add','.env')
        packet=pickup.collect(self.root)
        self.assertEqual(packet['entrypoints'],[])
        self.assertNotIn('this-secret',json.dumps(packet))
    def test_invalid_manifest_explicit(self):
        self.fixture(); (self.root/'package.json').write_text('{broken')
        self.assertEqual(pickup.collect(self.root)['entrypoint_scope']['status'],'invalid_manifest')
    def test_large_source_skipped(self):
        self.fixture(); (self.root/'scripts/trace-probe.ts').write_text('a'*64001)
        self.assertEqual(pickup.collect(self.root)['entrypoints'],[])
    def test_duplicate_json_members_use_last_literal(self):
        self.fixture()
        (self.root/'package.json').write_text('{"scripts":{"old":"tsx missing.ts"},"scripts":{"probe":"tsx scripts/trace-probe.ts"}}')
        p=pickup.collect(self.root)
        self.assertEqual([e['script_name'] for e in p['entrypoints']],['probe'])
        self.assertIn('scripts/trace-probe.ts',next(e['text'] for e in p['evidence'] if e['id']==p['entrypoints'][0]['manifest_evidence']))
    def test_no_commands_or_source_executed(self):
        self.fixture({'probe':'tsx scripts/trace-probe.ts && touch EXECUTED'})
        (self.root/'scripts/trace-probe.ts').write_text('throw new Error("do not execute");\n')
        def snap(): return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        before=snap();packet=pickup.collect(self.root)
        self.assertTrue(packet['entrypoints'])
        self.assertEqual(before,snap())
        self.assertFalse((self.root/'EXECUTED').exists())
    def test_focus_is_recorded_and_orders_leads(self):
        self.fixture({'misc':'tsx scripts/misc.ts','trace:probe':'tsx scripts/trace-probe.ts'})
        (self.root/'scripts/misc.ts').write_text('console.log(1)')
        self.g('add','.')
        p=pickup.collect(self.root,'trace')
        self.assertEqual(p['entrypoint_scope']['focus'],'trace')
        self.assertEqual(p['entrypoints'][0]['script_name'],'trace:probe')
    def test_source_target_swap_rejected(self):
        p=self.fixture(); f,a=pickup.interpretation_options(p)
        a[0]['target']=next(x['id'] for x in p['observed_files'] if x['path']=='runtime/sdk.ts')
        with self.assertRaisesRegex(ValueError,'Unsupported next_action'):
            pickup.validate({'interpretations':[f[0]],'next_action':a[0]},p)
    def test_multiple_distinct_focuses_rejected(self):
        (self.root/'untracked.txt').write_text('pending')
        p=pickup.collect(self.root)
        with self.assertRaisesRegex(ValueError,'Exactly one'):
            pickup.validate({'interpretations':[{'focus':'review_notes','evidence':'E4'},{'focus':'review_changes','evidence':'E2'}], 'next_action':{'kind':'review_history','evidence':'E3'}},p)

if __name__=='__main__': unittest.main()
