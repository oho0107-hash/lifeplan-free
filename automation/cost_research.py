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


# === Structured official fee table extraction (evidence only, never auto-priced) ===
FEE_LABELS = (
    ('入学金', 'admission', 'once'), ('入園金', 'admission', 'once'),
    ('入塾金', 'enrollment', 'once'), ('入会金', 'enrollment', 'once'),
    ('施設拡充資金', 'facility', None), ('施設拡充費', 'facility', None),
    ('施設整備・運営費', 'facility', None), ('施設負担金', 'facility', 'once'),
    ('施設維持費', 'facility', None), ('施設費', 'facility', None),
    ('維持費', 'facility', None), ('授業料', 'tuition', None),
    ('受講料', 'tuition', None), ('学級費', 'materials', 'annual'),
    ('教材費', 'materials', None), ('実験実習料', 'lab', None),
    ('後援会費', 'activity', None), ('父母と先生の会会費', 'activity', None),
    ('生徒会費', 'activity', None), ('会費', 'management', None),
    ('積立金', 'trip', None), ('指定端末', 'device', 'once'),
)
_YEN = re.compile(r'(?<![\d,])(?:\d{1,3}(?:,\d{3})+|\d+)\s*円')
_TOTAL_LABEL = re.compile(r'^(?:合計|計|小計|総計|年額合計|月額合計|合\s*計)$')
_VOLUNTARY = re.compile(r'任意|寄付|任意加入|希望者|選択制')
_JUNIOR = re.compile(r'中学校|中学納入|中学\s*授業|中等部')
_SENIOR = re.compile(r'高等学校|高校納入|高校\s*授業|高等部')


def _label_fee(label: str):
    label=norm(re.sub(r'^\s*[（(]?\d+[)）\.、]?\s*', '', label)).strip('※*:： ')  # numbered lists
    for term, kind, period in FEE_LABELS:
        if term in label:
            return label, kind, period
    return label, None, None


def _scope_matches(section: str, stage: str) -> bool:
    if stage not in ('junior_high','high_school'):
        return True
    # Shared sites often contain both middle- and high-school tables.
    # A heading must select the requested school stage before accepting costs.
    j=bool(_JUNIOR.search(section)); h=bool(_SENIOR.search(section))
    # The nearest school-level heading wins; page titles sometimes mention both.
    mentions=list(re.finditer(r'中学校|中学納入|中学\s*授業|中等部|高等学校|高校納入|高校\s*授業|高等部',section))
    if mentions:
        last=mentions[-1].group()
        if stage=='junior_high' and bool(_SENIOR.search(last)):return False
        if stage=='high_school' and bool(_JUNIOR.search(last)):return False
    elif j and h:
        return False
    return True


def _billing_period(label: str, context: str, hint: str | None):
    if '月額' in label or '毎月' in label: return 'monthly'
    if '年額' in label or '年間' in label: return 'annual'
    if '入学手続' in context or '入学納入金' in context or '入学後' in context:
        if hint == 'once' or '施設拡充' in label:return 'once'
    if hint: return hint
    if '月額' in context or '毎月' in context: return 'monthly'
    if '年額' in context or '年間' in context: return 'annual'
    return None  # Never guess the charge period.


def _candidate(label: str, amount_text: str, section: str, stage: str, row_id: int, *, context: str = ''):
    fee_label, kind, period_hint=_label_fee(label)
    if not kind or _TOTAL_LABEL.match(fee_label):return None
    # One explicitly written yen amount, not "annual total" next to a monthly fee.
    numbers=list(_YEN.finditer(amount_text))
    if len(numbers)!=1:return None
    value=int(re.sub(r'\D','',numbers[0].group()))
    if not 1 <= value <= 20_000_000:return None
    context=norm(context or section)
    period=_billing_period(fee_label,context,period_hint)
    if period is None:return None
    if not _scope_matches(section,stage):return None
    label=norm(fee_label)
    # Combined quote is a structural table transcription, not a substring of
    # the flattened HTML. The source row/section is retained separately.
    quote=norm(label+' '+numbers[0].group())
    return {'cost_name':label,'amount_yen':value,'cost_type':kind,'period':period,
            'quote':quote,'source_row':row_id,'section':section,
            'required':not bool(_VOLUNTARY.search(label+' '+context)),
            'source_kind':'html_table',
            'is_subtotal':False}


