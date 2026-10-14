"""Deterministic bill preview from VERIFIED fees and an explicit user approved selection.

This module will never pick the most expensive school or infer optional spending.
It returns a documented subtotal, NOT a complete future education total.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


class NeedsApproval(ValueError):
    pass


def quote_key(fee: dict) -> str:
    from hashlib import sha256
    fields = ['source_id','cost_name','cost_type','amount_yen','period','quote']
    payload = '\u001e'.join(str(fee.get(k,'')) for k in fields)
    return sha256(payload.encode()).hexdigest()[:16]


def preview(verified: list[dict], selection: dict) -> dict:
    """Selection example: {approved_by_user: true, school: ..., stage: ...,
    source_id: ..., observed_fee_year:2026, forecast_year:2035,
    approved_inflation_rate_pct:0, fee_charges:[{quote_key, months:12,
    occurrences:1, years:1}], excluded_fee_keys:[], double_count_reviewed:true}
    """
    if selection.get('approved_by_user') is not True:
        raise NeedsApproval('School/course and quoted costs must be selected by the user')
    if selection.get('double_count_reviewed') is not True:
        raise NeedsApproval('User must review bundled/included fees to prevent double count')
    source_id=selection.get('source_id')
    if not source_id or not isinstance(source_id,str):
        raise ValueError('source_id is required')
    year=selection.get('forecast_year')
    if not isinstance(year,int) or not 2020<=year<=2120:
        raise ValueError('Valid forecast_year is required')
    rate=selection.get('approved_inflation_rate_pct')
    if rate is None:
        raise NeedsApproval('A future price assumption must be explicitly approved, including zero')
    try: rate=Decimal(str(rate))
    except Exception as ex: raise ValueError('Invalid inflation rate') from ex
    if not -10 <= rate <= 20:raise ValueError('Unreasonable inflation assumption: re-approve manually')
    if rate != 0 and selection.get('inflation_assumption_approved') is not True:
        raise NeedsApproval('Non-zero inflation projection needs explicit approval')
    observed=selection.get('observed_fee_year')
    if not isinstance(observed,int) or observed>year or observed<2000:
        raise ValueError('Observed fee year is missing or greater than forecast year')
    # No back-filling from old fee schedules without recording a warning.
    evidence={quote_key(v):v for v in verified if v.get('source_id') == source_id
              and (v.get('year')==observed or (v.get('year') is None and year==observed))}
    if not evidence: raise NeedsApproval('No verified fee rows for selected school and year')
    selected=selection.get('fee_charges') or []
    if not selected: raise NeedsApproval('Choose verified individual fees first')
    seen=set(); lines=[]; observed_sum=0; future_sum=0
    for charge in selected:
        key=charge.get('quote_key')
        if key not in evidence: raise NeedsApproval('Selected quote cannot be verified: '+str(key))
        if key in seen:raise ValueError('Duplicate quote row: '+key)
        seen.add(key)
        e=evidence[key]
        if e.get('required') is not True and not charge.get('optional_confirmed'):
            raise NeedsApproval('Optional price must be actively selected: '+e.get('cost_name',''))
        period=e['period']
        if period=='monthly':
            months=charge.get('months')
            if type(months) is not int or not 1<=months<=12:raise NeedsApproval('Month count required (1..12)')
            multiplier=months
        elif period=='annual':
            multiplier=1
        elif period=='once':
            if charge.get('is_first_year') is not True:
                raise NeedsApproval('One-time fee applies only to confirmed first year')
            multiplier=1
        elif period=='per_event':
            occurrences=charge.get('occurrences')
            if type(occurrences) is not int or not 1<=occurrences<=20:
                raise NeedsApproval('Event count required (1..20)')
            multiplier=occurrences
        else: raise ValueError('Unsupported billing period')
        subtotal=e['amount_yen']*multiplier
        projected=(Decimal(subtotal)*((Decimal('1')+rate/100)**(year-observed))).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
        observed_sum+=subtotal; future_sum+=int(projected)
        lines.append({'quote_key':key,'cost_name':e['cost_name'],'cost_type':e.get('cost_type','other'),
                      'period':period,'multiplier':multiplier,'subtotal_at_observed_year_yen':subtotal,
                      'projected_subtotal_yen':int(projected), 'source_url':e['source_url'],
                      'data_year':observed, 'status':'user_selected_verified_quote'})
    return {'school':selection.get('school'),'stage':selection.get('stage'),'source_id':source_id,
            'observed_fee_year':observed,'forecast_year':year,
            'assumed_price_increase_pct':str(rate),
            'documented_subtotal_observed_yen':observed_sum,
            'documented_subtotal_forecast_yen':future_sum,'details':lines,
            'is_full_education_cost':False,
            'not_included':['unverified items','subsidies','unconfirmed tuition increases',
                            'any costs in other categories, courses, grades, providers'],
            'warning':'参考見積。教育費総額ではない。確認済みの項目のみ。'}
