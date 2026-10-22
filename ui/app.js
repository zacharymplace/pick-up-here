'use strict';
const $=id=>document.getElementById(id);let token='',snapshot='',savedBriefId='',savedTopic='',comparisonReady=false;
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=String(text);if(cls)e.className=cls;return e;};
function status(text){$('status').textContent=text;}
function error(text){$('error').textContent=text||'';$('error').hidden=!text;}
function setBusy(busy){for(const id of ['browse','collect','repository','focus','readiness','brief-file','comparison-file'])$(id).disabled=busy||!token;$('save-comparison').disabled=busy||!comparisonReady;$('use-topic').disabled=busy||!savedBriefId;$('refresh-compare').disabled=busy||!token||!savedBriefId;$('propose').disabled=busy||!snapshot;$('save-brief').disabled=busy||!snapshot;$('compare').disabled=busy||!snapshot||!savedBriefId;}
function clearComparison(){comparisonReady=false;$('save-comparison').disabled=true;$('comparison').replaceChildren();}
function requestError(exc){return exc instanceof TypeError?'Cannot reach the local app. Keep its Terminal window open, then reload the printed local URL.':exc.message;}
async function post(path,body){const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),195000);try{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Pickup-Token':token},body:JSON.stringify(body),signal:controller.signal});const data=await r.json();if(!r.ok)throw new Error(data.error||'Inspection failed');return data;}finally{clearTimeout(timer);}}
function ref(id,historical=false,prefix=null){
    const target=(prefix||(historical?'historical-':'evidence-'))+id;
    const a=node('a',(historical?'Saved ':prefix?'Later ':'Fresh ')+id);a.href='#'+target;
    a.addEventListener('click',event=>{
        const d=$(target);if(!d)return;
        event.preventDefault();
        for(let parent=d;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;
        d.querySelector('summary').focus();d.scrollIntoView({block:'center'});
    });return a;
}
function row(label,value,pill=false){const e=node('div',undefined,'factrow');e.append(node('span',label),node('span',value,pill?'pill':''));return e;}
function render(data){clearComparison();const f=data.facts;const el=$('facts');el.replaceChildren();el.append(row('Working tree',f.working_tree.state,true),row('Commit',f.head.value.slice(0,12)),row('Handoff context',f.notes.context==='available'?'Notes collected':'Missing from packet'));el.append(node('p',f.test_verification,'small'));const list=node('div');for(const [path,state] of Object.entries(f.notes.inventory)){list.append(row(path,state.replaceAll('_',' ')));}el.append(list);if(f.entrypoints.length){el.append(node('h3','Observed entry points'));for(const e of f.entrypoints){const item=node('div',undefined,'entry');item.append(node('b',e.script_name),node('code',e.path));el.append(item);}}if(f.recorded_tasks.length){el.append(node('h3','Recorded unchecked items'));for(const t of f.recorded_tasks.slice(0,8)){const item=node('div',undefined,'entry');item.append(node('code',t.path+':'+t.line),node('div',t.quote),node('div','Completion unverified','small'));el.append(item);}}const evidence=$('evidence');evidence.replaceChildren();for(const e of data.evidence){const d=node('details');d.id='evidence-'+e.id;d.append(node('summary',e.id+' · '+e.source),node('pre',e.text));if(e.truncated)d.append(node('p','This evidence excerpt was truncated.','small'));evidence.append(d);}$('limits').replaceChildren(...data.limits.map(x=>node('li',x)));$('save-section').hidden=false;$('save-status').textContent='';$('results').hidden=false;$('evidence-section').hidden=false;}
function invalidate(){snapshot='';clearComparison();$('compare').disabled=true;$('save-section').hidden=true;$('save-brief').disabled=true;$('results').hidden=true;$('evidence-section').hidden=true;$('proposal').replaceChildren();$('propose').disabled=true;error('');status('Project selection changed. Inspect it to collect a fresh snapshot.');}
$('repository').addEventListener('input',invalidate);$('focus').addEventListener('input',invalidate);
$('use-topic').addEventListener('click',()=>{
    if(!savedBriefId)return;
    if($('focus').value===savedTopic){status('The saved topic is already selected. Current facts are retained.');return;}
    $('focus').value=savedTopic;invalidate();
    status('Saved topic applied. Inspect repository to collect a fresh snapshot; no AI was run.');$('collect').focus();
});
$('brief-file').addEventListener('change',async()=>{
    const file=$('brief-file').files[0];if(!file)return;
    setBusy(true);$('history-status').textContent='Checking the saved file…';
    try{
        if(file.size>8*1024*1024)throw new Error('Brief exceeds the 8 MiB import limit.');
        const brief=JSON.parse(await file.text());
        const result=await post('/api/open-brief',{brief});savedBriefId=result.history;
        const view=result.view;savedTopic=view.requested_focus;const box=$('historical');box.replaceChildren();
        box.append(node('p','Historical context — file supplied, not current observations','eyebrow'),row('Repository label',view.repository),row('Saved commit',view.head.slice(0,12)),row('Collection time (file reported)',view.collected_at),row('Saved topic',view.requested_focus||'(none)'));
        box.append(node('p',view.checksum_status,'small'),node('p',view.authority,'small'));
        box.append(node('h3','Saved proposal text — not revalidated'),node('p',view.proposal_text_from_file||'No accepted proposal text in this file.','muted'));
        for(const [path,state] of Object.entries(view.note_inventory))box.append(row(path,state.replaceAll('_',' ')));
        const sources=node('details');sources.append(node('summary','Saved evidence (historical)'));
        for(const e of view.evidence){const d=node('details');d.id='historical-'+e.id;d.append(node('summary','Saved '+e.id+' · '+e.source),node('pre',e.text));sources.append(d);}
        box.append(sources);box.hidden=false;clearComparison();
        $('history-status').textContent='Historical brief opened. Select its repository and collect facts with the same topic, then compare. Comparison requires verified local Git ancestry; repository labels need not match.';
    }catch(exc){$('history-status').textContent='Brief not opened. '+exc.message+' Current facts and any previous historical brief are retained.';}
    finally{$('brief-file').value='';setBusy(false);}
});
function returnSummary(result,reason,target=$('comparison'),id='return-summary'){
    const box=node('section');box.id=id;box.setAttribute('aria-label','Return summary');
    box.append(node('h3','Return summary'));
    if(!result){
        box.append(row('Changed retained sources','Not determined'),row('Identical retained sources','Not determined'),node('p','Could not compare: '+reason));
        box.append(node('p','No comparison result is available. The saved brief remains historical.','small'));
    }else{
        box.append(row('Changed retained sources',result.changed_sources.length),row('Identical retained sources',result.unchanged_source_count),row('Newly / no longer collected',result.added_sources.length+' / '+result.removed_sources.length));
        const unpaired=result.added_sources.length+result.removed_sources.length;
        box.append(node('p','Could not compare both sides: '+unpaired+' source labels appear in only one collection. This does not establish file creation or deletion.','small'));
        if(result.truncated_sources.length)box.append(node('p','Full source text unavailable: '+result.truncated_sources.length+' source labels have truncated collected evidence. Only retained text was compared.','small'));
        const clipped=result.diff_previews.filter(d=>d.input_truncated||d.diff_truncated).length;
        if(clipped||result.diff_previews_omitted)box.append(node('p','Preview limits: '+clipped+' clipped previews; '+result.diff_previews_omitted+' source previews omitted. These limits do not change the retained-text comparison counts.','small'));
        const identical=node('details');identical.append(node('summary','Identical retained sources ('+result.unchanged_sources.length+')'));
        const list=node('ul');for(const source of result.unchanged_sources)list.append(node('li',source));if(!result.unchanged_sources.length)list.append(node('li','None'));identical.append(list);box.append(identical);
        box.append(node('p','Scope: collected excerpts only. Uncollected content, runtime behavior, tests, and live connections were not compared. Identical excerpts do not prove identical files.','small'));
    }
    target.append(box);
}
$('comparison-file').addEventListener('change',async()=>{
    const file=$('comparison-file').files[0];if(!file)return;
    setBusy(true);$('comparison-file').disabled=true;$('archive-status').textContent='Checking integrity and recomputing the saved comparison…';
    try{
        if(file.size>20*1024*1024)throw new Error('Comparison exceeds the 20 MiB import limit.');
        const result=await post('/api/open-comparison',{comparison_export:JSON.parse(await file.text())});
        const view=result.view;const box=node('div');
        box.append(node('p','Historical comparison — file supplied, no current observations','eyebrow'),node('p',view.integrity,'small'),node('p',view.authority,'small'),row('Export time (file reported)',view.exported_at_file_reported));
        for(const [name,label,prefix] of [['historical','Saved side','archive-before-'],['fresh','Later side','archive-after-']]){
            const side=view[name];box.append(node('h3',label),row('Repository label',side.repository),row('Commit (file reported)',side.head.slice(0,12)),row('Collected (file reported)',side.collected_at),row('Topic',side.requested_focus||'(none)'));
            const evidence=node('details');evidence.append(node('summary',label+' evidence ('+side.evidence.length+')'));
            for(const item of side.evidence){const d=node('details');d.id=prefix+item.id;d.append(node('summary',item.id+' · '+item.source),node('pre',item.text));if(item.truncated)d.append(node('p','Retained excerpt was truncated.','small'));evidence.append(d);}box.append(evidence);
        }
        returnSummary(view.comparison,null,box,'archive-summary');
        box.append(node('h3','Recomputed retained-text differences'));
        for(const diff of view.comparison.diff_previews){
            const d=node('details');d.append(node('summary',diff.source+' · '+diff.kind));
            const links=node('div',undefined,'refs');for(const id of diff.historical_evidence)links.append(ref(id,true,'archive-before-'));for(const id of diff.fresh_evidence)links.append(ref(id,false,'archive-after-'));d.append(links,node('pre',diff.text||'No visible line difference in this bounded preview. Inspect the retained evidence.'));box.append(d);
        }
        $('archive-view').replaceChildren(box);$('archive-view').hidden=false;
        $('archive-status').textContent='Historical comparison opened. Integrity checked and retained-text results recomputed; current facts and saved brief are unchanged.';
    }catch(exc){$('archive-status').textContent='Comparison not opened. '+requestError(exc)+' Existing historical view and current facts are retained.';}
    finally{$('comparison-file').value='';setBusy(false);$('comparison-file').disabled=!token;$('comparison-file').focus();}
});
async function compareFresh(){
    clearComparison();$('history-status').textContent='Rechecking fresh observations before comparing…';
    try{
        const result=await post('/api/compare',{snapshot,history:savedBriefId});const box=$('comparison');
        returnSummary(result);
        box.append(node('h3','Historical → fresh observations'),row('Historical repository label',result.historical_repository_label),row('Fresh repository label',result.fresh_repository_label),row('Historical commit',result.historical_commit.slice(0,12)),row('Fresh commit',result.fresh_commit.slice(0,12)));
        for(const [key,label] of [['changed_sources','Changed collected sources'],['added_sources','Newly collected sources'],['removed_sources','No longer collected sources']]){
            box.append(node('h3',label+' ('+result[key].length+')'));
            const list=node('ul');for(const source of result[key])list.append(node('li',source));if(!result[key].length)list.append(node('li','None'));box.append(list);
        }
        box.append(node('h3','Inspect the retained-text changes'));
        for(const diff of result.diff_previews){
            const section=node('details');section.append(node('summary',diff.source+' · '+diff.kind));
            section.append(node('p','Saved evidence: '+(diff.historical_evidence.join(', ')||'none')+' · Fresh evidence: '+(diff.fresh_evidence.join(', ')||'none'),'small'));
            const links=node('div',undefined,'refs');
            for(const id of diff.historical_evidence)links.append(ref(id,true));
            for(const id of diff.fresh_evidence)links.append(ref(id));
            section.append(links);
            section.append(node('pre',diff.text||'The retained source differs, but this line-based preview does not show the change (for example, a final newline or omitted text). Inspect the separate evidence views.'));
            if(diff.input_truncated||diff.diff_truncated)section.append(node('p','Preview truncated. Full retained evidence remains available in the separate evidence views.','small'));
            section.append(node('p',diff.note,'small'));box.append(section);
        }
        if(result.diff_previews_omitted)box.append(node('p',result.diff_previews_omitted+' additional source previews omitted by the 12-source limit.','small'));
        box.append(node('p',result.unchanged_source_count+' collected sources have identical retained text.','small'),node('p',result.scope,'small'),node('p',result.identity,'small'));
        comparisonReady=true;
        $('history-status').textContent='Comparison ready. Both evidence sets remain available separately; no AI or project command was run.';
    }catch(exc){const reason=requestError(exc);error(reason);$('comparison').replaceChildren();returnSummary(null,reason);$('history-status').textContent='Comparison unavailable. Historical context and current facts are retained.';}
}
$('compare').addEventListener('click',async()=>{
    setBusy(true);error('');try{await compareFresh();}finally{setBusy(false);$('compare').focus();}
});
$('save-comparison').addEventListener('click',async()=>{
    if(!comparisonReady)return;
    setBusy(true);error('');$('history-status').textContent='Rechecking facts and Git ancestry before export…';
    try{
        const result=await post('/api/export-comparison',{snapshot,history:savedBriefId});
        const url=URL.createObjectURL(new Blob([JSON.stringify(result.comparison_export,null,2)+'\n'],{type:'application/json'}));
        const link=node('a');link.href=url;link.download=result.filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
        $('history-status').textContent='Comparison download requested with both evidence packets. It is historical; review private excerpts before sharing. This is separate from a restart brief.';
    }catch(exc){comparisonReady=false;error(requestError(exc));$('history-status').textContent='No comparison downloaded. Evidence remains available. Collect and compare again before exporting.';}
    finally{setBusy(false);$(comparisonReady?'save-comparison':'refresh-compare').focus();}
});
$('refresh-compare').addEventListener('click',async()=>{
    if(!savedBriefId||!token)return;
    $('focus').value=savedTopic;invalidate();setBusy(true);
    status('Collecting fresh facts with the saved topic…');
    $('history-status').textContent='Collecting from the selected folder before verifying Git ancestry…';
    try{
        const data=await post('/api/facts',{repository:$('repository').value.trim(),focus:savedTopic});
        snapshot=data.snapshot;render(data);
        status('Fresh facts collected with the saved topic. No AI was run.');
        await compareFresh();
    }catch(exc){const reason=requestError(exc);error(reason);returnSummary(null,'Fresh collection failed. '+reason);status('No new snapshot collected.');$('history-status').textContent='Comparison stopped: fresh collection failed. The saved brief remains available; check the selected folder and retry.';}
    finally{setBusy(false);$('refresh-compare').focus();}
});
$('save-brief').addEventListener('click',async()=>{
    setBusy(true);error('');$('save-status').textContent='Rechecking the collected snapshot…';
    try{
        const result=await post('/api/export',{snapshot});
        const url=URL.createObjectURL(new Blob([JSON.stringify(result.brief,null,2)+'\n'],{type:'application/json'}));
        const link=node('a');link.href=url;link.download=result.filename;document.body.append(link);link.click();link.remove();
        setTimeout(()=>URL.revokeObjectURL(url),1000);
        $('save-status').textContent='Download requested. This brief is a historical snapshot; collect fresh facts when you return.';
    }catch(exc){error(requestError(exc));$('save-status').textContent='No brief downloaded. Your collected evidence remains available for review.';}
    finally{setBusy(false);$('save-brief').focus();}
});
$('browse').addEventListener('click',async()=>{
    if(!token)return;
    setBusy(true);error('');status('Choose a repository folder in the native dialog. It may appear behind your browser.');
    let selected=false;
    try{
        const result=await post('/api/choose-folder',{});
        if(result.cancelled){status('Folder selection cancelled. Your previous selection and evidence are retained.');}
        else{$('repository').value=result.repository;invalidate();selected=true;status('Folder selected. Inspect repository to collect a fresh snapshot.');}
    }catch(exc){error(requestError(exc));status('Folder selection did not change. You can still paste a path.');}
    finally{setBusy(false);$(selected?'collect':'browse').focus();}
});
$('inspect-form').addEventListener('submit',async e=>{e.preventDefault();setBusy(true);error('');snapshot='';clearComparison();$('save-section').hidden=true;$('results').hidden=true;$('evidence-section').hidden=true;$('proposal').replaceChildren();$('collect').disabled=true;$('propose').disabled=true;$('repository').disabled=true;$('focus').disabled=true;status('Collecting bounded, read-only evidence…');try{const data=await post('/api/facts',{repository:$('repository').value.trim(),focus:$('focus').value.trim()});snapshot=data.snapshot;render(data);$('propose').disabled=false;status('Facts collected. Review them first, then request one local AI proposal.');}catch(exc){error(requestError(exc));status('No new snapshot collected.');}finally{setBusy(false);$('collect').disabled=false;$('repository').disabled=false;$('focus').disabled=false;}});
$('propose').addEventListener('click',async()=>{setBusy(true);error('');$('proposal').replaceChildren();$('propose').disabled=true;$('collect').disabled=true;$('repository').disabled=true;$('focus').disabled=true;status('Local Gemma is choosing an inspection. This may take a minute; evidence stays open for review.');try{const data=await post('/api/propose',{snapshot});const box=$('proposal');const i=data.interpretation;box.append(node('p',i.proposed_next_action.text,'next'));for(const f of i.interpretations)box.append(node('p',f.text,'muted'));const ids=new Set(i.interpretations.map(x=>x.evidence));ids.add(i.proposed_next_action.evidence);const a=i.proposed_next_action;if(a.file_evidence)ids.add(a.file_evidence);if(a.entrypoint){ids.add(a.entrypoint.manifest_evidence);for(const lead of a.entrypoint.reexport_leads||[]){ids.add(lead.reexport_evidence);ids.add(lead.definition_evidence);}}const refs=node('div',undefined,'refs');for(const id of ids)refs.append(ref(id));box.append(refs,node('p','Proposed inspection only. No project command was executed.','small'));status('Proposal ready. Verify its supporting evidence before deciding what to inspect.');}catch(exc){error(exc.name==='AbortError'?'The request timed out. Facts are still available; wait for the running inspection to finish before retrying.':requestError(exc));status('Facts retained. No AI proposal accepted.');}finally{setBusy(false);$('propose').disabled=false;$('collect').disabled=false;$('repository').disabled=false;$('focus').disabled=false;}});
$('readiness').addEventListener('click',async()=>{if(!token){$('model-status').textContent='The app is still connecting. Try again when ready.';return;}$('readiness').disabled=true;$('model-status').textContent='Checking the local model list…';try{const result=await post('/api/readiness',{});$('model-status').textContent=result.message;}catch(exc){$('model-status').textContent=exc.message;}finally{$('readiness').disabled=false;}});
fetch('/api/session').then(r=>{if(!r.ok)throw new Error('Cannot connect to the local app');return r.json();}).then(data=>{$('release').textContent='v'+data.app_version+' · Release candidate · Acceptance pending';token=data.token;$('repository').value=data.repository;setBusy(false);status('Ready. Facts-only collection works without a model. AI proposals use local '+data.model+'.');}).catch(exc=>{error(requestError(exc));status('Start app.py and open its printed local URL.');});
