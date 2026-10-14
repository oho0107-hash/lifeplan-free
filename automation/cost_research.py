"""Official-price evidence collector (free stdlib, no web-search API).

Fetch only curated school/provider pages; never fetch user-supplied or model-supplied URLs.
Untrusted HTML is treated as data and never executed or interpreted as instructions.
"""
from __future__ import annotations
from datetime import datetime, timezone
from io import BytesIO
from html.parser import HTMLParser
import json
import re
import ssl
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

SOURCE_REGISTRY = Path(__file__).resolve().parent.parent / 'costs' / 'official_sources.json'
FOCUS = ('授業料','入学金','入園金','納付金','費用','学費','教材','設備費','施設','会費','積立','受講料','入塾金','入会金','給食','夏期講習','冬期講習','春期講習','入試','予備校','保育料','2026')
COST_WORDS = ('教育費','学費','入学金','入園料','入園金','私立','受験','小学校','中学校','高校','大学','塾','進学','授業料','学校費','費用調査','幼稚園','保育園','こども園','予備校','家庭教師','習い事','実費','教材','修学旅行','通学','一人暮らし')
MAX_PAGE_BYTES = 450_000


def norm(s: str) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s)).strip()


class StripHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.data=[]
        self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','svg','noscript'):
            self.skip+=1
        if tag in ('tr','p','li','td','th','br','h2','h3','h4','div','section'):
            self.data.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style','svg','noscript') and self.skip:
            self.skip-=1
        if tag in ('tr','p','li','td','th','h2','h3','h4','div','section'):
            self.data.append('\n')
    def handle_data(self, data):
        if not self.skip:
            self.data.append(data)


def strip_html(raw: str) -> str:
    parser=StripHTML()
    parser.feed(raw)
    lines=[norm(s) for s in ''.join(parser.data).splitlines()]
    return '\n'.join(x for x in lines if x)


def focused_text(raw_text: str, limit=11500) -> str:
    lines=raw_text.splitlines()
    idx=set()
    for i,line in enumerate(lines):
        if any(key in line for key in FOCUS):
            idx.update(range(max(0,i-2),min(len(lines),i+3)))
    excerpts='\n'.join(lines[i] for i in sorted(idx))
    return excerpts[:limit]


def selected_sources(request: str, registry: dict) -> list[dict]:
    """Prefer explicitly named schools; examples are *never* an assumed school choice.

    If the user requests a category without naming an institution, fetch at most
    two representative official URLs per stage. The report marks them examples.
    """
    if not any(word in request for word in COST_WORDS):
        return []
    entries=registry.get('sources',[])
    named=[s for s in entries if any(a.lower() in request.lower() for a in
                                ([s['school']]+s.get('aliases',[]))) ]
    if named:
        # If school has multiple stages, retain its individually labelled sources.
        return named[:12]
    stage_keywords={
        'nursery': ('保育園','保育所','こども園','0歳','1歳','2歳'),
        'kindergarten': ('幼稚園','入園','年少','年中','年長'),
        'elementary': ('小学校','小学校受験','小学','小学生'),
        'junior_high': ('中学','中学校','中高一貫'),
        'high_school': ('高校','高等学校','高校受験'),
        'university': ('大学','学部','理系','文系'),
        'cram_elementary': ('中学受験塾','小学生塾'),
        'cram_junior_high': ('高校受験塾','中学生塾'),
        'cram_high_school': ('大学受験塾','高校生塾'),
        'prep_school': ('予備校','浪人','高卒生'),
        'private_tutor': ('家庭教師','個別指導'),
        'lessons': ('習い事','公文','英会話','ピアノ','水泳'),
    }
    requested={stage for stage,words in stage_keywords.items() if any(w in request for w in words)}
    if not requested and ('教育費' in request or '全部' in request or '全体' in request):
        # A sample across existing registry. Does not imply full provider coverage.
        requested=set(stage_keywords)
    chosen=[]; counts={}
    for s in entries:
        stage=s.get('stage')
        if stage in requested and counts.get(stage,0)<2:
            chosen.append(s)
            counts[stage]=counts.get(stage,0)+1
        if len(chosen)>=10:break
    return chosen


