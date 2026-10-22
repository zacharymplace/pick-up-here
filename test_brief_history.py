import copy
import hashlib
import unittest
import pickup
import test_pickup as base
from brief_export import export_brief,timestamp
from brief_history import open_brief,compare_brief,canonical
from repository_match import verify_ancestry

class HistoryTests(unittest.TestCase):
    setUp=base.Tests.setUp
    tearDown=base.Tests.tearDown
    g=base.Tests.g
    def compare(self,history,fresh,focus):
        before=next(e['text'] for e in history['packet']['evidence'] if e['source']=='git:HEAD')
        after=next(e['text'] for e in fresh['evidence'] if e['source']=='git:HEAD')
        return compare_brief(history,fresh,focus,verify_ancestry(self.root,before,after))
    def brief(self):
        packet=pickup.collect(self.root)
        return export_brief({'packet':packet,'focus':'','collected_at':timestamp()})
    def resign(self,brief):
        brief['evidence_packet_sha256']=hashlib.sha256(canonical(brief['evidence_packet']).encode()).hexdigest()
        return brief
    def test_roundtrip_keeps_historical_authority(self):
        brief=self.brief();brief['review_status']['human_usefulness']='passed'
        history=open_brief(brief)
        self.assertEqual(history['packet'],brief['evidence_packet'])
        self.assertIn('not fresh',history['view']['authority'])
        self.assertNotIn('human_usefulness',history['view'])
        result=self.compare(history,pickup.collect(self.root),'')
        self.assertEqual(result['changed_sources'],[])
        self.assertIn('Git ancestry verified',result['identity'])
    def test_tamper_unsupported_and_oversized_fields(self):
        brief=self.brief();brief['evidence_packet']['repository']='tampered'
        with self.assertRaisesRegex(ValueError,'checksum'):open_brief(brief)
        for change in [lambda b:b.update(format_version=2),lambda b:b.update(collected_at='not a date'),lambda b:b.update(requested_focus='x'*257),lambda b:b['evidence_packet'].update(version='unknown')]:
            brief=self.brief();change(brief)
            with self.assertRaises(ValueError):open_brief(brief)
    def test_duplicate_ids_and_git_sources_rejected_even_with_matching_checksum(self):
        for same_id in [True,False]:
            brief=self.brief();item=copy.deepcopy(brief['evidence_packet']['evidence'][0])
            if not same_id:item['id']='E999'
            brief['evidence_packet']['evidence'].append(item)
            with self.assertRaises(ValueError):open_brief(self.resign(brief))
    def test_comparison_ignores_ids_and_reports_literal_source_changes(self):
        brief=self.brief();history=open_brief(brief);fresh=copy.deepcopy(history['packet'])
        for n,item in enumerate(fresh['evidence'],100):item['id']='E'+str(n)
        self.assertEqual(self.compare(history,fresh,'')['changed_sources'],[])
        next(e for e in fresh['evidence'] if e['source']=='README.md')['text']='Changed note text'
        result=self.compare(history,fresh,'')
        self.assertEqual(result['changed_sources'],['README.md'])
    def test_renamed_label_allowed_but_topic_and_engine_mismatch_refused(self):
        history=open_brief(self.brief())
        with self.assertRaisesRegex(ValueError,'Topics'):self.compare(history,pickup.collect(self.root),'different')
        packet=copy.deepcopy(history['packet']);packet['repository']='renamed'
        self.assertEqual(self.compare(history,packet,'')['fresh_repository_label'],'renamed')
        packet['version']='other'
        with self.assertRaises(ValueError):self.compare(history,packet,'')
    def test_saved_proposal_is_file_text_not_current_selection(self):
        brief=self.brief();brief['proposal_state']='accepted'
        brief['proposal']={'interpretation':{'proposed_next_action':{'text':'<img src=x onerror=alert(1)>'}}}
        history=open_brief(brief)
        self.assertEqual(history['view']['proposal_text_from_file'],'<img src=x onerror=alert(1)>')
        self.assertIn('not authenticated',history['view']['checksum_status'])
    def test_diff_preview_shows_literal_before_and_after(self):
        history=open_brief(self.brief());fresh=copy.deepcopy(history['packet'])
        next(e for e in fresh['evidence'] if e['source']=='README.md')['text']='New literal context\n'
        diff=self.compare(history,fresh,'')['diff_previews'][0]
        self.assertEqual(diff['source'],'README.md');self.assertIn('+New literal context',diff['text'])
        self.assertIn('--- historical/README.md',diff['text']);self.assertIn('+++ fresh/README.md',diff['text'])
    def test_summary_partitions_sources_and_marks_truncated_evidence(self):
        history=open_brief(self.brief());fresh=copy.deepcopy(history['packet'])
        note=next(e for e in fresh['evidence'] if e['source']=='README.md')
        note['text']='changed';note['truncated']=True
        fresh['evidence'].append({'id':'E900','source':'new source','text':'literal'})
        history['packet']['evidence'].append({'id':'E901','source':'old source','text':'literal'})
        result=self.compare(history,fresh,'')
        self.assertEqual(result['changed_sources'],['README.md'])
        self.assertEqual(result['added_sources'],['new source'])
        self.assertEqual(result['removed_sources'],['old source'])
        self.assertEqual(result['truncated_sources'],['README.md'])
        self.assertEqual(result['unchanged_source_count'],len(result['unchanged_sources']))
        self.assertEqual(set(result['unchanged_sources']),{e['source'] for e in fresh['evidence']}-{'README.md','new source'})
    def test_diff_bounds_and_changes_outside_preview_are_explicit(self):
        history=open_brief(self.brief());fresh=copy.deepcopy(history['packet'])
        for packet,tail in [(history['packet'],'OLD'),(fresh,'NEW')]:
            next(e for e in packet['evidence'] if e['source']=='README.md')['text']='x'*7000+tail
        diff=self.compare(history,fresh,'')['diff_previews'][0]
        self.assertTrue(diff['input_truncated']);self.assertEqual(diff['text'],'')
        fresh=copy.deepcopy(history['packet'])
        for n in range(20):fresh['evidence'].append({'id':'E'+str(n+100),'source':f'added-{n}','text':'content'})
        result=self.compare(history,fresh,'')
        self.assertEqual(len(result['diff_previews']),12);self.assertEqual(result['diff_previews_omitted'],8)

if __name__=='__main__':unittest.main()
