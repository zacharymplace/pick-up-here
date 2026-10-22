"""Historical comparison package with both bounded evidence sets; no inference."""
import hashlib
from brief_export import timestamp
from brief_history import canonical,open_brief,compare_evidence
from datetime import datetime
from release import VERSION

MAX_COMPARISON_BYTES=20*1024*1024

def open_comparison(value):
    """Validate file integrity and replay text comparison without Git or collection."""
    if not isinstance(value,dict) or value.get('format')!='pick-up-here-return-comparison' or type(value.get('format_version')) is not int or value['format_version']!=1:
        raise ValueError('Unsupported return-comparison format.')
    payload=value.get('payload')
    if not isinstance(payload,dict) or value.get('payload_sha256')!=hashlib.sha256(canonical(payload).encode()).hexdigest():
        raise ValueError('Comparison payload checksum does not match.')
    def date(text):
        if not isinstance(text,str) or len(text)>80:raise ValueError('Invalid comparison timestamp.')
        try:
            if datetime.fromisoformat(text).tzinfo is None:raise ValueError()
        except ValueError:raise ValueError('Comparison timestamps must include a timezone.')
        return text
    exported=date(value.get('exported_at'))
    views=[]
    for name in ('historical','fresh'):
        side=payload.get(name)
        if not isinstance(side,dict):raise ValueError('Both evidence sets are required.')
        packet=side.get('evidence_packet')
        collected=date(side.get('collected_at_file_reported' if name=='historical' else 'collected_at'))
        original_export=date(side.get('exported_at_file_reported')) if name=='historical' else exported
        envelope={'format':'pick-up-here-restart-brief','format_version':1,'evidence_packet':packet,
            'evidence_packet_sha256':side.get('evidence_packet_sha256'),
            'repository':packet.get('repository') if isinstance(packet,dict) else None,
            'requested_focus':side.get('requested_focus'),'collected_at':collected,
            'exported_at':original_export,'proposal_state':'not_requested'}
        views.append(open_brief(envelope)['view'])
    before,after=views
    if before['requested_focus']!=after['requested_focus']:raise ValueError('Saved topics differ.')
    comparison=payload.get('comparison')
    if not isinstance(comparison,dict):raise ValueError('Saved comparison is missing.')
    computed=compare_evidence(payload['historical']['evidence_packet'],payload['fresh']['evidence_packet'])
    for key,result in computed.items():
        if key not in comparison or canonical(comparison[key])!=canonical(result):raise ValueError('Saved comparison disagrees with recomputed evidence: '+key)
    for key,expected in [('historical_commit',before['head']),('fresh_commit',after['head']),('historical_repository_label',before['repository']),('fresh_repository_label',after['repository'])]:
        if comparison.get(key)!=expected:raise ValueError('Comparison labels or commits disagree with the evidence.')
    match=comparison.get('repository_match')
    if not isinstance(match,dict) or match.get('verified') is not True or match.get('method')!='git_commit_ancestry' or match.get('historical_commit')!=before['head'] or match.get('fresh_commit')!=after['head']:
        raise ValueError('Recorded ancestry claim does not bind the included commits.')
    return {'historical':before,'fresh':after,'comparison':computed,'exported_at_file_reported':exported,
        'integrity':'Payload and evidence checksums match; retained-text comparison recomputed and matches. Authorship is not authenticated.',
        'authority':'Historical file evidence only. Git ancestry is a recorded file claim, not reverified here. No repository was inspected and no Git, AI, or project command was run.'}

def export_comparison(history,saved,comparison):
    historical={'collected_at_file_reported':history['view']['collected_at'],
        'exported_at_file_reported':history['view']['exported_at'],
        'requested_focus':history['focus'],'evidence_packet':history['packet']}
    fresh={'collected_at':saved['collected_at'],'requested_focus':saved['focus'],
        'evidence_packet':saved['packet']}
    for side in (historical,fresh):
        side['evidence_packet_sha256']=hashlib.sha256(canonical(side['evidence_packet']).encode()).hexdigest()
    payload={'historical':historical,'fresh':fresh,'comparison':comparison}
    return {'format':'pick-up-here-return-comparison','format_version':1,
        'app_version':VERSION,'exported_at':timestamp(),'payload':payload,
        'payload_sha256':hashlib.sha256(canonical(payload).encode()).hexdigest(),
        'checksum_encoding':'UTF-8 JSON; sorted keys; separators comma/colon; ensure_ascii=true; payload only',
        'review_status':{'historical_after_download':True,'bounded_snapshot_rechecked':True,
            'git_ancestry_rechecked':True,'tests_executed_by_app':False,'human_usefulness':'not_recorded'},
        'read_me':'Historical comparison of retained evidence, not every repository byte or runtime state. '
            'Saved evidence is file supplied; checksums do not authenticate authorship. '
            'Both evidence packets may contain private repository excerpts; review before sharing. '
            'No AI interpretation is included. This comparison format is separate from restart briefs.'}