def fetch_source(source: dict, *, opener=urllib.request.urlopen) -> dict:
    parsed=urllib.parse.urlparse(source['url'])
    if parsed.scheme!='https' or parsed.hostname!=source['host']:
        raise ValueError('Official-source URL is not on the approved host')
    if parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Unsafe source URL')
    req=urllib.request.Request(source['url'],headers={'User-Agent':'Lifeplan-Cost-Research/1.0 (public school price evidence; no data submitted)', 'Accept':'text/html,application/pdf'})
    with opener(req,timeout=18) as resp:
        final=urllib.parse.urlparse(resp.geturl())
        if final.scheme!='https' or final.hostname!=source['host']:
            raise ValueError('Unexpected redirect outside verified school domain')
        ctype=resp.headers.get('content-type','')
        is_pdf=source['url'].lower().endswith('.pdf')
        if not ('text/html' in ctype or (is_pdf and 'application/pdf' in ctype)):
            raise ValueError('Unexpected response type: '+ctype[:70])
        cap=3_000_000 if is_pdf else MAX_PAGE_BYTES
        raw=resp.read(cap+1)
        if len(raw)>cap:raise ValueError('School page too large for free research')
        charset=resp.headers.get_content_charset() or 'utf-8'
    if is_pdf:
        # Dependency is a free open-source reader installed only in the AI generation job.
        from pypdf import PdfReader
        reader=PdfReader(BytesIO(raw))
        full='\n'.join((page.extract_text() or '') for page in list(reader.pages)[:55])
        full='\n'.join(norm(line) for line in full.splitlines() if norm(line))
    else:
        full=strip_html(raw.decode(charset,'replace'))
    site_year = source['year'] if source['year'] is not None and str(source['year']) in full else None
    return {'id':source['id'],'school':source['school'],'stage':source['stage'],
            'year':site_year,'url':source['url'],'fetched_at':datetime.now(timezone.utc).isoformat(),
            'status':'ok','text':focused_text(full),'full_text':full[:75_000]}


def collect(request: str, registry: dict, *, fetch=fetch_source) -> list[dict]:
    results=[]
    for source in selected_sources(request,registry):
        try:
            results.append(fetch(source))
        except Exception as exc:
            results.append({'id':source['id'],'school':source['school'],'stage':source['stage'],
                            'year':source['year'],'url':source['url'],'status':'unavailable',
                            'reason':type(exc).__name__+': '+str(exc)[:150]})
    return results


FEE_TYPES = frozenset((
    'admission','tuition','facility','meals','uniform','materials','device','trip',
    'transport','activity','exams','lab','enrollment','testing','seasonal_course',
    'special_course','equipment','extended_care','events','supplies','travel',
    'application','deposit','rent','management','moving','utilities','food',
    'communication','insurance','other'
))


def verify_ai_records(records: list[dict], snapshots: list[dict]) -> tuple[list[dict],list[dict]]:
    """Never accept a fee unsupported by an exact substring of its source page."""
    by_id={s['id']:s for s in snapshots if s.get('status')=='ok'}
    verified=[]; rejected=[]
    for r in records[:65]:
        if not isinstance(r,dict):continue
        sid=r.get('source_id')
        s=by_id.get(sid)
        quote=norm(str(r.get('quote','')))
        amount=r.get('amount_yen')
        try:amount=int(amount)
        except (TypeError,ValueError):amount=-1
        period=r.get('period')
        cost_type=r.get('cost_type')
        if cost_type not in FEE_TYPES: cost_type='other'
        # Quote must appear, and amount literal must be present in that quote.
        # Prevent currency unit confusion by restricting to yen.
        quoted_numbers = [int(x.replace(',', '')) for x in re.findall(r'\d[\d,]*', quote)]
        if (not s or not 5<=len(quote)<=240 or not 1<=amount<=20_000_000 or
            period not in ('once','monthly','annual','per_event') or
            quote not in norm(s['full_text']) or amount not in quoted_numbers or
            ('円' not in quote and not re.search(r'単位\s*[:：]?\s*円',s['full_text']))):
            rejected.append({'source_id':sid,'name':r.get('cost_name',''), 'reason':'no independently matched official quote/amount'})
            continue
        verified.append({'school':s['school'],'stage':s['stage'],'year':s['year'],
                         'source_id':sid,'source_url':s['url'],'fetched_at':s['fetched_at'],
                         'cost_name':str(r.get('cost_name',''))[:100], 'amount_yen':amount,
                         'cost_type':cost_type,
                         'course_or_grade':str(r.get('course_or_grade','未確認'))[:120],
                         'bill_includes':str(r.get('bill_includes','未確認'))[:150],
                         'period':period, 'quote':quote,
                         'required':r.get('required') is True,
                         'notes':str(r.get('notes',''))[:250]})
    return verified,rejected


def registry():return json.loads(SOURCE_REGISTRY.read_text(encoding='utf-8'))


if __name__=='__main__':
    import sys
    rq=' '.join(sys.argv[1:]) or '私立中学校 学費'
    data=collect(rq,registry())
    print(json.dumps([{k:v for k,v in s.items() if k!='full_text'} for s in data],ensure_ascii=False,indent=2))