class FeeTableParser(HTMLParser):
    """Read HTML table cells/line breaks and heading scope; no code execution."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip=0;self.head_depth=0;self.head='';self.section='';self.head_level=0;self.heading_stack={}
        self.tables=0;self.row=False;self.cell=False;self.current=[];self.cell_parts=[]
        self.table_rows=[];self.row_seq=0;self.context_parts=[]
        self.prose_rows=[];self.para_depth=0;self.para_parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','svg','noscript'):
            self.skip+=1;return
        if self.skip:return
        if tag in ('h1','h2','h3','h4','h5'):
            self.head_depth+=1;self.head='';self.head_level=int(tag[1])
        if tag in ('p','li') and not self.tables:
            self.para_depth+=1
            if self.para_depth==1:self.para_parts=[]
        if tag=='table':self.tables+=1
        if tag=='tr' and self.tables:
            self.row=True;self.current=[]
        if tag in ('td','th') and self.row:
            self.cell=True;self.cell_parts=[]
        if tag=='br' and self.cell:self.cell_parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','svg','noscript'):
            if self.skip:self.skip-=1
            return
        if self.skip:return
        if tag in ('h1','h2','h3','h4','h5') and self.head_depth:
            self.head_depth-=1
            if self.head.strip():
                level=self.head_level
                self.heading_stack={k:v for k,v in self.heading_stack.items() if k<level}
                self.heading_stack[level]=norm(self.head)
                self.section=' / '.join(self.heading_stack[k] for k in sorted(self.heading_stack))
                self.context_parts=[]
        if tag in ('p','li') and self.para_depth:
            self.para_depth-=1
            if self.para_depth==0 and not self.tables:
                note=norm(''.join(self.para_parts))
                if note:self.prose_rows.append((self.section,note))
        if tag in ('td','th') and self.cell:
            self.current.append('\n'.join(norm(s) for s in ''.join(self.cell_parts).splitlines() if norm(s)))
            self.cell=False
        if tag=='tr' and self.row:
            self.row_seq+=1
            self.table_rows.append((self.row_seq,self.section,self.current[:],
                                    norm(' '.join(self.context_parts[-25:]))[:500]))
            self.row=False
        if tag=='table' and self.tables:self.tables-=1
    def handle_data(self,data):
        if self.skip:return
        if self.head_depth:self.head+=data
        if self.cell:self.cell_parts.append(data)
        if self.para_depth and not self.tables:self.para_parts.append(data)
        if not self.tables and not self.head_depth and len(self.context_parts)<200:
            if norm(data):self.context_parts.append(norm(data))


def extract_table_fees(raw_html: str, stage: str) -> list[dict]:
    """Build exact table-row fee candidates, with no automatic cost adoption.

    A table can have parallel multiline labels and prices (e.g. Kaisei),
    or simple 2-column rows. Ambiguous, unscoped and summary rows are omitted.
    The main caller may show these as evidence; acceptance still needs review.
    """
    parser=FeeTableParser();parser.feed(raw_html)
    found=[];seen=set()
    for row_id, section, cells, note in parser.table_rows[:550]:
        if not _scope_matches(section,stage) or len(cells)<2:continue
        labels=[norm(s) for s in cells[0].splitlines() if norm(s)]
        amounts=[norm(s) for s in cells[1].splitlines() if norm(s)]
        if not labels or not amounts:continue
        # In a table where one cell lists 5 fee names and another lists 5 prices,
        # the only safe pairing is positional, with equal row lengths.
        pairs=list(zip(labels,amounts)) if len(labels)==len(amounts) else (
            [(cells[0],cells[1])] if len(labels)==len(amounts)==1 else [])
        context=section+' '+note+' '+' '.join(cells[2:])
        for label,amt in pairs:
            candidate=_candidate(label,amt,section,stage,row_id,context=context)
            if not candidate:continue
            key=(candidate['cost_name'],candidate['amount_yen'],candidate['period'],section)
            if key in seen:continue
            seen.add(key);found.append(candidate)
    # Prose can contain real mandatory fees that are not in the table: Kaisei's
    # first-year class fee and second-year facility contribution, for example.
    # Only extract adjacent, explicit label + yen pairs within the same sentence.
    labels='|'.join(sorted((re.escape(x[0]) for x in FEE_LABELS),key=len,reverse=True))
    inline_re=re.compile(r'('+labels+r')([^。；;\n]{0,85}?)('+_YEN.pattern+r')')
    for section, prose in parser.prose_rows:
        if not _scope_matches(section,stage):continue
        for match in inline_re.finditer(prose):
            name=match.group(1)
            # The fragment may contain other fees (e.g. an illustrative parenthetical)
            # or be an optional donation; do not adopt it automatically.
            quote=norm(match.group())
            if len(_YEN.findall(quote))!=1 or _VOLUNTARY.search(quote):continue
            fee=_candidate(name,match.group(3),section,stage,0,context=section+' '+prose)
            if not fee:continue
            fee['quote']=quote[:240]
            fee['source_kind']='html_prose'
            fee['grade_scope']=('first_year_only' if re.search(r'(第\s*1\s*学年|中1|初年度)',quote)
                               else 'from_second_year' if re.search(r'第\s*2\s*学年から',prose)
                               else 'unknown')
            key=(fee['cost_name'],fee['amount_yen'],fee['period'],section)
            if key in seen:continue
            seen.add(key);found.append(fee)
    return found


def fee_completeness(verified: list[dict], snapshots: list[dict], *, required_labels: dict[str,list[str]] | None = None) -> dict:
    """A fail-closed fee-data coverage audit, not a total cost estimate.

    Required fee names are supplied explicitly from verified school policy,
    not guessed from national averages or other schools. Without such a
    checklist the result cannot be marked complete.
    """
    required_labels=required_labels or {}
    result={}
    for snap in snapshots:
        sid=snap['id']
        required=required_labels.get(sid)
        rows=[r for r in verified if r.get('source_id')==sid]
        matched={norm(r['cost_name']) for r in rows}
        missing=[x for x in required or [] if norm(x) not in matched]
        table_evidence=snap.get('evidence_rows',[])
        unverified_table=[r['cost_name'] for r in table_evidence
                          if norm(r['cost_name']) not in matched]
        status=('complete_for_explicit_checklist' if required is not None and not missing
                else 'incomplete')
        result[sid]={'status':status,'verified_count':len(rows),
                     'required_checklist_provided':required is not None,
                     'missing_required':missing,'unverified_table_candidates':sorted(set(unverified_table)),
                     'unconfirmed_items_are_zero':False}
    return result


def annual_cost_preview(verified: list[dict], *, source_id: str, required_labels: list[str],
                        year_count: int = 3, months_per_year: int = 12) -> dict:
    """Only exact verified charges; refuse a full-budget total if anything is missing.

    `year_count` is not a forecast: grade-specific or unknown fees keep each
    affected year incomplete. One-time entrance charges occur in year 1 only.
    """
    if not 1 <= year_count <= 6 or not 1 <= months_per_year <= 12:
        raise ValueError('invalid duration or months')
    entries=[r for r in verified if r.get('source_id')==source_id and r.get('required') is True]
    byname={}
    for row in entries:
        byname.setdefault(norm(row['cost_name']),[]).append(row)
    missing=[n for n in required_labels if norm(n) not in byname]
    results=[]
    for grade in range(1,year_count+1):
        subtotal=0;excluded=[]
        for name in required_labels:
            possibilities=byname.get(norm(name),[])
            if not possibilities:continue
            if len(possibilities)>1:
                excluded.append(name+'（同名で異なる納付条件があり判定不能）');continue
            record=possibilities[0]
            scope=record.get('course_or_grade','')
            grade_scope=record.get('grade_scope','unknown')
            # Official-source grade_scope overrides any AI-proposed grade label.
            is_first_only=(grade_scope=='first_year_only' or
                bool(re.search(r'(?:中|高|小|第)?1\s*年|初年度|第\s*1\s*学年',scope)))
            if grade_scope=='from_second_year' and grade==1:
                continue
            if grade>1 and is_first_only and record.get('period')!='once':
                excluded.append(name+'（2年目以降は未確認）');continue
            period=record['period']
            if period=='once':factor=1 if grade==1 else 0
            elif period=='monthly':factor=months_per_year
            elif period=='annual':factor=1
            else:excluded.append(name+'（回数未確認）');continue
            subtotal+=record['amount_yen']*factor
        unresolved=missing+excluded
        results.append({'year_number':grade,'confirmed_subtotal_yen':subtotal,
                        'full_total_yen':None,
                        'unresolved':unresolved,'is_full_education_budget':False})
    return {'source_id':source_id,'years':results,'full_course_total_yen':None,
            'confirmed_subtotal_yen':sum(y['confirmed_subtotal_yen'] for y in results),
            'warning':'既知の必須費目の小計のみ。制服・通学・受験費・学年差・補助金などの全費用ではありません。'}


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
    evidence_rows=[]
    if is_pdf:
        # Dependency is a free open-source reader installed only in the AI generation job.
        from pypdf import PdfReader
        reader=PdfReader(BytesIO(raw))
        full='\n'.join((page.extract_text() or '') for page in list(reader.pages)[:55])
        full='\n'.join(norm(line) for line in full.splitlines() if norm(line))
    else:
        html=raw.decode(charset,'replace')
        full=strip_html(html)
        evidence_rows=extract_table_fees(html,source['stage'])
        if evidence_rows:
            # Keep cross-cell fee associations in the AI prompt. AI-generated
            # lines still require independent numeric verification below.
            compact=['[HTML料金表] '+x['section']+' | '+x['quote']+' | '+x['period']
                     for x in evidence_rows[:80]]
            full='\n'.join(compact)+'\n'+full
    site_year = source['year'] if source['year'] is not None and str(source['year']) in full else None
    return {'id':source['id'],'school':source['school'],'stage':source['stage'],
            'year':site_year,'url':source['url'],'fetched_at':datetime.now(timezone.utc).isoformat(),
            'status':'ok','text':focused_text(full),'full_text':full[:75_000],
            'evidence_rows':evidence_rows}


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
        fee_name=norm(str(r.get('cost_name','')))
        amount=r.get('amount_yen')
        try:amount=int(amount)
        except (TypeError,ValueError):amount=-1
        period=r.get('period')
        cost_type=r.get('cost_type')
        if cost_type not in FEE_TYPES: cost_type='other'
        # Quote must appear, and amount literal must be present in that quote.
        # Prevent currency unit confusion by restricting to yen.
        quoted_numbers = [int(x.replace(',', '')) for x in re.findall(r'\d[\d,]*', quote)]
        # The same quote must include the named fee; an unrelated amount on
        # another row is NOT evidence, even if the source page contains it.
        table_rows=s.get('evidence_rows',[]) if s else []
        comparable=lambda val: re.sub(r'(?<=\d)\s+(?=円)', '', norm(val))
        normalized_quote=comparable(quote)
        matched_row=next((row for row in table_rows if
                      comparable(row['quote'])==normalized_quote and
                      row['amount_yen']==amount and row['period']==period and
                      norm(row['cost_name'])==fee_name), None)
        exact_row=matched_row is not None
        inline_match=(not table_rows and s is not None and
                      normalized_quote in comparable(s['full_text']) and fee_name in quote)
        # HTML may also have inline notes outside tables. Such rows remain
        # accepted only when their exact quote is independently present.
        inline_note=(s is not None and normalized_quote in comparable(s['full_text'])
                     and fee_name in quote and not ('[HTML料金表]' in s['full_text']
                     and normalized_quote in comparable(s['full_text'].split('\n',1)[0])
                     and not exact_row))
        if (not s or not 5<=len(quote)<=240 or not 1<=amount<=20_000_000 or
            not fee_name or period not in ('once','monthly','annual','per_event') or
            not (exact_row or inline_match or inline_note) or amount not in quoted_numbers or
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
                         'evidence_kind':matched_row.get('source_kind','html_table') if matched_row else 'source_text',
                         'evidence_section':matched_row.get('section','') if matched_row else '',
                         'required':(matched_row['required'] if matched_row is not None
                                     else r.get('required') is True),
                         'grade_scope':matched_row.get('grade_scope','unknown') if matched_row else 'unknown',
                         'notes':str(r.get('notes',''))[:250]})
    return verified,rejected


def registry():return json.loads(SOURCE_REGISTRY.read_text(encoding='utf-8'))


if __name__=='__main__':
    import sys
    rq=' '.join(sys.argv[1:]) or '私立中学校 学費'
    data=collect(rq,registry())
    print(json.dumps([{k:v for k,v in s.items() if k!='full_text'} for s in data],ensure_ascii=False,indent=2))
