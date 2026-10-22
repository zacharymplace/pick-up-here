"""Bounded Markdown evidence and lexical file links; never execute project content."""
import re

STOP = {'the', 'and', 'for', 'with', 'add', 'more', 'tests', 'test', 'utilities',
        'scripts', 'script', 'src', 'py', 'md', 'js', 'ts', 'tsx', 'json', 'toml',
        'future', 'publishing', 'init', '__init__'}

def tokens(text):
    return {s for s in re.findall(r'[a-z][a-z0-9]+', text.lower()) if s not in STOP}

def markdown_parts(text):
    """ATX headings and unchecked list items outside backtick/tilde fences."""
    sections, tasks = [], []
    current = None
    fence = None
    heading = '(preamble)'
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if marker:
            value = marker.group(1)
            if fence is None:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence) and not line[marker.end():].strip():
                fence = None
            if current is not None:
                current['lines'].append(line)
            continue
        title = re.match(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$', line) if fence is None else None
        if title:
            if current is not None:
                current['end_line'] = number - 1
                sections.append(current)
            heading = title.group(1)
            current = {'heading': heading, 'start_line': number, 'lines': [line]}
        elif current is not None:
            current['lines'].append(line)
        if fence is None and re.match(r'^\s*[-*+]\s+\[ \]\s+\S', line):
            tasks.append({'line': number, 'heading': heading, 'quote': line})
    if current is not None:
        current['end_line'] = len(text.splitlines())
        sections.append(current)
    return sections[:64], tasks[:32]

def linked_candidates(tasks, files):
    """Word overlap is only a lead, never evidence that a task is unfinished."""
    candidates = []
    for task in tasks:
        # Ignore metadata tails in backticks only for token matching, not exact citations.
        words = tokens(task['quote'])
        ranked = []
        for file in files:
            if file['path'].endswith('/__init__.py') or file['path'] == '__init__.py':
                continue
            overlap = sorted(words & tokens(file['path']))
            explicit = bool(re.search(r'(?<![\w./-])'+re.escape(file['path'])+r'(?![\w./-])', task['quote']))
            if explicit or overlap:
                ranked.append((not explicit, -len(overlap), file['path'], file, overlap))
        for not_explicit, score, path, file, overlap in sorted(ranked)[:3]:
            file_words = tokens(file['path'])
            related = [other['id'] for other in files if other['path'].startswith(('tests/', 'test/')) and other['id'] != file['id'] and len(file_words & tokens(other['path'])) >= 2][:3]
            candidates.append({'kind': 'inspect_task_file', 'evidence': task['evidence'], 'target': file['id'],
                'basis': 'exact_path_mention' if not not_explicit else 'lexical_overlap',
                'matched_tokens': overlap, 'related_tests': related,
                'limitation': 'A suggested association only; no code or tests were inspected and the recorded task may be stale.'})
    return candidates[:8]
