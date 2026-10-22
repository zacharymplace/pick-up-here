import copy
import hashlib
import unittest
from unittest.mock import patch
from brief_history import canonical
from comparison_export import open_comparison
import test_app as base

class ComparisonViewerTests(unittest.TestCase):
    setUp=base.AppTests.setUp
    tearDown=base.AppTests.tearDown
    g=base.AppTests.g
    post=base.AppTests.post
    comparison_setup=base.AppTests.comparison_setup
    def export(self):
        pair,_=self.comparison_setup();self.post('/api/compare',pair)
        _,result=self.post('/api/export-comparison',pair)
        return result['comparison_export']
    def resign(self,value):
        value['payload_sha256']=hashlib.sha256(canonical(value['payload']).encode()).hexdigest()
    def test_viewer_roundtrip_is_read_only_and_recomputes(self):
        value=self.export();snapshots=copy.deepcopy(self.server.snapshots);histories=copy.deepcopy(self.server.histories);comparison=copy.deepcopy(self.server.comparison)
        with patch('pickup.collect') as collect,patch('pickup.generate') as model,patch('app.verify_ancestry') as git:
            status,result=self.post('/api/open-comparison',{'comparison_export':value})
            self.assertEqual(status,200);collect.assert_not_called();model.assert_not_called();git.assert_not_called()
        self.assertEqual(result['view']['comparison']['changed_sources'],value['payload']['comparison']['changed_sources'])
        self.assertIn('not reverified',result['view']['authority'])
        self.assertEqual(self.server.snapshots,snapshots);self.assertEqual(self.server.histories,histories);self.assertEqual(self.server.comparison,comparison)
    def test_viewer_rejects_tamper_and_rehashed_false_result(self):
        value=self.export();value['payload']['comparison']['changed_sources']=[]
        with self.assertRaisesRegex(ValueError,'checksum'):open_comparison(value)
        self.resign(value)
        with self.assertRaisesRegex(ValueError,'recomputed'):open_comparison(value)
    def test_viewer_rejects_bad_packet_and_unbound_claim(self):
        value=self.export();value['payload']['historical']['evidence_packet']['evidence'][0]['text']='bad';self.resign(value)
        with self.assertRaises(ValueError):open_comparison(value)
        value=self.export();value['payload']['comparison']['repository_match']['historical_commit']='0'*40;self.resign(value)
        with self.assertRaisesRegex(ValueError,'ancestry claim'):open_comparison(value)
    def test_viewer_rejects_bad_format_dates_and_token(self):
        value=self.export()
        self.assertEqual(self.post('/api/open-comparison',{'comparison_export':value},token='')[0],403)
        for field,wrong in [('format_version',True),('exported_at','not a timestamp')]:
            bad=copy.deepcopy(value);bad[field]=wrong
            self.assertEqual(self.post('/api/open-comparison',{'comparison_export':bad})[0],400)

if __name__=='__main__':unittest.main()
