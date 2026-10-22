import json
import io
import hashlib
import shlex
import subprocess
from types import SimpleNamespace
import threading
import urllib.error
import urllib.request
from unittest.mock import patch
import unittest
import tempfile
from pathlib import Path
from release import VERSION
import test_pickup as base
import app
import pickup

class AppTests(unittest.TestCase):
    g=base.Tests.g
    def setUp(self):
        base.Tests.setUp(self)
        self.server=app.AppServer(0,str(self.root))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();base.Tests.tearDown(self)
    def post(self,path,data,origin=None,token=None):
        request=urllib.request.Request(self.server.origin+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Origin':origin or self.server.origin,'X-Pickup-Token':self.server.token if token is None else token})
        try:
            with self.client.open(request) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def test_facts_flow_and_csp(self):
        with self.client.open(self.server.origin) as r:
            self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])
            self.assertIn(b'Choose your project',r.read())
        status,data=self.post('/api/facts',{'repository':str(self.root),'focus':''})
        self.assertEqual(status,200);self.assertEqual(data['facts']['working_tree']['state'],'clean')
        self.assertTrue(data['evidence'])
    def test_release_version_matches_session_and_export(self):
        with self.client.open(self.server.origin+'/api/session') as response:
            self.assertEqual(json.load(response)['app_version'],VERSION)
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        _,export=self.post('/api/export',{'snapshot':data['snapshot']})
        self.assertEqual(export['brief']['app_version'],VERSION)
        self.assertEqual(export['brief']['engine_version'],'0.6')
        self.assertEqual(export['brief']['format_version'],1)
    def test_cli_version_without_server(self):
        result=subprocess.run([app.sys.executable,str(app.HERE/'app.py'),'--version'],cwd=self.root,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0);self.assertEqual(result.stdout.strip(),'Pick Up Here '+VERSION)
    def test_reject_cross_origin_and_missing_token(self):
        self.assertEqual(self.post('/api/facts',{'repository':str(self.root)},origin='https://example.invalid')[0],403)
        self.assertEqual(self.post('/api/facts',{'repository':str(self.root)},token='')[0],403)
    def test_changed_snapshot_rejected_before_model(self):
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        (self.root/'README.md').write_text('changed')
        with patch.object(pickup,'generate') as model:
            status,_=self.post('/api/propose',{'snapshot':data['snapshot']})
            self.assertEqual(status,409);model.assert_not_called()
    def test_model_failure_preserves_facts(self):
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        with patch.object(pickup,'generate',side_effect=ConnectionError('offline')):
            status,result=self.post('/api/propose',{'snapshot':data['snapshot']})
        self.assertEqual(status,503);self.assertIn('Facts remain',result['error'])
        self.assertEqual(self.server.snapshots[data['snapshot']]['packet']['repository'],self.root.name)
    def test_valid_proposal_and_changed_during_inference(self):
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        def generate(packet):
            f,a=pickup.interpretation_options(packet)
            return dict(pickup.assemble(packet,{'interpretations':[f[0]],'next_action':a[0]}),qualification='Test selection; not a live model response')
        with patch.object(pickup,'generate',side_effect=generate):
            self.assertEqual(self.post('/api/propose',{'snapshot':data['snapshot']})[0],200)
        def change(packet):
            result=generate(packet);(self.root/'new.txt').write_text('changed');return result
        with patch.object(pickup,'generate',side_effect=change):
            self.assertEqual(self.post('/api/propose',{'snapshot':data['snapshot']})[0],409)
    def test_unknown_snapshot_and_relative_path(self):
        self.assertEqual(self.post('/api/propose',{'snapshot':'unknown'})[0],409)
        self.assertEqual(self.post('/api/facts',{'repository':'relative'})[0],400)
    def test_pasted_paths_and_file_error(self):
        for value in [str(self.root),shlex.quote(str(self.root))]:
            self.assertEqual(app.repository_path(value),str(self.root))
        folder=self.root/'space here';folder.mkdir()
        self.assertEqual(app.repository_path(str(folder).replace(' ',r'\ ')),str(folder))
        with patch('pathlib.Path.expanduser',return_value=folder):
            self.assertEqual(app.repository_path('~/space here'),str(folder))
        with self.assertRaisesRegex(ValueError,'This is a file'):
            app.repository_path(str(self.root/'README.md'))
        for value in ['cd '+str(self.root),'"unfinished',str(self.root/'missing')]:
            with self.assertRaises(ValueError):app.repository_path(value)
    def test_readiness_states_and_no_inference(self):
        for payload,state in [({'models':[{'name':'gemma3:4b'}]},'ready'),({'models':[{'name':'gemma3:1b'}]},'model_missing'),({'models':['bad']},'unavailable')]:
            response=io.BytesIO(json.dumps(payload).encode())
            with patch('app.urllib.request.build_opener') as opener,patch.object(pickup,'generate') as generate:
                opener.return_value.open.return_value=response
                status,result=self.post('/api/readiness',{})
                self.assertEqual(status,200);self.assertEqual(result['state'],state);generate.assert_not_called()
                self.assertEqual(opener.return_value.open.call_args.args[0],'http://127.0.0.1:11434/api/tags')
        with patch('app.urllib.request.build_opener',side_effect=OSError('offline')):
            self.assertEqual(app.model_readiness()['state'],'unavailable')
        self.assertEqual(self.post('/api/readiness',{},token='')[0],403)
    def test_native_folder_selection_uses_fixed_script(self):
        with patch('app.sys.platform','darwin'),patch('app.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=str(self.root)+'\n')) as run:
            status,result=self.post('/api/choose-folder',{})
        self.assertEqual(status,200);self.assertFalse(result['cancelled'])
        self.assertEqual(result['repository'],str(self.root))
        self.assertEqual(run.call_args.args[0][:2],['/usr/bin/osascript','-e'])
        self.assertNotIn(str(self.root),run.call_args.args[0][2])
        self.assertEqual(run.call_args.kwargs['timeout'],120)
        self.assertEqual(self.server.snapshots,{})
    def test_folder_cancel_preserves_snapshot(self):
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        with patch('app.sys.platform','darwin'),patch('app.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='\n')):
            status,result=self.post('/api/choose-folder',{})
        self.assertEqual((status,result),(200,{'cancelled':True}))
        self.assertIn(data['snapshot'],self.server.snapshots)
    def test_folder_unavailable_timeout_and_invalid_result(self):
        with patch('app.sys.platform','linux'):
            self.assertEqual(self.post('/api/choose-folder',{})[0],503)
        for outcome in [subprocess.TimeoutExpired('osascript',120),OSError('missing')]:
            with patch('app.sys.platform','darwin'),patch('app.subprocess.run',side_effect=outcome):
                self.assertEqual(self.post('/api/choose-folder',{})[0],503)
        for result in [SimpleNamespace(returncode=1,stdout=''),SimpleNamespace(returncode=0,stdout=str(self.root/'README.md'))]:
            with patch('app.sys.platform','darwin'),patch('app.subprocess.run',return_value=result):
                self.assertEqual(self.post('/api/choose-folder',{})[0],503)
    def test_folder_rejects_unauthorized_and_busy_requests(self):
        with patch('app.choose_folder') as chooser:
            self.assertEqual(self.post('/api/choose-folder',{},token='')[0],403)
            self.assertEqual(self.post('/api/choose-folder',{},origin='https://example.invalid')[0],403)
            self.server.gate.acquire()
            try:self.assertEqual(self.post('/api/choose-folder',{})[0],409)
            finally:self.server.gate.release()
            chooser.assert_not_called()
    def test_export_facts_only_retains_packet_without_model_or_writes(self):
        _,data=self.post('/api/facts',{'repository':str(self.root),'focus':'coffee'})
        saved=self.server.snapshots[data['snapshot']]
        def files():return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        before=files()
        with patch.object(pickup,'generate') as generate:
            status,result=self.post('/api/export',{'snapshot':data['snapshot']})
            generate.assert_not_called()
        self.assertEqual(status,200);self.assertEqual(before,files())
        brief=result['brief'];self.assertEqual(brief['evidence_packet'],saved['packet'])
        self.assertEqual(brief['proposal_state'],'not_requested');self.assertIsNone(brief['proposal'])
        self.assertEqual(brief['requested_focus'],'coffee');self.assertEqual(brief['collected_at'],saved['collected_at'])
        self.assertEqual(brief['review_status']['human_usefulness'],'not_recorded')
        self.assertNotIn('token',brief);self.assertNotIn('path',brief)
        canonical=json.dumps(brief['evidence_packet'],sort_keys=True,separators=(',',':'),ensure_ascii=True)
        self.assertEqual(brief['evidence_packet_sha256'],hashlib.sha256(canonical.encode()).hexdigest())
    def test_export_accepted_proposal_then_failed_retry_is_explicit(self):
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        packet=self.server.snapshots[data['snapshot']]['packet'];f,a=pickup.interpretation_options(packet)
        selection={'interpretations':[f[0]],'next_action':a[0]}
        result=dict(pickup.assemble(packet,selection),qualification='Controlled test selection',model='gemma3:4b',model_selection=selection)
        with patch.object(pickup,'generate',return_value=result):
            self.assertEqual(self.post('/api/propose',{'snapshot':data['snapshot']})[0],200)
        _,export=self.post('/api/export',{'snapshot':data['snapshot']})
        self.assertEqual(export['brief']['proposal_state'],'accepted')
        self.assertEqual(export['brief']['proposal']['selection'],selection)
        with patch.object(pickup,'generate',side_effect=OSError('offline')):
            self.assertEqual(self.post('/api/propose',{'snapshot':data['snapshot']})[0],503)
        _,export=self.post('/api/export',{'snapshot':data['snapshot']})
        self.assertEqual(export['brief']['proposal_state'],'failed');self.assertIsNone(export['brief']['proposal'])
    def test_export_rejects_stale_or_unreadable_repository(self):
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        (self.root/'README.md').write_text('Changed after collection')
        status,result=self.post('/api/export',{'snapshot':data['snapshot']})
        self.assertEqual(status,409);self.assertNotIn('brief',result)
        with patch.object(pickup,'collect',side_effect=OSError('unavailable')):
            self.assertEqual(self.post('/api/export',{'snapshot':data['snapshot']})[0],409)
    def test_export_rejects_unknown_replaced_and_unauthorized_snapshot(self):
        _,first=self.post('/api/facts',{'repository':str(self.root)})
        self.post('/api/facts',{'repository':str(self.root)})
        self.assertEqual(self.post('/api/export',{'snapshot':first['snapshot']})[0],409)
        self.assertEqual(self.post('/api/export',{'snapshot':'unknown'})[0],409)
        self.assertEqual(self.post('/api/export',{},token='')[0],403)
    def test_open_history_does_not_collect_run_model_or_replace_current_facts(self):
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        _,export=self.post('/api/export',{'snapshot':data['snapshot']})
        with patch.object(pickup,'collect') as collect,patch.object(pickup,'generate') as generate:
            status,opened=self.post('/api/open-brief',{'brief':export['brief']})
            self.assertEqual(status,200);collect.assert_not_called();generate.assert_not_called()
        self.assertIn(data['snapshot'],self.server.snapshots)
        status,result=self.post('/api/compare',{'history':opened['history'],'snapshot':data['snapshot']})
        self.assertEqual(status,200);self.assertEqual(result['changed_sources'],[])
    def test_invalid_import_preserves_opened_history_and_snapshot(self):
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        _,export=self.post('/api/export',{'snapshot':data['snapshot']})
        _,opened=self.post('/api/open-brief',{'brief':export['brief']})
        self.assertEqual(self.post('/api/open-brief',{'brief':{'bad':'file'}})[0],400)
        self.assertIn(opened['history'],self.server.histories);self.assertIn(data['snapshot'],self.server.snapshots)
        self.assertEqual(self.post('/api/open-brief',{'brief':export['brief']},token='')[0],403)
    def test_compare_rechecks_current_state_and_requires_history(self):
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        self.assertEqual(self.post('/api/compare',{'snapshot':data['snapshot'],'history':'missing'})[0],409)
        _,export=self.post('/api/export',{'snapshot':data['snapshot']})
        _,opened=self.post('/api/open-brief',{'brief':export['brief']})
        (self.root/'README.md').write_text('Changed since collection')
        self.assertEqual(self.post('/api/compare',{'snapshot':data['snapshot'],'history':opened['history']})[0],409)
        _,fresh=self.post('/api/facts',{'repository':str(self.root)})
        status,result=self.post('/api/compare',{'snapshot':fresh['snapshot'],'history':opened['history']})
        self.assertEqual(status,200);self.assertIn('README.md',result['changed_sources'])
    def comparison_setup(self):
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        _,export=self.post('/api/export',{'snapshot':data['snapshot']})
        _,opened=self.post('/api/open-brief',{'brief':export['brief']})
        (self.root/'README.md').write_text('Fresh comparison text\n')
        _,fresh=self.post('/api/facts',{'repository':str(self.root)})
        pair={'snapshot':fresh['snapshot'],'history':opened['history']}
        return pair,export['brief']['evidence_packet']
    def test_comparison_export_requires_success_and_binds_evidence(self):
        from brief_history import canonical
        pair,old=self.comparison_setup()
        self.assertEqual(self.post('/api/export-comparison',pair)[0],409)
        _,comparison=self.post('/api/compare',pair)
        with patch.object(pickup,'generate') as model:
            status,result=self.post('/api/export-comparison',pair);model.assert_not_called()
        self.assertEqual(status,200);value=result['comparison_export'];payload=value['payload']
        self.assertEqual(value['format'],'pick-up-here-return-comparison')
        self.assertEqual(payload['historical']['evidence_packet'],old)
        self.assertEqual(payload['fresh']['evidence_packet'],self.server.snapshots[pair['snapshot']]['packet'])
        self.assertEqual(payload['comparison'],comparison)
        self.assertEqual(value['payload_sha256'],hashlib.sha256(canonical(payload).encode()).hexdigest())
        self.assertNotIn(str(self.root),json.dumps(value));self.assertNotIn(self.server.token,json.dumps(value))
        self.assertTrue(value['review_status']['historical_after_download'])
    def test_comparison_export_stale_unreadable_replaced_and_unauthorized(self):
        pair,_=self.comparison_setup();self.post('/api/compare',pair)
        self.assertEqual(self.post('/api/export-comparison',pair,token='')[0],403)
        with patch.object(app,'verify_ancestry',side_effect=ValueError('History unavailable')):
            self.assertEqual(self.post('/api/export-comparison',pair)[0],409)
        self.assertEqual(self.post('/api/export-comparison',pair)[0],409)
        self.post('/api/compare',pair)
        with patch.object(pickup,'collect',side_effect=OSError('unreadable')):
            self.assertEqual(self.post('/api/export-comparison',pair)[0],409)
        self.post('/api/compare',pair)
        (self.root/'README.md').write_text('changed after comparison')
        self.assertEqual(self.post('/api/export-comparison',pair)[0],409)
        self.post('/api/facts',{'repository':str(self.root)})
        self.assertEqual(self.post('/api/export-comparison',pair)[0],409)
    def test_compare_blocks_unrelated_same_name_and_allows_renamed_clone(self):
        _,data=self.post('/api/facts',{'repository':str(self.root)})
        _,export=self.post('/api/export',{'snapshot':data['snapshot']})
        _,opened=self.post('/api/open-brief',{'brief':export['brief']})
        with tempfile.TemporaryDirectory() as d:
            other=Path(d)/self.root.name;other.mkdir()
            (other/'README.md').write_text('# Unrelated project\n')
            for args in [['init','-q'],['add','.'],['-c','user.name=Other','-c','user.email=other@example.invalid','commit','-qm','Different project']]:
                subprocess.run(['git','-C',str(other),*args],check=True,capture_output=True)
            _,fresh=self.post('/api/facts',{'repository':str(other)})
            status,result=self.post('/api/compare',{'snapshot':fresh['snapshot'],'history':opened['history'],'repository_match':{'verified':True}})
            self.assertEqual(status,409);self.assertIn('not verified',result['error'])
            clone=Path(d)/'renamed clone'
            subprocess.run(['git','clone','--quiet',str(self.root),str(clone)],check=True)
            _,fresh=self.post('/api/facts',{'repository':str(clone)})
            status,result=self.post('/api/compare',{'snapshot':fresh['snapshot'],'history':opened['history']})
            self.assertEqual(status,200);self.assertTrue(result['repository_match']['verified'])

if __name__=='__main__':unittest.main()
