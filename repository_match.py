"""Verify local Git ancestry without remotes, writes, or name-based fallback."""
import re
import subprocess

def verify_ancestry(repository,historical_head,fresh_head):
    for value in (historical_head,fresh_head):
        if not isinstance(value,str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})',value):
            raise ValueError('Repository matching requires valid saved and fresh Git commit IDs.')
    command=['git','--no-replace-objects','--no-optional-locks','-c','core.fsmonitor=false','-C',str(repository)]
    try:
        head=subprocess.run(command+['rev-parse','HEAD'],capture_output=True,text=True,timeout=10)
        if head.returncode or head.stdout.strip()!=fresh_head:raise ValueError('Selected repository HEAD changed. Collect fresh facts before comparing.')
        match=subprocess.run(command+['merge-base','--is-ancestor',historical_head,fresh_head],capture_output=True,timeout=10)
    except (OSError,subprocess.TimeoutExpired):
        raise ValueError('Could not verify local Git ancestry. Historical context remains available; comparison is blocked.')
    if match.returncode:
        raise ValueError('Saved commit is not verified as an ancestor of the selected repository HEAD. History may be unrelated, divergent, rewritten, or incomplete. Historical context remains available; no name-only fallback is used.')
    return {'verified':True,'method':'git_commit_ancestry','historical_commit':historical_head,'fresh_commit':fresh_head,
        'scope':'Verified shared Git ancestry, not authenticated project ownership. Clones and forks can share this history. No remote URL or local path is exported.'}
