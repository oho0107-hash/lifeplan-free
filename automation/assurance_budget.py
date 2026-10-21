"""Evidence-linked education reserve estimate; NOT a guarantee of future solvency.

Costs are stored for one selected provider/course/stage, never averaged across
unrelated schools. Unknown charges require a bounded and sourced user-approved
allowance, or the estimate remains incomplete. No API or personal data required.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal, ROUND_CEILING
from urllib.parse import urlsplit


class BudgetError(ValueError):
    pass


def _money(value, name):
    if isinstance(value, bool):
        raise BudgetError(f'{name}: boolean is not a yen amount')
    try:
        n=Decimal(str(value))
    except Exception as exc:
        raise BudgetError(f'{name}: invalid yen amount') from exc
    if not n.is_finite() or n<0 or n>100_000_000:
        raise BudgetError(f'{name}: outside allowed range')
    return n


def _rate(value, name):
    try:
        n=Decimal(str(value))
    except Exception as exc:
        raise BudgetError(f'{name}: invalid percentage') from exc
    if not n.is_finite() or not 0<=n<=30:
        raise BudgetError(f'{name}: percentage must be between 0 and 30')
    return n / Decimal(100)


def _ceil(number):
    return int(number.quantize(Decimal('1'), rounding=ROUND_CEILING))


def calculate(plan:dict, price_rows:list[dict]):
    """Create scenario totals with independently declared growth and reserve assumptions.

    plan: {provider_id,stage,entry_year,years,base_year,annual_growth_pct,
           stress_growth_pct,contingency_pct, coverage_required:[str],
           supplemental:[{category,amount_yen,period,source,grade_numbers:[int]}],
           optional_categories:[str]}
    prices: [{provider_id,stage,cost_id,cost_type,amount_yen,period,
              grade_numbers,year,source_url,quote,evidence_status:'verified',
              required:true, included_in:null}]
    """
    sid=plan.get('provider_id'); stage=plan.get('stage'); year=plan.get('entry_year')
    years=plan.get('years')
    if not isinstance(sid,str) or not sid or not isinstance(stage,str) or not stage:
        raise BudgetError('provider_id and stage are required')
    if type(year) is not int or not 2020<=year<=2120:
        raise BudgetError('entry_year must be a valid year')
    if type(years) is not int or not 1<=years<=8:
        raise BudgetError('years must be 1..8')
    growth=_rate(plan.get('annual_growth_pct'), 'annual_growth_pct')
    stress=_rate(plan.get('stress_growth_pct'), 'stress_growth_pct')
    contingency=_rate(plan.get('contingency_pct'), 'contingency_pct')
    if stress<growth:
        raise BudgetError('stress_growth_pct must not be below annual_growth_pct')
    supplement=plan.get('supplemental',[])
    if not isinstance(supplement,list):
        raise BudgetError('supplemental must be a list')
    seen=set(); bill=[]; confirmed_categories=set(); uncovered=[]
    for row in price_rows:
        if row.get('provider_id')!=sid or row.get('stage')!=stage:
            continue
        if row.get('evidence_status')!='verified':
            uncovered.append(str(row.get('cost_type','unknown'))+'：根拠未確認')
            continue
        cost_id=str(row.get('cost_id',''))
        if not cost_id or cost_id in seen:raise BudgetError('Duplicate or missing cost_id')
        seen.add(cost_id)
        observed=row.get('year')
        if type(observed) is not int or observed<2000 or observed>year:
            raise BudgetError('Verified cost must have its own source year')
        url=str(row.get('source_url',''))
        if urlsplit(url).scheme!='https' or not urlsplit(url).hostname or not row.get('quote'):
            raise BudgetError('Verified cost requires official URL and quoted evidence')
        if row.get('included_in'):
            # Summary totals and sub-items are not both added.
            continue
        p=row.get('period')
        if p not in ('once','monthly','annual','per_event'):
            raise BudgetError('Unknown payment period')
        grades=row.get('grade_numbers')
        if not isinstance(grades,list) or not grades or any(type(g) is not int or g<1 or g>years for g in grades):
            raise BudgetError('Explicit applicable grades are required')
        if p=='once' and len(grades)!=1:
            raise BudgetError('One-time fee must apply to exactly one grade')
        if p=='per_event':
            repeats=row.get('events_per_year')
            if type(repeats) is not int or not 1<=repeats<=20:
                raise BudgetError('Event count must be explicit')
            factor=repeats
        elif p=='monthly':
            months=row.get('months_per_year')
            if type(months) is not int or not 1<=months<=12:
                raise BudgetError('Month count must be explicit')
            factor=months
        else:factor=1
        bill.append((str(row.get('cost_type')),str(row.get('cost_name',cost_id)),
                     _money(row.get('amount_yen'),cost_id)*factor,observed,grades,'verified',url))
        if row.get('required') is True:
            confirmed_categories.add(str(row.get('cost_type')))

    for line in supplement:
        cat=str(line.get('category',''))
        if not cat or not line.get('evidence_description'):
            raise BudgetError('A conservative allowance needs category and evidence_description')
        url=line.get('source_url')
        if url and (urlsplit(str(url)).scheme!='https' or not urlsplit(str(url)).hostname):
            raise BudgetError('Supplement URL must be HTTPS')
        grades=line.get('grade_numbers')
        if not isinstance(grades,list) or not grades or any(type(g) is not int or g<1 or g>years for g in grades):
            raise BudgetError('Allowance must specify applicable grade numbers')
        amount=_money(line.get('amount_yen'),cat)
        if amount==0 and line.get('status')!='not_applicable':
            raise BudgetError('Unknown expenses cannot be entered as zero')
        p=line.get('period','annual')
        if p not in ('annual','once'):
            raise BudgetError('Allowance must already be annualized or one-time')
        bill.append((cat,cat,amount,year,grades,'allowance',str(url or 'evidence description only')))
        confirmed_categories.add(cat)

    required=set(plan.get('coverage_required',[]))
    if not required or not all(isinstance(x,str) and x for x in required):
        raise BudgetError('Explicit coverage_required is mandatory')
    missing=sorted(required-confirmed_categories)
    row_totals=[]
    for g in range(1,years+1):
        thisyear=year+g-1
        baseline=stress_value=original=0
        lines=[]
        for cat,name,amount,observed,grades,kind,url in bill:
            if g not in grades:continue
            y=thisyear-observed
            normal=_ceil(amount*(1+growth)**y)
            stress_yen=_ceil(amount*(1+stress)**y)
            original+=int(amount);baseline+=normal;stress_value+=stress_yen
            lines.append({'category':cat,'fee':name,'evidence_kind':kind,
                          'observed_amount_yen':int(amount), 'current_scenario_yen':normal,
                          'stress_scenario_yen':stress_yen,'evidence':url})
        # Buffer is explicitly visible, not presented as a discovered fee.
        reserve=_ceil(Decimal(stress_value)*(1+contingency))
        row_totals.append({'school_year':g,'calendar_year':thisyear,
                           'known_price_subtotal_yen':original,
                           'baseline_yen':baseline,'stress_yen':stress_value,
                           'reserve_yen':reserve,'assumption_buffer_yen':reserve-stress_value,
                           'lines':lines})
    return {'provider_id':sid,'stage':stage,'start_year':year,
            'assumptions':{'annual_growth_pct':str(growth*100),
                           'stress_growth_pct':str(stress*100),
                           'contingency_pct':str(contingency*100)},
            'years':row_totals,
            'baseline_total_yen':sum(r['baseline_yen'] for r in row_totals),
            'stress_total_yen':sum(r['stress_yen'] for r in row_totals),
            'reserve_total_yen':sum(r['reserve_yen'] for r in row_totals),
            'missing_categories':missing,
            'unverified_items':uncovered,
            'readiness':('scenario_covered_not_guaranteed' if not missing and not uncovered else 'incomplete'),
            'safe_to_claim_guarantee':False,
            'warning':('将来の進路・学費・物価・追加費用を100％保証する数字ではありません。'
                       '未確認の費目がある場合は十分額として使用できません。')}
