"""Strict auto-merge classification. Only documentary research OR isolated CSS.

Financial source data, Python/JS, workflows and calculators require approval.
Classification must be independent of the AI's own verdict.
"""
from __future__ import annotations
from pathlib import PurePosixPath
import re

DOC_REVIEW=re.compile(r'^reviews/issue-[0-9]+-run-[0-9]+\.md$')
DOC_COST=re.compile(r'^costs/(?:issue|coverage-issue)-[0-9]+-run-[0-9]+\.json$')


def classify(files:list[str], *, old_html:str|None=None, new_html:str|None=None)->str:
    if not files or any(not isinstance(f,str) or '..' in PurePosixPath(f).parts for f in files):
        return 'human_required'
    # Evidence reports do not change the app's financial model or deployed files.
    if all(DOC_REVIEW.fullmatch(f) or DOC_COST.fullmatch(f) for f in files):
        return 'evidence_only'
    if 'index.html' in files and all(f=='index.html' or DOC_REVIEW.fullmatch(f) or DOC_COST.fullmatch(f) for f in files) and old_html is not None and new_html is not None:
        from guard import only_css_changed
        if only_css_changed(old_html,new_html):
            return 'cosmetic_only'
    return 'human_required'


if __name__=='__main__':
    import argparse,subprocess
    p=argparse.ArgumentParser()
    p.add_argument('--base',default='HEAD^');p.add_argument('--head',default='HEAD')
    ns=p.parse_args()
    def git(*args):return subprocess.check_output(['git',*args],text=True)
    files=git('diff','--name-only',ns.base,ns.head).strip().splitlines()
    old=new=None
    if 'index.html' in files:
        old=git('show',ns.base+':index.html');new=git('show',ns.head+':index.html')
    print(classify(files,old_html=old,new_html=new))
