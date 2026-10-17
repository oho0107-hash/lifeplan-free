"""Fail-closed patch application and release risk detection. No external dependencies."""
from pathlib import Path
import re
import ast

ENGINE_END = "})(typeof window!=='undefined'?window:globalThis);"
START = '/* LIFE Financial Studio'
ALLOWED = {'index.html', 'engine.js'}

class UnsafePatch(ValueError):
    pass

def replace_once(source, before, after):
    if not before or not isinstance(after, str) or len(before) > 13000 or len(after) > 16000:
        raise UnsafePatch('Empty, invalid or oversized patch')
    if source.count(before) != 1:
        raise UnsafePatch('Target text not found uniquely (repo changed or guessed patch)')
    return source.replace(before, after, 1)

def engine_range(html):
    start = html.find(START)
    if start < 0:
        raise UnsafePatch('Engine marker not found in index.html')
    end = html.find(ENGINE_END, start)
    if end < 0:
        raise UnsafePatch('Engine ending marker not found')
    return start, end + len(ENGINE_END)

def sync_engine(html, engine):
    a, b = engine_range(html)
    return html[:a] + engine.strip() + html[b:]

def apply_patches(original, edits):
    """Original/updated are dict filename:text; refuse edits that touch generated embedded engine."""
    if not isinstance(edits, list) or not 1 <= len(edits) <= 12:
        raise UnsafePatch('Expected 1..12 edits')
    result = original.copy()
    html_base = original['index.html']
    a, b = engine_range(html_base)
    if html_base[a:b] != original['engine.js'].strip():
        raise UnsafePatch('Embedded engine and engine.js differ. Sync source manually first')
    for patch in edits:
        if not isinstance(patch, dict) or set(patch) != {'file','old','new'}:
            raise UnsafePatch('Patch must contain file, old and new')
        path, old, new = patch['file'], patch['old'], patch['new']
        if path not in ALLOWED or not isinstance(old, str) or not isinstance(new, str):
            raise UnsafePatch('File or patch content not permitted')
        if old == new: continue
        if path == 'index.html':
            # forbid editing duplicated engine directly; engine.js is source of truth
            start, end = engine_range(result['index.html'])
            if result['index.html'][:start].count(old) + result['index.html'][end:].count(old) != 1:
                raise UnsafePatch('index.html patches must be outside embedded engine')
        result[path] = replace_once(result[path], old, new)
    result['index.html'] = sync_engine(result['index.html'], result['engine.js'])
    if len(result['index.html']) > 200000 or len(result['engine.js']) > 100000:
        raise UnsafePatch('Generated app exceeds safety size limit')
    if result == original:
        raise UnsafePatch('No effective changes')
    return result

RESEARCH_ALLOWED = {'automation/cost_research.py', 'automation/test_cost_research.py'}
RESEARCH_SAFE_IMPORTS = frozenset({
    '__future__', 'datetime', 'io', 'html', 'json', 're', 'ssl',
    'unicodedata', 'urllib', 'pathlib', 'pypdf', 'unittest',
    'cost_research', 'typing', 'collections', 'decimal', 'textwrap',
    'math', 'itertools', 'functools',
})
RESEARCH_FORBIDDEN_ADDITIONS = (
    'GEMINI_API_KEY', 'GITHUB_TOKEN', 'os.environ', 'subprocess',
    'socket.', 'eval(', 'exec(', '__import__(', 'compile(',
    'import os', 'import sys', 'import requests', 'import importlib',
)


def _roots_imported(tree):
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split('.')[0])
    return roots


def apply_research_patches(original, edits):
    """Allow only evidence parser AND its regression tests to change together.

    The edited Python is NEVER executed in the AI generation or PR publication
    jobs. It runs only in an isolated verification job without GitHub write
    credentials or the AI key, followed by mandatory human review.
    """
    if not isinstance(edits, list) or not 2 <= len(edits) <= 12:
        raise UnsafePatch('Research code change requires 2..12 exact patches, including a regression test')
    result = original.copy()
    files_changed = set()
    for patch in edits:
        if not isinstance(patch, dict) or set(patch) != {'file', 'old', 'new'}:
            raise UnsafePatch('Patch must contain only file, old and new')
        path, old, new = patch['file'], patch['old'], patch['new']
        if path not in RESEARCH_ALLOWED or not isinstance(old, str) or not isinstance(new, str):
            raise UnsafePatch('Research agent may edit only cost_research.py and its test file')
        if old == new:
            continue
        if any(blocked in new and blocked not in old for blocked in RESEARCH_FORBIDDEN_ADDITIONS):
            raise UnsafePatch('Research patch contains a credential/network/unsafe-code marker')
        result[path] = replace_once(result[path], old, new)
        files_changed.add(path)
    if files_changed != RESEARCH_ALLOWED:
        raise UnsafePatch('Research code and regression tests must both be changed')
    for path in RESEARCH_ALLOWED:
        if len(result[path]) > (70000 if path.endswith('/cost_research.py') else 30000):
            raise UnsafePatch('Research patch exceeds file size limit')
        try:
            orig_ast = ast.parse(original[path], filename=path)
            updated_ast = ast.parse(result[path], filename=path)
        except SyntaxError as e:
            raise UnsafePatch('Research patch is not valid Python syntax: '+str(e)) from e
        added_imports = _roots_imported(updated_ast) - _roots_imported(orig_ast)
        if not added_imports <= RESEARCH_SAFE_IMPORTS:
            raise UnsafePatch('Non-allowlisted new Python import: '+str(sorted(added_imports - RESEARCH_SAFE_IMPORTS)))
    return result


def only_css_changed(old_html, new_html):
    """Auto-publish if and only if the only difference is within a single existing style block."""
    pattern = re.compile(r'<style>(.*?)</style>', re.S)
    mo, mn = pattern.search(old_html), pattern.search(new_html)
    if not mo or not mn or len(pattern.findall(old_html)) != 1 or len(pattern.findall(new_html)) != 1:
        return False
    # Deny CSS features that could fetch a remote resource from a user's browser.
    if re.search(r'url\s*\(|@import\b|expression\s*\(|behavior\s*:', mn.group(1), re.I):
        return False
    return (old_html[:mo.start(1)] == new_html[:mn.start(1)] and
            old_html[mo.end(1):] == new_html[mn.end(1):] and
            mo.group(1) != mn.group(1))

def is_auto_publish_safe(original, updated):
    return (original['engine.js'] == updated['engine.js'] and
            only_css_changed(original['index.html'], updated['index.html']))

if __name__ == '__main__':
    import json, sys
    base = Path(sys.argv[1]); output = Path(sys.argv[2]); diff = Path(sys.argv[3])
    sources = {s:(base/s).read_text(encoding='utf-8') for s in ALLOWED}
    edits = json.loads(diff.read_text(encoding='utf-8'))['changes']
    new = apply_patches(sources, edits)
    output.mkdir(parents=True, exist_ok=True)
    for name, content in new.items(): (output/name).write_text(content,encoding='utf-8')
    print('COSMETIC_ONLY' if is_auto_publish_safe(sources,new) else 'APPROVAL_REQUIRED')
