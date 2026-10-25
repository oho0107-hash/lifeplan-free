"""Bounded orchestration contracts; AI opinions never constitute test evidence.

The verifier executes repository tests only in a secret-free isolated CI job.
No model request, publication or token acquisition is performed by this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import time

SCHEMA_VERSION = 1
REQUIREMENT_FIELDS = (
    'name', 'purpose', 'inputs', 'outputs', 'rules', 'conditions', 'exceptions',
    'sources', 'target_year', 'unknowns', 'related_requirements',
)
TEST_COMMANDS = (
    ('python-regression', (sys.executable, 'automation/orchestration.py', 'unit')),
    ('node-regression', ('node', '--test', '--test-reporter=tap', 'automation/test_smoke.cjs')),
    ('browser', (sys.executable, 'automation/test_browser.py')),
    ('browser-privacy', (sys.executable, 'automation/test_browser_privacy.py')),
)


def unittest_outcomes(log: str) -> dict:
    """Keep nonpassing outcomes distinct; skipped suites cannot prove readiness."""
    counts = re.findall(r'Ran (\d+) tests?', log)
    result = {'tests': int(counts[-1]) if counts else 0}
    for key, label in (('failures', 'failures'), ('errors', 'errors'), ('skipped', 'skipped'),
                       ('expected_failures', 'expected failures'), ('unexpected_successes', 'unexpected successes')):
        matches = re.findall(r'(?:^|[,(]\s*)' + re.escape(label) + r'=(\d+)', log, re.MULTILINE)
        result[key] = int(matches[-1]) if matches else 0
    return result


def digest(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def requirements_contract(payload: dict) -> list[dict]:
    """Fail closed on incomplete model output; assign deterministic local IDs."""
    items = payload.get('requirements')
    if not isinstance(items, list) or not 1 <= len(items) <= 30:
        raise ValueError('requirements must contain 1..30 structured requirements')
    result = []
    for number, original in enumerate(items, 1):
        if not isinstance(original, dict):
            raise ValueError('requirements must be objects, not untestable prose')
        row = dict(original)
        for field in REQUIREMENT_FIELDS:
            if field not in row:
                raise ValueError(f'missing requirement field: {field}')
        for field in ('name', 'purpose', 'rules'):
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError(f'{field} must be nonempty text')
        for field in ('inputs', 'outputs', 'conditions', 'exceptions', 'sources', 'unknowns', 'related_requirements'):
            if not isinstance(row[field], list):
                raise ValueError(f'{field} must be a list')
        acceptance = row.get('acceptance_tests')
        if not isinstance(acceptance, list) or not acceptance:
            raise ValueError('every requirement needs acceptance_tests')
        row['id'] = f'REQ-{number:03}'
        tests = []
        for index, case in enumerate(acceptance, 1):
            if not isinstance(case, dict) or any(
                not isinstance(case.get(key), str) or not case[key].strip()
                for key in ('input', 'expected', 'method')
            ):
                raise ValueError('acceptance test needs input, expected and method')
            tests.append({**case, 'id': f'AT-{number:03}-{index:02}', 'status': 'unrun'})
        row['acceptance_tests'] = tests
        row['counter_review'] = 'pending'
        row['final_verdict'] = 'unverified'
        result.append(row)
    return result


def candidate_manifest(request: str, requirements: list[dict], candidate: dict,
                       reviews: dict, attempts: list[dict], research_only=False) -> dict:
    """Persist evidence gaps explicitly, even if every reviewer says approved."""
    return {
        'schema_version': SCHEMA_VERSION,
        'request_sha256': digest(request),
        'execution_mode': 'sequential_model_calls_not_independent_process_agents',
        'requirements': requirements,
        'candidate_sha256': {path: digest(content) for path, content in candidate.items()},
        'reviews': reviews,
        'attempts': attempts,
        'objective_tests': 'pending_isolated_verifier',
        'acceptance_coverage': 'unverified_until_tests_are_mapped_and_executed',
        'policy_sources': 'unverified_except_exact_cost_quotes',
        'independent_recalculation': 'pending_for_affected_financial_rules',
        'final_verdict': 'evidence_pending',
        'pr_mode': 'draft',
        'auto_merge_eligible': False,
        'human_approval_required': not research_only,
        'publication_authorized': False,
    }


def tracked_snapshot(root: Path) -> dict[str, str]:
    """Bind objective evidence to content, including newly introduced test files."""
    names = subprocess.check_output(
        ['git', 'ls-files', '-c', '-o', '--exclude-standard', '-z'], cwd=root,
    ).decode('utf-8').split('\0')
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in names if name and (root / name).is_file()
            and name.endswith(('.py', '.js', '.cjs', '.html', '.json', '.yml', '.yaml', '.toml'))
            and not name.startswith(('agent-output/', 'reports/'))}


def run_verification(root: Path, out: Path, include_browser=True) -> dict:
    """Run real checks, preserve exit status, and reject a zero-test runner.

    These are regression checks, NOT proof that every proposed acceptance
    condition or current legal rule is correct. The report says so explicitly.
    """
    import re
    before = tracked_snapshot(root)
    results = []
    commands = list(TEST_COMMANDS)
    # Fail closed if the independent calculation suite is present but fails;
    # its separate policy diagnostic can report known baseline defects.
    if (root / 'automation/test_independent_finance.py').is_file():
        commands.append(('policy-diagnostic', (sys.executable, 'automation/test_independent_finance.py',
                         '--diagnose', '--output', str(out.resolve().with_name('POLICY_DIAGNOSTIC.json')))))
    if (root / 'tests/engine.test.cjs').is_file():
        commands.append(('additional-engine', ('node', '--test', '--test-reporter=tap', 'tests/engine.test.cjs')))
    for name, command in commands:
        if name.startswith('browser') and not include_browser:
            results.append({'id': name, 'status': 'unrun', 'reason': 'explicit --without-browser'})
            continue
        started = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, timeout=600)
            output, code = completed.stdout, completed.returncode
        except subprocess.TimeoutExpired:
            output, code = 'Test process exceeded 600 seconds', 124
        except OSError as error:
            output, code = f'Test runner unavailable: {error.strerror}', 127
        if name == 'python-regression':
            counts = re.findall(r'Ran (\d+) tests?', output)
            nonempty = bool(counts and int(counts[-1]) > 0)
        elif name in ('node-regression', 'additional-engine'):
            counts = re.findall(r'# tests (\d+)', output)
            nonempty = bool(counts and int(counts[-1]) > 0)
        elif name.startswith('browser'):
            nonempty = 'PASS' in output
            counts = []
        else:
            nonempty, counts = bool(output.strip()), []
        results.append({'id': name, 'command': list(command), 'exit_code': code,
                        'status': 'passed' if code == 0 and nonempty else 'failed',
                        'test_count': int(counts[-1]) if counts else None,
                        'elapsed_seconds': round(time.monotonic() - started, 2),
                        'output': output})
        if name == 'python-regression':
            summaries = re.findall(r'^UNIT_OUTCOMES=(.+)$', output, re.MULTILINE)
            results[-1]['suite_outcomes'] = json.loads(summaries[-1]) if summaries else []
    unchanged = before == tracked_snapshot(root)
    report = {
        'schema_version': SCHEMA_VERSION, 'source_sha256': before,
        'source_unchanged_during_tests': unchanged, 'checks': results,
        'status': 'passed' if unchanged and all(r['status'] == 'passed' for r in results) else 'failed',
        'scope': 'executed regression suites; requirement acceptance and law correctness require separate evidence',
        'publication_authorized': False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    verify = subs.add_parser('verify')
    verify.add_argument('--root', type=Path, default=Path('.'))
    verify.add_argument('--out', type=Path, required=True)
    verify.add_argument('--without-browser', action='store_true')
    subs.add_parser('unit', help='Run every Python unittest suite, excluding the standalone browser runner')
    args = parser.parse_args()
    if args.action == 'unit':
        import re
        directory = Path(__file__).resolve().parent
        passed, count, outcomes = True, 0, []
        # Generated parser tests must not monkeypatch unittest or imported
        # finance suites in a shared interpreter. Each suite is a child process;
        # only this trusted parent retains the aggregate verdict.
        files = sorted(directory.glob('test_*.py'), key=lambda p: (p.name == 'test_cost_research.py', p.name))
        for file in files:
            if file.name.startswith('test_browser'):
                continue
            command = [sys.executable, '-m', 'unittest', 'discover', '-s', str(directory), '-p', file.name, '-v']
            try:
                run = subprocess.run(command, capture_output=True, text=True, timeout=300)
                log = run.stdout + run.stderr
                print(log, end='', flush=True)
                result = unittest_outcomes(log)
                executed = result['tests']
                count += executed
                outcomes.append({'suite': file.name, 'exit_code': run.returncode, **result})
                passed = passed and run.returncode == 0 and executed > 0 and not any(
                    value for key, value in result.items() if key != 'tests')
            except (OSError, subprocess.TimeoutExpired):
                passed = False
                outcomes.append({'suite': file.name, 'status': 'runner_failed_or_timed_out'})
                print(f'FAIL: could not complete {file.name}', flush=True)
        print(f'Ran {count} tests across isolated Python suites', flush=True)
        print('UNIT_OUTCOMES=' + json.dumps(outcomes), flush=True)
        return 0 if passed and count else 1
    report = run_verification(args.root.resolve(), args.out, not args.without_browser)
    print(json.dumps({'status': report['status'], 'report': str(args.out),
                      'checks': [{k: row.get(k) for k in ('id', 'status', 'test_count')} for row in report['checks']]}))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
