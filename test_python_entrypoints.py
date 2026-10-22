import json
import unittest
import test_pickup as base
import pickup

class PythonEntrypointTests(unittest.TestCase):
    setUp=base.Tests.setUp
    tearDown=base.Tests.tearDown
    g=base.Tests.g
    def fixture(self):
        (self.root/'scripts').mkdir()
        (self.root/'src/coffee_cad/items').mkdir(parents=True)
        (self.root/'README.md').write_text('# Coffee\n```bash\npython scripts/export-cup.py\n```\n')
        (self.root/'scripts/export-cup.py').write_text('from coffee_cad.items import build_cup\nraise RuntimeError("NEVER EXECUTE")\n')
        (self.root/'src/coffee_cad/items/__init__.py').write_text('from .cup import build_cup\n')
        self.g('add','.')
        return pickup.collect(self.root)
    def test_literal_script_source_and_local_module(self):
        packet=self.fixture();entry=packet['entrypoints'][0]
        self.assertEqual(entry['manifest_line'],3)
        self.assertEqual(entry['local_import_leads'][0]['path'],'src/coffee_cad/items/__init__.py')
        focuses,actions=pickup.interpretation_options(packet)
        result=pickup.assemble(packet,{'interpretations':[focuses[0]],'next_action':actions[0]})
        text=result['ai_interpretation']['proposed_next_action']['text']
        self.assertIn('README.md:3',text);self.assertIn('scripts/export-cup.py',text)
        self.assertNotIn('package.json:',text);self.assertIn('do not run',text)
        self.assertEqual(result['repository_facts'],pickup.repository_facts(packet))
    def test_missing_untracked_symlink_large_and_outside_scripts(self):
        self.fixture()
        for source in ['python scripts/missing.py','python ../other/export.py','python scripts/export-cup.py && touch EXECUTED']:
            (self.root/'README.md').write_text(source)
            self.assertEqual(pickup.collect(self.root)['entrypoints'],[])
        (self.root/'README.md').write_text('python scripts/export-cup.py')
        self.g('reset','--','scripts/export-cup.py')
        self.assertEqual(pickup.collect(self.root)['entrypoints'],[])
        self.g('add','scripts/export-cup.py')
        (self.root/'scripts/export-cup.py').write_text('x'*64001)
        self.assertEqual(pickup.collect(self.root)['entrypoints'],[])
        (self.root/'scripts/export-cup.py').unlink()
        (self.root/'scripts/export-cup.py').symlink_to(self.root/'README.md')
        self.assertEqual(pickup.collect(self.root)['entrypoints'],[])
    def test_focus_limit_and_invalid_prefix(self):
        self.fixture()
        for n in range(9):
            (self.root/f'scripts/export-{n}.py').write_text('from coffee_cad.items import build_cup\n')
        (self.root/'README.md').write_text('\n'.join(f'python scripts/export-{n}.py' for n in range(9)))
        self.g('add','.')
        packet=pickup.collect(self.root,'export 8')
        self.assertEqual(len(packet['entrypoints']),6)
        (self.root/'scripts/export-0.py').write_text('def unfinished(\n')
        packet=pickup.collect(self.root)
        entry=next(e for e in packet['entrypoints'] if e['path']=='scripts/export-0.py')
        self.assertEqual(entry['local_import_leads'],[])
        self.assertEqual(entry['import_analysis'],'prefix_not_parseable_no_import_leads')
    def test_no_execution_secrets_or_mutation(self):
        self.fixture();(self.root/'.env').write_text('SECRET_NOT_FOR_PACKET')
        self.g('add','.env')
        def snapshot():return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        before=snapshot();packet=pickup.collect(self.root)
        self.assertEqual(before,snapshot());self.assertNotIn('SECRET_NOT_FOR_PACKET',json.dumps(packet))
    def implementation(self,init='from .cup import build_cup\n',source='def build_cup():\n    raise RuntimeError("NEVER EXECUTE")\n'):
        self.fixture()
        (self.root/'src/coffee_cad/items/__init__.py').write_text(init)
        (self.root/'src/coffee_cad/items/cup.py').write_text(source)
        self.g('add','.')
        return pickup.collect(self.root)
    def test_named_reexport_definition_and_citable_chain(self):
        packet=self.implementation();entry=packet['entrypoints'][0];lead=entry['reexport_leads'][0]
        self.assertEqual(lead['path'],'src/coffee_cad/items/cup.py')
        self.assertEqual(lead['symbol'],'build_cup');self.assertEqual(lead['definition_line'],1)
        evidence={e['id']:e for e in packet['evidence']}
        self.assertIn('from .cup import build_cup',evidence[lead['reexport_evidence']]['text'])
        self.assertIn('def build_cup',evidence[lead['definition_evidence']]['text'])
        f,a=pickup.interpretation_options(packet)
        brief=pickup.assemble(packet,{'interpretations':[f[0]],'next_action':a[0]})
        self.assertIn('cup.py:1 (build_cup',brief['ai_interpretation']['proposed_next_action']['text'])
        self.assertEqual(brief['repository_facts'],pickup.repository_facts(packet))
    def test_aliases_match_imported_name(self):
        packet=self.implementation('from .cup import make_cup as build_cup\n','def make_cup():\n    return 1\n')
        self.assertEqual(packet['entrypoints'][0]['reexport_leads'][0]['symbol'],'make_cup')
    def test_absolute_reexport_with_truncated_later_body(self):
        packet=self.implementation('from coffee_cad.items.cup import build_cup\n'+'\n'*79+'__all__ = [\n"build_cup",\n]\n','def build_cup():\n'+'    pass\n'*90)
        lead=packet['entrypoints'][0]['reexport_leads'][0]
        self.assertEqual(lead['symbol'],'build_cup')
        self.assertTrue(lead['reexport_excerpt_truncated']);self.assertTrue(lead['definition_excerpt_truncated'])
    def test_reexports_bounded_and_repository_unchanged(self):
        self.implementation()
        (self.root/'scripts/export-cup.py').write_text('from coffee_cad.items import a, b, c, d\n')
        (self.root/'src/coffee_cad/items/__init__.py').write_text('from .cup import a, b, c, d\n')
        (self.root/'src/coffee_cad/items/cup.py').write_text('\n'.join(f'def {name}():\n    raise RuntimeError("NEVER EXECUTE")' for name in 'abcd'))
        def snapshot():return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        before=snapshot();packet=pickup.collect(self.root)
        self.assertEqual(len(packet['entrypoints'][0]['reexport_leads']),3)
        self.assertEqual(before,snapshot())
    def test_no_wildcard_conditional_multihop_or_wrong_symbol(self):
        self.implementation()
        for init in ['from .cup import *\n','if True:\n    from .cup import build_cup\n','from .cup import wrong_name\n','from ..items.cup import build_cup\n']:
            (self.root/'src/coffee_cad/items/__init__.py').write_text(init)
            self.assertEqual(pickup.collect(self.root)['entrypoints'][0]['reexport_leads'],[])
        (self.root/'src/coffee_cad/items/__init__.py').write_text('from .cup import build_cup\n')
        (self.root/'src/coffee_cad/items/cup.py').write_text('from .other import build_cup\n')
        self.assertEqual(pickup.collect(self.root)['entrypoints'][0]['reexport_leads'],[])
    def test_unsafe_large_untracked_and_late_definition_omitted(self):
        self.implementation();target=self.root/'src/coffee_cad/items/cup.py'
        for source in ['x'*64001,'\n'*81+'def build_cup():\n    pass\n','def build_cup(:\n']:
            target.write_text(source)
            self.assertEqual(pickup.collect(self.root)['entrypoints'][0]['reexport_leads'],[])
        target.write_text('def build_cup():\n    pass\n');self.g('reset','--','src/coffee_cad/items/cup.py')
        self.assertEqual(pickup.collect(self.root)['entrypoints'][0]['reexport_leads'],[])
        self.g('add','.');target.unlink();target.symlink_to(self.root/'README.md')
        self.assertEqual(pickup.collect(self.root)['entrypoints'][0]['reexport_leads'],[])

if __name__=='__main__':unittest.main()
