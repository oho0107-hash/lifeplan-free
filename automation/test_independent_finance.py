"""Independent Python arithmetic against BOTH shipping JavaScript engines.

Ordinary unittest tests cover supported mathematical contracts, not policy accuracy.
--diagnose records reproducible unresolved defects; --strict fails publication.
All inputs are invented. No network, keys, family data, or AI judgments are used.
"""
import argparse
import calendar
from datetime import date
from decimal import Decimal, localcontext
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def probe(method, args):
    result = subprocess.run(
        ["node", str(ROOT / "automation/finance_probe.cjs")],
        input=json.dumps([{"method": method, "args": args}]), text=True,
        capture_output=True, check=True, timeout=30,
    )
    return json.loads(result.stdout)[0]


def base(**updates):
    info = dict(husband_birth="1990-01-01", wife_birth="1991-06-01",
                kid1_birth="", kid2_birth="", kid3_birth="", kid4_has="no",
                husband_month_net="0", wife_month_net="0", husband_bonus_net="0",
                wife_bonus_net="0", current_savings="0", current_invest_balance="0",
                annual_investment="0", investment_return="0", living_cost_annual="0",
                living_cost_growth="0", child_allowance_mode="no", univ_free_use="no",
                hs_free_use="no", loan_principal="0", travel_cost="0")
    info.update({key: str(value) for key, value in updates.items()})
    return info


def fixed_payment(principal, annual_percent, years, periods_per_year):
    """Discounted-cash-flow oracle, not a copy of the JS annuity formula."""
    with localcontext() as context:
        context.prec = 45
        rate = Decimal(str(annual_percent)) / 100 / periods_per_year
        discount = sum((Decimal(1) + rate) ** -period
                       for period in range(1, years * periods_per_year + 1))
        return float(Decimal(str(principal)) / discount)


def school_grade(birthday, year, month):
    """Find the first April 1 on which the child has reached age six."""
    birth = date.fromisoformat(birthday)
    # Japanese age attainment is the day before birthday: April 1 births enter
    # with the preceding year's April 2 cohort.
    admission = birth.year + 6
    if (birth.month, birth.day) > (4, 1):
        admission += 1
    academic_year = year if month >= 4 else year - 1
    return academic_year - admission + 1


class IndependentFinanceTests(unittest.TestCase):
    def both(self, method, args):
        result = probe(method, args)
        self.assertEqual(result["standalone"], result["embedded"],
                         "Published embedded engine differs from source")
        self.assertNotIn("error", result["standalone"])
        return result["standalone"]["value"]

    def test_asset_conservation_48_independent_examples(self):
        for cash in (0, 100, -50):
            for invested in (0, 200):
                for surplus in (-250, 300):
                    for rate in (-100, 5):
                        with self.subTest(cash=cash, invested=invested,
                                          surplus=surplus, rate=rate):
                            actual = self.both("settleAssets", [cash, invested, surplus, 60, rate])
                            # Transfers and liquidation cannot create net assets.
                            expected = cash + surplus + invested * (1 + rate / 100)
                            self.assertAlmostEqual(actual["total"], expected, places=7)
                            self.assertAlmostEqual(actual["cash"] + actual["invest"], expected)
                            self.assertEqual(actual["debt"], max(0, -actual["cash"]))
                            self.assertGreaterEqual(actual["invest"], 0)

    def test_constant_monthly_mortgage_discounted_cashflows(self):
        principal, rate, years = 12000000, 1.5, 10
        expected_month = fixed_payment(principal, rate, years, 12)
        info = base(loan_principal=principal, loan_start_date="2026-01-01",
                    loan_years=years, loan_rate_initial=rate)
        rows = self.both("mortgageSchedule", [info])
        self.assertEqual(len(rows), years)
        self.assertAlmostEqual(rows[0]["standardPay"], expected_month * 12, delta=1)
        for row in rows:
            self.assertAlmostEqual(row["startBalance"] + row["interest"]
                                   - row["totalPay"], row["endBalance"], delta=1)
        self.assertLessEqual(rows[-1]["endBalance"], 1)

    def test_zero_interest_prepayment_conserves_principal(self):
        info = base(loan_principal=1200000, loan_start_date="2026-01-01",
                    loan_years=2, loan_rate_initial=0,
                    loan_prepay_once_date="2026-06-01", loan_prepay_once_amount=200000)
        rows = self.both("mortgageSchedule", [info])
        self.assertAlmostEqual(sum(row["totalPay"] for row in rows), 1200000)
        self.assertEqual(sum(row["interest"] for row in rows), 0)
        self.assertEqual(sum(row["prepay"] for row in rows), 200000)

    def test_school_year_boundary_from_admission_dates(self):
        for birthday in ("2014-04-02", "2015-04-01", "2015-04-02", "2020-02-29"):
            actual = self.both("education", [base(kid1_birth=birthday,
                                                  extra_activity_level="low"), 2026, 1])
            observed = {row["stage"]: row["months"] for row in actual}
            expected = {}
            for month in range(1, 13):
                grade = school_grade(birthday, 2026, month)
                stage = ("0-2歳" if grade <= -3 else "3-5歳" if grade <= 0
                         else "小学校" if grade <= 6 else "中学校" if grade <= 9
                         else "高校" if grade <= 12 else "大学" if grade <= 16 else "なし")
                if stage != "なし":
                    expected[stage] = expected.get(stage, 0) + 1
            self.assertEqual(observed, expected, birthday)

    def test_calendar_cashflow_rollforward_uses_each_cost_once(self):
        info = base(husband_month_net=300000, wife_month_net=200000,
                    husband_bonus_net=600000, wife_bonus_net=400000,
                    current_savings=1000000, current_invest_balance=500000,
                    living_cost_annual=2400000, annual_investment=300000)
        result = self.both("calculate", [info, {"startYear": 2026}])
        previous = 1500000
        for row in result["cashflow"]:
            self.assertEqual(row[7], 7000000)  # two salaries x12 + annual bonuses
            self.assertEqual(row[13], sum(row[8:13]))
            self.assertEqual(row[18], row[7] - row[13])
            self.assertEqual(row[16], previous + row[18])
            self.assertEqual(row[16], row[14] + row[15])
            previous = row[16]

    def test_newborn_allowance_not_full_birth_year(self):
        # Without older siblings and with application on time: next-month
        # entitlement. This verifies the timing assumption, not eligibility.
        for month in (1, 6, 12):
            birthday = f"2026-{month:02d}-{calendar.monthrange(2026, month)[1]:02d}"
            info = base(kid1_birth=birthday, child_allowance_mode="yes")
            row = self.both("calculate", [info, {"startYear": 2026}])["cashflow"][0]
            self.assertEqual(row[7], (12 - month) * 15000)

    def test_zero_to_four_children_twins_and_no_duplicate_costs(self):
        births = ("2020-04-01", "2020-04-01", "2022-04-02", "2028-01-01")
        for number in range(5):
            info = base(**{f"kid{index+1}_birth": births[index] if index < number else ""
                           for index in range(4)})
            info["kid4_has"] = "yes" if number == 4 else "no"
            result = self.both("calculate", [info, {"startYear": 2026}])
            education = self.both("education", [info, 2026, len(result["cashflow"])])
            previous = 0
            for row in result["cashflow"]:
                expected = sum(item["net"] for item in education if item["year"] == row[0])
                self.assertEqual(row[8], expected)
                self.assertEqual(row[16], previous - expected)
                self.assertEqual(row[17], max(0, -row[16]))
                previous = row[16]
            self.assertEqual(len({(item["year"], item["order"], item["stage"])
                                  for item in education}), len(education))

    def test_invalid_dates_nonfinite_and_fourth_child_are_rejected(self):
        for info in (base(husband_birth="2023-02-29"),
                     base(wife_month_net="NaN"),
                     base(husband_month_net="Infinity"),
                     base(kid4_has="yes", kid4_birth="")):
            result = probe("calculate", [info, {"startYear": 2026}])
            for variant in ("standalone", "embedded"):
                self.assertIn("error", result[variant])


