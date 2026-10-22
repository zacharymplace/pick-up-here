"""Pick Up Here: a local repository restart assistant."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import threading
import webbrowser
import urllib.error
import urllib.request
import pickup
from release import VERSION
from brief_export import export_brief, timestamp
from brief_history import open_brief, compare_brief, MAX_BRIEF_BYTES
from repository_match import verify_ancestry
from comparison_export import export_comparison,open_comparison,MAX_COMPARISON_BYTES

HERE=Path(__file__).resolve().parent

def choose_folder():
    """Open one macOS folder dialog. Fixed script; never interpolate user content."""
    if sys.platform!='darwin':
        raise RuntimeError('Folder browsing currently requires macOS. Paste a folder path instead.')
    script='''try
return POSIX path of (choose folder with prompt "Choose your Git repository root")
on error number -128
return ""
end try'''
    try:
        result=subprocess.run(['/usr/bin/osascript','-e',script],capture_output=True,text=True,timeout=120)
    except subprocess.TimeoutExpired:
        raise RuntimeError('Folder selection timed out. Try again or paste a folder path.')
    except OSError:
        raise RuntimeError('The native folder dialog could not start. Paste a folder path instead.')
    if result.returncode:
        raise RuntimeError('The native folder dialog could not finish. Paste a folder path instead.')
    value=result.stdout.rstrip('\r\n')
    if not value:return {'cancelled':True}
    return {'cancelled':False,'repository':repository_path(value)}

def repository_path(value):
    if not isinstance(value,str) or not value.strip() or len(value)>2048:
        raise ValueError('Enter a repository folder path, not a terminal command.')
    value=value.strip()
    if value.startswith(('"',"'")) or '\\ ' in value:
        try:parts=shlex.split(value)
        except ValueError:raise ValueError('The pasted path has an unmatched quote.')
        if len(parts)!=1:raise ValueError('Paste just one repository folder path.')
        value=parts[0]
    path=Path(value).expanduser()
    if not path.is_absolute():raise ValueError('Enter an absolute folder path or a path beginning with ~/.')
    if path.is_file():raise ValueError('This is a file. Enter its repository folder instead.')
    if not path.is_dir():raise ValueError('Folder not found. In Finder, copy the repository folder as a pathname and paste it here.')
    return str(path)

def model_readiness():
    """Inspect installed model names only; never pull or run a model."""
    try:
        client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with client.open('http://127.0.0.1:11434/api/tags',timeout=2) as response:
            raw=response.read(1048577)
        if len(raw)>1048576:raise ValueError('Model listing too large')
        data=json.loads(raw)
        models=data['models']
        if not isinstance(models,list) or any(not isinstance(m,dict) for m in models):raise ValueError('Invalid model listing')
        installed=any(m.get('name')=='gemma3:4b' or m.get('model')=='gemma3:4b' for m in models)
        return {'state':'ready' if installed else 'model_missing','message':
            'Ollama is reachable and gemma3:4b is installed. Inference has not been tested.' if installed else
            'Ollama is reachable. Install the required model in Terminal: ollama pull gemma3:4b'}
    except (OSError,ValueError,KeyError,TypeError):
        return {'state':'unavailable','message':'Could not read the local Ollama model list. Open Ollama, then check again. Facts-only inspection still works.'}

class AppServer(ThreadingHTTPServer):
    def __init__(self, port=8765, repository=''):
        super().__init__(('127.0.0.1',port),Handler)
        self.origin=f'http://127.0.0.1:{self.server_port}'
        self.token=secrets.token_hex(32)
        self.repository=repository
        self.snapshots={}
        self.histories={}
        self.comparison=None
        self.gate=threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,code,data,mime='application/json'):
        body=json.dumps(data).encode() if mime=='application/json' else data
        self.send_response(code)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def trusted_host(self):
        if self.headers.get('Host')!=self.server.origin.removeprefix('http://'):
            self.send(403,{'error':'Open this app using its printed 127.0.0.1 URL.'});return False
        return True
    def do_GET(self):
        if not self.trusted_host():return
        if self.path=='/api/session':
            self.send(200,{'token':self.server.token,'repository':self.server.repository,'model':'gemma3:4b','app_version':VERSION});return
        assets={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if self.path not in assets:self.send(404,{'error':'Not found'});return
        name,mime=assets[self.path]
        self.send(200,(HERE/'ui'/name).read_bytes(),mime)
    def do_POST(self):
        if not self.trusted_host():return
        if self.headers.get('Origin')!=self.server.origin or not secrets.compare_digest(self.headers.get('X-Pickup-Token',''),self.server.token):
            self.send(403,{'error':'Refresh the local app before trying again.'});return
        if self.path not in ('/api/facts','/api/propose','/api/readiness','/api/choose-folder','/api/export','/api/open-brief','/api/compare','/api/export-comparison','/api/open-comparison'):
            self.send(404,{'error':'Not found'});return
        if not self.server.gate.acquire(blocking=False):
            self.send(409,{'error':'An inspection is already running. Wait for it to finish.'});return
        try:
            try:
                length=int(self.headers.get('Content-Length','0'))
                maximum=MAX_COMPARISON_BYTES+4096 if self.path=='/api/open-comparison' else MAX_BRIEF_BYTES+4096 if self.path=='/api/open-brief' else 4096
                if not 0<length<=maximum:raise ValueError(f'Request must be 1–{maximum} bytes')
                request=json.loads(self.rfile.read(length))
                if not isinstance(request,dict):raise ValueError('Request must be an object')
            except (ValueError,UnicodeError,RecursionError) as exc:
                self.send(400,{'error':str(exc)});return
            if self.path=='/api/open-comparison':
                try:view=open_comparison(request.get('comparison_export'))
                except (ValueError,TypeError,KeyError,RecursionError):
                    self.send(400,{'error':'Comparison not opened: unsupported format, invalid evidence, checksum mismatch, or results disagree with recomputed evidence. Existing views are retained.'});return
                self.send(200,{'view':view});return
            if self.path=='/api/open-brief':
                try:history=open_brief(request.get('brief'))
                except (ValueError,TypeError,RecursionError):
                    self.send(400,{'error':'Could not open brief: unsupported format, invalid fields, or evidence checksum mismatch. Current facts and any previously opened brief are retained.'});return
                key=secrets.token_hex(16)
                self.server.histories={key:history}
                self.server.comparison=None
                self.send(200,{'history':key,'view':history['view']});return
            if self.path=='/api/choose-folder':
                try:self.send(200,choose_folder())
                except (RuntimeError,ValueError) as exc:self.send(503,{'error':str(exc)})
                return
            if self.path=='/api/readiness':
                self.send(200,model_readiness());return
            if self.path=='/api/facts':
                self.server.comparison=None
                repository=request.get('repository','');focus=request.get('focus','')
                try:repository=repository_path(repository)
                except (ValueError,RuntimeError) as exc:
                    self.send(400,{'error':str(exc)});return
                try:packet=pickup.collect(repository,focus)
                except Exception as exc:
                    self.send(400,{'error':str(exc)});return
                key=secrets.token_hex(16)
                self.server.snapshots={key:{'path':repository,'focus':focus,'packet':packet,'collected_at':timestamp()}}
                self.send(200,{'snapshot':key,'repository':repository,'facts':pickup.repository_facts(packet),'evidence':packet['evidence'],'limits':packet['limits']})
            else:
                key=request.get('snapshot')
                if not isinstance(key,str) or key not in self.server.snapshots:
                    self.send(409,{'error':'Collect a fresh facts snapshot first.'});return
                saved=self.server.snapshots[key]
                def current():return pickup.collect(saved['path'],saved['focus'])==saved['packet']
                if self.path in ('/api/compare','/api/export-comparison'):
                    history_id=request.get('history')
                    if not isinstance(history_id,str) or history_id not in self.server.histories:
                        self.send(409,{'error':'Open a saved brief before comparing.'});return
                    previous=self.server.comparison
                    self.server.comparison=None
                    if self.path=='/api/export-comparison' and (not previous or previous['snapshot']!=key or previous['history']!=history_id):
                        self.send(409,{'error':'Complete a successful comparison of these facts and this brief before exporting.'});return
                    try:
                        if not current():
                            self.send(409,{'error':'Repository changed since collection. Collect fresh facts before comparing.'});return
                        history=self.server.histories[history_id]
                        historical_head=history['view']['head']
                        fresh_head=pickup.repository_facts(saved['packet'])['head']['value']
                        match=verify_ancestry(saved['path'],historical_head,fresh_head)
                        if not current():
                            self.send(409,{'error':'Repository changed during ancestry verification. Collect fresh facts before comparing.'});return
                        comparison=compare_brief(history,saved['packet'],saved['focus'],match)
                        if self.path=='/api/export-comparison' and comparison!=previous['result']:
                            self.send(409,{'error':'Comparison changed. Compare again before exporting.'});return
                    except ValueError as exc:
                        self.send(409,{'error':str(exc)});return
                    except Exception:
                        self.send(409,{'error':'Could not recheck current observations. Collect fresh facts before comparing.'});return
                    self.server.comparison={'snapshot':key,'history':history_id,'result':comparison}
                    if self.path=='/api/export-comparison':
                        self.send(200,{'filename':'pick-up-here-comparison-'+fresh_head[:12]+'.json',
                            'comparison_export':export_comparison(history,saved,comparison)});return
                    self.send(200,comparison);return
                if self.path=='/api/export':
                    try:
                        if not current():
                            self.send(409,{'error':'Repository changed since collection. Refresh facts before saving a brief.'});return
                    except Exception:
                        self.send(409,{'error':'Could not recheck the repository. Refresh facts before saving a brief.'});return
                    head=pickup.repository_facts(saved['packet'])['head']['value'][:12]
                    self.send(200,{'filename':f'pick-up-here-{head}.json','brief':export_brief(saved)});return
                saved['proposal']=None
                saved['proposal_state']='failed'
                try:
                    if not current():
                        self.send(409,{'error':'Repository changed since collection. Refresh facts first.'});return
                    result=pickup.generate(saved['packet'])
                    if not current():
                        self.send(409,{'error':'Repository changed during inference. Refresh facts first.'});return
                except Exception as exc:
                    self.send(503,{'error':'No AI proposal produced. Facts remain available. Check that Ollama is running with gemma3:4b installed. Details: '+str(exc)});return
                saved['proposal']={'interpretation':result['ai_interpretation'],'qualification':result['qualification'],
                    'model':result.get('model','gemma3:4b'),'selection':result.get('model_selection')}
                saved['proposal_state']='accepted'
                self.send(200,{'interpretation':result['ai_interpretation'],'qualification':result['qualification']})
        finally:self.server.gate.release()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',action='version',version='Pick Up Here '+VERSION)
    parser.add_argument('--repository',default='')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--open',action='store_true',help='Open the local screen in your browser')
    args=parser.parse_args()
    if not 0<=args.port<=65535:
        parser.error('Port must be between 0 and 65535.')
    try:
        server=AppServer(args.port,args.repository)
    except OSError as exc:
        parser.error(f'Could not start the local app: {exc}. Try --port 8766.')
    with server:
        print('Pick Up Here '+VERSION+': '+server.origin,flush=True)
        print('Keep this terminal open. Press Ctrl+C to stop.',flush=True)
        if args.open:
            def open_screen():
                try:opened=webbrowser.open(server.origin)
                except Exception:opened=False
                if not opened:print('Open the printed URL manually in your browser.',flush=True)
            threading.Thread(target=open_screen,daemon=True).start()
        try:server.serve_forever()
        except KeyboardInterrupt:pass

if __name__=='__main__':main()
