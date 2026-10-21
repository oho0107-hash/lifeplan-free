"""Detect meaningful changes in registered school-price page excerpts.

Runs without paid APIs or secrets; raw page text is NOT interpreted as an instruction.
Produces JSON only; the GitHub workflow may open an alert Issue for review.
"""
from __future__ import annotations
import json
from pathlib import Path


def compare(old:dict|None, new:dict)->dict:
    prior={x['id']:x for x in old.get('rows',[])} if old else {}
    changes=[]
    for item in new.get('rows',[]):
        last=prior.get(item['id'])
        if not last:continue  # initial baseline is not proof of a price change
        if item.get('status')!='fetched':
            if item.get('status')!=last.get('status'):
                changes.append({'id':item['id'],'url':item['url'],'type':'page_unavailable',
                                'message':'公式ページが取得できなくなりました'})
            continue
        if last.get('status')=='fetched' and item.get('fee_excerpt_sha256')!=last.get('fee_excerpt_sha256'):
            changes.append({'id':item['id'],'url':item['url'],'type':'excerpt_changed',
                            'message':'料金に関するページ抜粋が変化しました（値上げとは限りません）'})
        elif last.get('status')!='fetched':
            changes.append({'id':item['id'],'url':item['url'],'type':'page_restored',
                            'message':'ページが再び取得できるようになりました'})
    return {'has_previous_baseline':old is not None,'source_change_count':len(changes),
            'changes':changes,'readiness':'requires_official_fee_revalidation' if changes else 'no_change_detected',
            'note':'更新候補の検出であり、価格の上昇や学費の確定ではありません。'}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--old');p.add_argument('--new',required=True);p.add_argument('--out',required=True)
    args=p.parse_args()
    older=json.loads(Path(args.old).read_text()) if args.old and Path(args.old).exists() else None
    current=json.loads(Path(args.new).read_text())
    result=compare(older,current)
    Path(args.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(f"Official price page changes: {result['source_change_count']}, has baseline: {result['has_previous_baseline']}")