def diagnose():
    """Fixed counterexamples. Failures are real gaps, never expectedFailure."""
    checks = []

    def add(identifier, severity, title, expected, actual, source, requirement):
        values = {key: value.get("value") for key, value in actual.items()}
        valid = all(value == expected for value in values.values())
        checks.append(dict(id=identifier, severity=severity, title=title,
                           expected=expected, actual=values,
                           status="pass" if valid else "unresolved",
                           source=source, requirement=requirement))

    info = base(loan_principal=1200000, loan_main_principal=0,
                loan_start_date="2026-01-01", loan_years=1, loan_rate_initial=12)
    result = probe("mortgageSchedule", [info])
    expected = round(fixed_payment(1200000, 12, 1, 2) * 2)
    actual = {key: {"value": round(value["value"][0]["standardPay"])}
              for key, value in result.items()}
    add("FIN-BONUS-001", "High", "年2回のボーナス返済を月割り返済に置換している",
        expected, actual, "数学的基準: 年利12%・半年利6%の2回均等返済の現在価値=120万円",
        "ボーナス返済月と毎月返済を区別し、利息と残高を独立照合する")

    info = base(wife_month_net=200000, kid1_birth="2026-12-20")
    result = probe("calculate", [info, {"startYear": 2026}])
    # Counterexample is explicitly an assumption: no maternity/parental leave
    # and salary paid all year. The UI has no leave dates to express this case.
    actual = {key: {"value": value["value"]["cashflow"][0][7]}
              for key, value in result.items()}
    add("FIN-LEAVE-001", "High", "出産の年に妻の給与を無条件で全額ゼロにする",
        2400000, actual, "合成入力: 月手取り20万円、12月出生、休業なしのシナリオ",
        "産休・育休の実際の期間と給与・給付の入力を分離する。期待値は制度給付額ではない")

    info = base(living_cost_annual=1000000, living_cost_growth=2,
                kid1_birth="2000-06-01")
    result = probe("calculate", [info, {"startYear": 2026}])
    actual = {key: {"value": value["value"]["cashflow"][1][9]}
              for key, value in result.items()}
    add("FIN-INFLATION-001", "High", "末子卒業後に指定生活費上昇率が適用されない",
        1020000, actual, "数学的基準: 100万円×1.02、子は2000年出生・既卒、年2027",
        "入力した生活費上昇率を世帯構成と独立して適用する")

    unresolved = [check["id"] for check in checks if check["status"] != "pass"]
    return dict(schema_version=1, kind="independent_finance_counterexamples",
                input_privacy="fabricated_only", copied_implementation=False,
                checks=checks, unresolved=unresolved,
                counts={"checks": len(checks), "passed": len(checks)-len(unresolved),
                        "unresolved": len(unresolved),
                        "critical_high": sum(check["severity"] in ("Critical", "High")
                                             and check["status"] != "pass" for check in checks)},
                publication_allowed=not unresolved,
                limitations=["全制度・全機能の網羅監査ではない",
                             "制度一次資料の現行性はこのオフライン診断では未検証",
                             "休業なしケースは入力表現不足を含む。制度上の給付額の期待値ではない"])


if __name__ == "__main__":
    if "--diagnose" in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument("--diagnose", action="store_true")
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", type=Path)
        args = parser.parse_args()
        report = diagnose()
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        raise SystemExit(1 if args.strict and not report["publication_allowed"] else 0)
    unittest.main()
