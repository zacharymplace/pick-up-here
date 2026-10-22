"""Static package-script entry points and one-hop local import leads. Never execute."""
import json
import posixpath
import re
from details import tokens

CODE_SUFFIXES = ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.py', '.sh')

def members(text, start=0):
    decoder = json.JSONDecoder()
    i = start
    while text[i].isspace(): i += 1
    if text[i] != '{': return
    i += 1
    while True:
        while text[i].isspace(): i += 1
        if text[i] == '}': return
        key_start = i
        key, i = decoder.raw_decode(text, i)
        while text[i].isspace(): i += 1
        if text[i] != ':': raise ValueError('Invalid object member')
        i += 1
        while text[i].isspace(): i += 1
        value_start = i
        value, end = decoder.raw_decode(text, i)
        yield key, value, key_start, value_start, end
        i = end
        while text[i].isspace(): i += 1
        if text[i] == '}': return
        if text[i] != ',': raise ValueError('Invalid object separator')
        i += 1

def inspect_entrypoints(root, files, add, focus=''):
    by_path = {f['path']: f for f in files}
    state = {'manifest': 'package.json', 'status': 'not_observed', 'focus': focus,
             'scope': 'Node package scripts only; up to 6 direct entry points and 3 one-hop import leads per entry; no execution or runtime connectivity verified.'}
    def read(path):
        f=root/path
        if path not in by_path or f.is_symlink() or not f.is_file() or not f.resolve().is_relative_to(root): return None
        if f.stat().st_size>64000: return None
        try: return f.read_text(encoding='utf-8')
        except (UnicodeError, OSError): return None
    text=read('package.json')
    if text is None:
        if 'package.json' in by_path: state['status']='unreadable_or_size_limit'
        return [], state
    try:
        parsed=json.loads(text)
        if not isinstance(parsed,dict) or not isinstance(parsed.get('scripts'),dict):
            state['status']='no_script_object'; return [], state
        scripts_start=None
        for key,value,begin,start,end in members(text):
            if key=='scripts': scripts_start=start
        spans={}
        for name,command,begin,start,end in members(text,scripts_start):
            if isinstance(command,str): spans[name]=(command,begin,end)
    except (ValueError, TypeError, IndexError):
        state['status']='invalid_manifest'; return [], state
    state['status']='inspected'
    choices=[]
    for name,(command,begin,end) in spans.items():
        for path in re.findall(r'(?:\./)?[A-Za-z0-9_@./-]+\.(?:[cm]?[jt]sx?|py|sh)(?![A-Za-z0-9_./-])',command):
            path=path.removeprefix('./')
            if path not in by_path or not path.endswith(CODE_SUFFIXES): continue
            score=len(tokens(focus)&tokens(name+' '+path))
            choices.append((-score,len(command),name,path,command,begin,end))
    entries=[]
    for score,length,name,path,command,begin,end in sorted(choices)[:6]:
        source=read(path)
        if source is None: continue
        line=text.count('\n',0,begin)+1; end_line=text.count('\n',0,end)+1
        manifest_evidence=add(f'package.json:lines:{line}-{end_line}',text[begin:end])
        # Read at most 64 KB and expose only a bounded literal prefix.
        source_lines=source.splitlines()[:80]
        excerpt='\n'.join(source_lines)[:6000]
        source_lines=excerpt.splitlines()
        source_evidence=add(f'{path}:bounded-prefix',excerpt)
        leads=[]
        for number,code in enumerate(source_lines,1):
            if not re.search(r'\b(?:import|from|require)\b',code): continue
            for specifier in re.findall(r'''["'](\.[^"']+)["']''',code):
                proposed=posixpath.normpath(posixpath.join(posixpath.dirname(path),specifier))
                variants=[proposed]
                if proposed.endswith('.js'): variants.extend([proposed[:-3]+'.ts',proposed[:-3]+'.tsx'])
                elif not posixpath.splitext(proposed)[1]: variants.extend(proposed+s for s in ('.ts','.js','.tsx','/index.ts','/index.js'))
                for target in dict.fromkeys(variants):
                    if target not in by_path or not target.endswith(CODE_SUFFIXES): continue
                    leads.append({'path':target,'file_id':by_path[target]['id'],'specifier':specifier,'line':number,
                        'quote':code,'resolution':'literal_observed_path' if target==proposed else 'static_resolution_candidate_not_runtime_verified'})
                    break
        entries.append({'manifest':'package.json','script_name':name,'command_literal':command,
            'manifest_line':line,'manifest_end_line':end_line,'manifest_evidence':manifest_evidence,
            'target':by_path[path]['id'],'path':path,'evidence':source_evidence,
            'excerpt':excerpt,'excerpt_truncated':len(excerpt)<len(source),
            'local_import_leads':leads[:3], 'focus_matches':-score,
            'authority':'static_source_observation_not_runtime_proof'})
    state['entrypoint_count']=len(entries)
    return entries,state
