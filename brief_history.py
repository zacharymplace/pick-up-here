"""Read a historical brief as untrusted data; compare bounded observations only."""
import hashlib
import json
import re
import difflib
from datetime import datetime

MAX_BRIEF_BYTES=8*1024*1024

def canonical(packet):
    return json.dumps(packet,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)

def open_brief(value):
    def text(value,limit):
        if not isinstance(value,str) or len(value)>limit:raise ValueError('Invalid or oversized brief text.')
        return value
    if not isinstance(value,dict) or value.get('format')!='pick-up-here-restart-brief' or type(value.get('format_version')) is not int or value['format_version']!=1:
        raise ValueError('Unsupported restart-brief format. Choose a Pick Up Here version-1 JSON export.')
    packet=value.get('evidence_packet')
    if not isinstance(packet,dict) or packet.get('version')!='0.6':raise ValueError('Unsupported evidence packet version; this viewer supports engine 0.6 exports.')
    digest=hashlib.sha256(canonical(packet).encode()).hexdigest()
    if value.get('evidence_packet_sha256')!=digest:raise ValueError('Evidence packet checksum does not match. The saved packet may have changed.')
    repository=text(packet.get('repository'),256)
    if value.get('repository')!=repository:raise ValueError('Repository labels disagree inside the brief.')
    focus=text(value.get('requested_focus'),256)
    dates={}
    for name in ('collected_at','exported_at'):
        dates[name]=text(value.get(name),80)
        try:
            if datetime.fromisoformat(dates[name]).tzinfo is None:raise ValueError()
        except ValueError:raise ValueError('Brief timestamps must include a timezone.')
    evidence=packet.get('evidence')
    if not isinstance(evidence,list) or not 1<=len(evidence)<=2048:raise ValueError('Invalid evidence list.')
    ids=set();by_source={}
    for item in evidence:
        if not isinstance(item,dict):raise ValueError('Invalid evidence item.')
        eid=text(item.get('id'),16);source=text(item.get('source'),4096);text(item.get('text'),16000)
        if not re.fullmatch(r'E[1-9][0-9]*',eid) or eid in ids:raise ValueError('Invalid or duplicate evidence ID.')
        ids.add(eid);by_source[source]=item['text']
    if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})',by_source.get('git:HEAD','')) or 'git:status' not in by_source:
        raise ValueError('Required Git observations are missing or invalid.')
    if any(sum(e['source']==source for e in evidence)!=1 for source in ('git:HEAD','git:status')):
        raise ValueError('Duplicate Git observations are ambiguous.')
    inventory=packet.get('note_inventory')
    if not isinstance(inventory,dict) or len(inventory)>4:raise ValueError('Invalid note inventory.')
    allowed={'README.md','HANDOFF.md','STATUS.md','docs/HANDOFF.md'}
    states={'collected','missing','empty','skipped_symlink','skipped_outside_repository','skipped_not_regular_file','skipped_size_limit'}
    if set(inventory)!=allowed or any(not isinstance(v,str) or v not in states for v in inventory.values()):raise ValueError('Invalid note availability state.')
    proposal_state=value.get('proposal_state')
    if proposal_state not in ('accepted','failed','not_requested'):raise ValueError('Invalid saved proposal state.')
    proposal=None
    if proposal_state=='accepted':
        try:proposal=text(value['proposal']['interpretation']['proposed_next_action']['text'],16000)
        except (KeyError,TypeError):raise ValueError('Saved proposal text is missing.')
    return {'packet':packet,'focus':focus,'view':{
        'repository':repository,'head':by_source['git:HEAD'],'working_tree':by_source['git:status'],
        'note_inventory':inventory,'requested_focus':focus,**dates,
        'proposal_state_from_file':proposal_state,'proposal_text_from_file':proposal,
        'evidence':evidence,'checksum_status':'Evidence packet checksum matches; authorship and proposal text are not authenticated.',
        'authority':'Historical file content, not fresh observations or human acceptance.'}}

def compare_brief(history,fresh,focus,repository_match=None):
    old=history['packet']
    historical_head=next(e['text'] for e in old['evidence'] if e['source']=='git:HEAD')
    fresh_head=next(e['text'] for e in fresh['evidence'] if e['source']=='git:HEAD')
    if not isinstance(repository_match,dict) or repository_match.get('verified') is not True or repository_match.get('method')!='git_commit_ancestry' or repository_match.get('historical_commit')!=historical_head or repository_match.get('fresh_commit')!=fresh_head:
        raise ValueError('Verified Git ancestry for these saved and fresh commits is required before comparison.')
    if old['version']!=fresh['version']:raise ValueError('Collector versions differ; a like-for-like comparison is unavailable.')
    if history['focus']!=focus:raise ValueError('Topics differ. Collect fresh facts with the saved topic for a like-for-like comparison.')
    return {**compare_evidence(old,fresh),
        'identity':'Git ancestry verified: the saved commit is an ancestor of the selected repository commit. Shared ancestry is not proof of project ownership; clones and forks can share history.',
        'repository_match':repository_match,
        'historical_repository_label':old['repository'],'fresh_repository_label':fresh['repository'],
        'historical_commit':historical_head,'fresh_commit':fresh_head}

def compare_evidence(old,fresh):
    """Pure retained-text comparison; does not establish Git ancestry or freshness."""
    def sources(packet):
        result={}
        for item in packet['evidence']:
            result.setdefault(item['source'],set()).add(item['text'])
        return result
    before=sources(old);after=sources(fresh)
    shared=set(before)&set(after)
    changed=sorted(s for s in shared if before[s]!=after[s])
    added=sorted(set(after)-set(before));removed=sorted(set(before)-set(after))
    previews=[]
    def excerpt(values):
        full='\n\n'.join(sorted(values))
        clipped=''.join(full.splitlines(keepends=True)[:200])[:6000]
        return clipped,clipped!=full
    changes=[(s,'changed') for s in changed]+[(s,'newly collected') for s in added]+[(s,'no longer collected') for s in removed]
    for source,kind in changes[:12]:
        left,left_cut=excerpt(before.get(source,set()));right,right_cut=excerpt(after.get(source,set()))
        lines=list(difflib.unified_diff(left.splitlines(),right.splitlines(),fromfile='historical/'+source,tofile='fresh/'+source,lineterm='',n=3))
        full='\n'.join(lines);preview='\n'.join(lines[:160])[:8000]
        previews.append({'source':source,'kind':kind,'text':preview,
            'historical_evidence':[e['id'] for e in old['evidence'] if e['source']==source],
            'fresh_evidence':[e['id'] for e in fresh['evidence'] if e['source']==source],
            'input_truncated':left_cut or right_cut,'diff_truncated':preview!=full,
            'note':'Multiple excerpts are joined in lexical order. This compares retained excerpts, not whole files.'})
    return {'changed_sources':sorted(s for s in shared if before[s]!=after[s]),
        'diff_previews':previews,'diff_previews_omitted':max(0,len(changes)-12),
        'added_sources':sorted(set(after)-set(before)),'removed_sources':sorted(set(before)-set(after)),
        'unchanged_source_count':sum(before[s]==after[s] for s in shared),
        'unchanged_sources':sorted(s for s in shared if before[s]==after[s]),
        'truncated_sources':sorted({e['source'] for packet in (old,fresh) for e in packet['evidence'] if e.get('truncated')}),
        'scope':'Compared retained source text by source label, not evidence IDs or every repository byte. Unchanged observations do not prove unchanged runtime state.'}
