"""Free scheduled reachability and evidence re-fetch for the curated source list.
Does not update tuition figures, app baseline, or paid APIs.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from cost_research import fetch_source, registry, norm


def main():
    sources = registry()['sources']
    rows=[]
    for source in sources:
        try:
            snap=fetch_source(source)
            digest=sha256(norm(snap['text']).encode('utf-8')).hexdigest()
            rows.append({'id':source['id'],'stage':source['stage'],'url':source['url'],
                         'status':'fetched','fee_excerpt_sha256':digest,
                         'official_year_visible':snap.get('year')})
        except Exception as exc:
            rows.append({'id':source['id'],'stage':source['stage'],'url':source['url'],
                         'status':'needs_review','reason':type(exc).__name__+': '+str(exc)[:150]})
    data={'generated_at_utc':datetime.now(timezone.utc).isoformat(),
          'what_this_is':'weekly page availability and excerpt fingerprint, NOT fee verification or price auto-update',
          'rows':rows}
    out=Path('reports/official_cost_source_check.json')
    out.parent.mkdir(exist_ok=True,parents=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    bad=sum(x['status']!='fetched' for x in rows)
    print(f'Checked {len(rows)} registered sources; needs review {bad}. Reports artifact contains details.')
    # Deliberately return zero: a blocked page is not a signal to overwrite.


if __name__ == '__main__':main()
