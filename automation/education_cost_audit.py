"""Education expense completeness and evidence report (no invented zero-priced rows).

Standard library only. This is intentionally an audit; it does not silently
replace the user's app calculation model or choose schools.
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COVERAGE = ROOT / 'costs' / 'education_cost_coverage.json'


def checklist() -> dict:
    return json.loads(COVERAGE.read_text(encoding='utf-8'))


def report(verified: list[dict], sources: list[dict], *, selected: list[str] | None = None) -> dict:
    spec = checklist()
    selected = selected or list(spec['stages'])
    invalid = set(selected) - set(spec['stages'])
    if invalid:
        raise ValueError('Unknown stages: '+', '.join(sorted(invalid)))
    by_stage = defaultdict(list)
    for record in verified:
        if record.get('stage') in spec['stages'] and isinstance(record.get('amount_yen'), int):
            by_stage[record['stage']].append(record)
    by_sources = defaultdict(list)
    for source in sources:
        by_sources[source.get('stage')].append(source)
    audit = []
    for stage in selected:
        v=by_stage[stage]
        found_kinds={r.get('cost_type') for r in v if r.get('cost_type')}
        # Missing fees might truly be inapplicable; never report a zero cost.
        missing=[{'fee_type':kind,'name':spec['item_labels'][kind],
                  'status':'not_confirmed_not_zero'} for kind in spec['stages'][stage]['items'] if kind not in found_kinds]
        found=[{'fee_type':k,'name':spec['item_labels'].get(k,k)}
               for k in spec['stages'][stage]['items'] if k in found_kinds]
        audit.append({'stage':stage,'label':spec['stages'][stage]['label'],
                      'registered_official_sources':len(by_sources[stage]),
                      'verified_fee_entries':len(v),
                      'documented_fee_types':found,
                      'unconfirmed_fee_types':missing,
                      'state':('requires_source_registration' if not by_sources[stage] else
                               'partially_researched' if missing or not v else 'fee_types_detected_needs_personal_confirmation'),
                      'source_only_subtotal_yen':None,
                      'why_no_subtotal':'Sources can cover different schools/grades. Never add fees across providers.'})
    return {'schema_version':1,'purpose':'review_only_do_not_auto_apply',
            'education_fee_stages':audit,
            'registered_source_count':len(sources),
            'all_known_costs_are_for_comparison_only':True,
            'missing_costs_are_not_zero':True,
            'note':'費目が0円・対象外なのかは学校・コース単位で追加確認。任意項目は選択時だけ加算。'}


if __name__ == '__main__':
    import sys
    from cost_research import registry
    rows=[{'stage':s['stage'],'id':s['id']} for s in registry()['sources']]
    print(json.dumps(report([], rows), ensure_ascii=False, indent=2))
