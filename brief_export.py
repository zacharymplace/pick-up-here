"""Portable snapshot envelope. No file writes or inference."""
from datetime import datetime, timezone
import hashlib
import json
from release import VERSION

def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def export_brief(saved):
    packet=saved['packet']
    canonical=json.dumps(packet,sort_keys=True,separators=(',',':'),ensure_ascii=True)
    return {
        'format':'pick-up-here-restart-brief',
        'format_version':1,
        'app_version':VERSION,
        'engine_version':packet['version'],
        'collected_at':saved['collected_at'],
        'exported_at':timestamp(),
        'repository':packet['repository'],
        'requested_focus':saved['focus'],
        'proposal_state':saved.get('proposal_state','not_requested'),
        'proposal':saved.get('proposal'),
        'evidence_packet':packet,
        'evidence_packet_sha256':hashlib.sha256(canonical.encode()).hexdigest(),
        'checksum_encoding':'UTF-8 JSON; sorted keys; separators comma/colon; ensure_ascii=true; evidence_packet only',
        'review_status':{
            'repository_rechecked_before_export':True,
            'recheck_scope':'Same bounded collector output, not every repository byte or runtime state.',
            'human_accuracy':'not_recorded',
            'human_usefulness':'not_recorded',
            'tests_executed_by_app':False,
            'historical_after_download':True,
        },
        'read_me':'Saved observations and a proposed inspection, not current repository state. Recollect before relying on it later. This file contains repository excerpts; review before sharing. The checksum detects packet changes; it does not authenticate authorship.',
    }
