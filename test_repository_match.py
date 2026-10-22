from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
import unittest
import pickup
import test_pickup as base
from repository_match import verify_ancestry
from brief_export import export_brief,timestamp
from brief_history import open_brief,compare_brief

class RepositoryMatchTests(unittest.TestCase):
    setUp=base.Tests.setUp
    tearDown=base.Tests.tearDown
    g=base.Tests.g
    def head(self):return self.g('rev-parse','HEAD').stdout.decode().strip()
    def test_same_commit_and_descendant_match_without_writes(self):
        old=self.head();self.assertTrue(verify_ancestry(self.root,old,old)['verified'])
        (self.root/'README.md').write_text('Later work');self.g('add','.');self.g('commit','-qm','Later')
        def snap():return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        before=snap();proof=verify_ancestry(self.root,old,self.head());self.assertEqual(before,snap())
        self.assertEqual(proof['method'],'git_commit_ancestry')
    def test_clone_with_different_folder_name_matches_legacy_brief(self):
        packet=pickup.collect(self.root);brief=export_brief({'packet':packet,'focus':'','collected_at':timestamp()})
        history=open_brief(brief)
        with tempfile.TemporaryDirectory() as d:
            clone=Path(d)/'renamed project'
            subprocess.run(['git','clone','--quiet','--no-hardlinks',str(self.root),str(clone)],check=True)
            fresh=pickup.collect(clone);proof=verify_ancestry(clone,self.head(),self.head())
            result=compare_brief(history,fresh,'',proof)
            self.assertNotEqual(result['historical_repository_label'],result['fresh_repository_label'])
    def test_same_name_unrelated_history_rejected(self):
        old=self.head()
        with tempfile.TemporaryDirectory() as d:
            other=Path(d)/self.root.name;other.mkdir()
            for args in [['init','-q'],['config','user.email','other@example.invalid'],['config','user.name','Other']]:subprocess.run(['git','-C',str(other),*args],check=True,capture_output=True)
            (other/'different.txt').write_text('Unrelated history')
            for args in [['add','.'],['commit','-qm','Other root']]:subprocess.run(['git','-C',str(other),*args],check=True,capture_output=True)
            new=subprocess.check_output(['git','-C',str(other),'rev-parse','HEAD'],text=True).strip()
            with self.assertRaisesRegex(ValueError,'not verified'):verify_ancestry(other,old,new)
    def test_divergent_history_and_changed_head_rejected(self):
        root=self.head();self.g('checkout','-qb','branch-one')
        (self.root/'one.txt').write_text('one');self.g('add','.');self.g('commit','-qm','one');old=self.head()
        self.g('checkout','-qb','branch-two',root)
        (self.root/'two.txt').write_text('two');self.g('add','.');self.g('commit','-qm','two')
        with self.assertRaisesRegex(ValueError,'not verified'):verify_ancestry(self.root,old,self.head())
        self.g('replace','--graft',self.head(),old)
        with self.assertRaisesRegex(ValueError,'not verified'):verify_ancestry(self.root,old,self.head())
        with self.assertRaisesRegex(ValueError,'HEAD changed'):verify_ancestry(self.root,root,old)
    def test_incomplete_shallow_history_rejected(self):
        old=self.head();(self.root/'README.md').write_text('later');self.g('add','.');self.g('commit','-qm','later')
        with tempfile.TemporaryDirectory() as d:
            clone=Path(d)/'shallow'
            subprocess.run(['git','clone','--quiet','--depth','1',self.root.as_uri(),str(clone)],check=True)
            with self.assertRaisesRegex(ValueError,'not verified'):verify_ancestry(clone,old,self.head())
    def test_malformed_ids_timeout_and_missing_proof_fail_closed(self):
        head=self.head()
        for bad in ['--all','not-a-hash','a'*39]:
            with self.assertRaises(ValueError):verify_ancestry(self.root,bad,head)
        with patch('repository_match.subprocess.run',side_effect=subprocess.TimeoutExpired('git',10)):
            with self.assertRaisesRegex(ValueError,'Could not verify'):verify_ancestry(self.root,head,head)
        packet=pickup.collect(self.root);history=open_brief(export_brief({'packet':packet,'focus':'','collected_at':timestamp()}))
        with self.assertRaisesRegex(ValueError,'Verified Git ancestry'):compare_brief(history,packet,'')

if __name__=='__main__':unittest.main()
