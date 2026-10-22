"""README-documented Python scripts; bounded static inspection, never execution."""
import ast
import posixpath
import re
from details import tokens

def inspect_python_entrypoints(root, files, notes, add, focus=''):
    observed={f['path']:f for f in files}
    def read(path):
        f=root/path
        if path not in observed or f.is_symlink() or not f.resolve().is_relative_to(root) or not f.is_file():return None
        if f.stat().st_size>64000:return None
        try:return f.read_text(encoding='utf-8')
        except (OSError,UnicodeError):return None
    def prefix(source):return '\n'.join(source.splitlines()[:80])[:6000]
    def parse(source):
        try:return ast.parse(source)
        except (SyntaxError,ValueError,RecursionError):return None
    def reexports(leads):
        resolved=[]
        for lead in leads:
            if not lead['path'].endswith('/__init__.py') or not lead.get('imported_symbols'):continue
            source=read(lead['path'])
            if source is None:continue
            excerpt=prefix(source);tree=parse(source)
            if tree is None:continue
            for item in tree.body:
                if not isinstance(item,ast.ImportFrom) or not item.module:continue
                literal=ast.get_source_segment(source,item)
                if not literal or literal not in excerpt:continue
                if item.level==1:
                    base=posixpath.join(posixpath.dirname(lead['path']),item.module.replace('.','/'))
                elif item.level==0 and item.module.startswith(lead['specifier']+'.'):
                    base=('src/' if lead['path'].startswith('src/') else '')+item.module.replace('.','/')
                else:continue
                for alias in item.names:
                    exported=alias.asname or alias.name
                    if alias.name=='*' or exported not in lead['imported_symbols']:continue
                    # Exactly one implementation-module hop; no package recursion.
                    target=base+'.py';target_source=read(target)
                    if target_source is None:continue
                    target_excerpt=prefix(target_source);target_tree=parse(target_source)
                    if target_tree is None:continue
                    definition=next((n for n in target_tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name==alias.name),None)
                    if definition is None or definition.lineno>len(target_excerpt.splitlines()):continue
                    if alias.name not in target_excerpt.splitlines()[definition.lineno-1]:continue
                    if any(x['path']==target and x['symbol']==alias.name for x in resolved):continue
                    resolved.append({'path':target,'file_id':observed[target]['id'],'symbol':alias.name,'exported_as':exported,
                        'via':lead['path'],'reexport_line':item.lineno,'definition_line':definition.lineno,
                        'reexport_evidence':add(f"{lead['path']}:bounded-prefix",excerpt),
                        'definition_evidence':add(f'{target}:bounded-prefix',target_excerpt),
                        'reexport_excerpt_truncated':len(excerpt)<len(source),
                        'definition_excerpt_truncated':len(target_excerpt)<len(target_source),
                        'resolution':'static_named_reexport_and_definition_not_runtime_verified'})
                    if len(resolved)==3:return resolved
        return resolved
    candidates=[]
    for note,text in notes.items():
        for line,quote in enumerate(text.splitlines(),1):
            match=re.fullmatch(r'\s*python(?:3)?\s+(?:\./)?(scripts/[A-Za-z0-9_/-]+\.py)\s*',quote)
            if match and match[1] in observed:
                path=match[1]
                candidates.append((-len(tokens(focus)&tokens(path)),path,note,line,quote))
    entries=[];seen=set()
    for score,path,note,line,quote in sorted(candidates):
        if path in seen:continue
        seen.add(path)
        source=read(path)
        if source is None:continue
        excerpt=prefix(source)
        tree=parse(excerpt)
        leads=[]
        for item in sorted(ast.walk(tree),key=lambda n:getattr(n,'lineno',0)) if tree else []:
            modules=[]
            if isinstance(item,ast.Import):modules=[a.name for a in item.names]
            elif isinstance(item,ast.ImportFrom) and not item.level and item.module:modules=[item.module]
            for module in modules:
                base=module.replace('.','/')
                for target in [f'src/{base}.py',f'src/{base}/__init__.py',f'{base}.py',f'{base}/__init__.py']:
                    if target not in observed or read(target) is None:continue
                    if not any(l['path']==target for l in leads):
                        leads.append({'path':target,'file_id':observed[target]['id'],'specifier':module,'line':item.lineno,
                            'quote':excerpt.splitlines()[item.lineno-1],
                            'imported_symbols':sorted(a.name for a in item.names if a.name!='*') if isinstance(item,ast.ImportFrom) else [],
                            'resolution':'static_module_path_candidate_not_runtime_verified'})
                    elif isinstance(item,ast.ImportFrom):
                        existing=next(l for l in leads if l['path']==target)
                        existing['imported_symbols']=sorted(set(existing['imported_symbols'])|{a.name for a in item.names if a.name!='*'})
                    break
        manifest_evidence=add(f'{note}:line:{line}',quote)
        evidence=add(f'{path}:bounded-prefix',excerpt)
        entries.append({'manifest':note,'script_name':path,'command_literal':quote,'manifest_line':line,'manifest_end_line':line,
            'manifest_evidence':manifest_evidence,'target':observed[path]['id'],'path':path,'evidence':evidence,
            'excerpt':excerpt,'excerpt_truncated':len(excerpt)<len(source),'local_import_leads':leads[:3],
            'reexport_leads':reexports(leads[:3]),
            'focus_matches':-score,'authority':'static_source_observation_not_runtime_proof',
            'discovery':'literal_documented_python_command','import_analysis':'parsed_prefix' if tree else 'prefix_not_parseable_no_import_leads'})
        if len(entries)==6:break
    return entries,{'manifest':'allowlisted notes','status':'inspected' if candidates else 'not_observed','focus':focus,
        'entrypoint_count':len(entries),'scope':'Up to 6 tracked documented scripts; 64KB files and 80-line/6000-character prefixes; 3 local module leads and 3 named re-export/definition matches per entry; one implementation hop only; no execution or runtime resolution.'}
