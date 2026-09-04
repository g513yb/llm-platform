"""运行测试套件并生成可视化报告（自包含 HTML + 结构化 JSON），零第三方依赖。

配合云端流水线（tests/cloud_run.sh）：下载数据 → 本脚本跑测试 → 出报告。
报告为纯静态单文件（内嵌 CSS，折叠用原生 <details>），可直接浏览器打开 / 静态托管 / 端口转发查看。

若提供 --expected（默认 tests/expected.json），则对每个用例比对预期 vs 实际，生成评估结果
（match/mismatch/missing），并在 HTML 报告中追加"预期评估"区块。

用法：
    python tests/run_and_report.py                     # 默认 tests/report.html + tests/report.json
    python tests/run_and_report.py --html out/report.html --json out/report.json
    python tests/run_and_report.py --pattern "test_unittest*.py" --fail-fast
    python tests/run_and_report.py --no-expected       # 跳过预期评估
退出码 = 失败 + 错误数（CI 友好）。
"""
from __future__ import annotations

import argparse
import html
import json
import sys
import time
import traceback
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATUS_LABELS = {"pass": ("通过", "ok"), "fail": ("失败", "bad"),
                 "error": ("错误", "bad"), "skip": ("跳过", "warn")}


class CollectingResult(unittest.result.TestResult):
    """逐用例收集：id/模块/类/状态/耗时/traceback。"""

    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict] = []
        self._cur: dict | None = None

    def startTest(self, test) -> None:
        super().startTest(test)
        self._cur = {
            "id": test.id(),
            "module": test.__class__.__module__,
            "class": test.__class__.__name__,
            "name": getattr(test, "_testMethodName", str(test)),
            "status": "pass",
            "tb": "",
            "started": time.perf_counter(),
        }

    def stopTest(self, test) -> None:
        super().stopTest(test)
        self._cur["dur_ms"] = round((time.perf_counter() - self._cur["started"]) * 1000, 2)
        self.items.append(self._cur)
        self._cur = None

    def _trace(self, err) -> str:
        return "".join(traceback.format_exception(*err))

    def addSuccess(self, test) -> None:
        super().addSuccess(test)
        self._cur["status"] = "pass"

    def addFailure(self, test, err) -> None:
        super().addFailure(test, err)
        self._cur["status"] = "fail"
        self._cur["tb"] = self._trace(err)

    def addError(self, test, err) -> None:
        super().addError(test, err)
        self._cur["status"] = "error"
        self._cur["tb"] = self._trace(err)

    def addSkip(self, test, reason) -> None:
        super().addSkip(test, reason)
        self._cur["status"] = "skip"
        self._cur["tb"] = f"skip reason: {reason}"


# ---------------------------------------------------------------- 预期评估
def load_expected(path: Path) -> dict:
    """加载 expected.json，返回 {case_id: {...}}；文件不存在返回 {}。"""
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("cases", {})


def evaluate(items: list[dict], expected: dict) -> dict:
    """比对实际结果 vs 预期，返回评估汇总。

    汇总字段：
      match: 预期与实际一致的数量
      mismatch: 预期与实际不一致的用例列表（含 id, expected, actual, rationale）
      missing_actual: 预期有但实际未跑的用例 id 列表
      missing_expected: 实际有但预期未定义的用例 id 列表
      per_case: {id: {expected, actual, verdict}}  verdict ∈ match/mismatch/missing_expected/missing_actual
      summary_text: 一句话汇总
    """
    actual_by_id = {it["id"]: it["status"] for it in items}
    per_case: dict[str, dict] = {}
    mismatches: list[dict] = []
    missing_actual: list[str] = []
    missing_expected: list[str] = []
    match_count = 0

    for cid, exp in expected.items():
        if cid in actual_by_id:
            actual = actual_by_id[cid]
            verdict = "match" if actual == exp.get("expect") else "mismatch"
            if verdict == "match":
                match_count += 1
            else:
                mismatches.append({"id": cid, "expected": exp.get("expect"),
                                   "actual": actual, "rationale": exp.get("rationale", "")})
            per_case[cid] = {"expected": exp.get("expect"), "actual": actual,
                             "verdict": verdict, "category": exp.get("category", ""),
                             "fixture": exp.get("fixture", ""), "samples": exp.get("samples", 0),
                             "rationale": exp.get("rationale", "")}
        else:
            missing_actual.append(cid)
            per_case[cid] = {"expected": exp.get("expect"), "actual": "(未运行)",
                             "verdict": "missing_actual", "category": exp.get("category", ""),
                             "fixture": exp.get("fixture", ""), "samples": exp.get("samples", 0),
                             "rationale": exp.get("rationale", "")}

    for cid in actual_by_id:
        if cid not in expected:
            missing_expected.append(cid)
            per_case[cid] = {"expected": "(未定义)", "actual": actual_by_id[cid],
                             "verdict": "missing_expected", "category": "", "fixture": "",
                             "samples": 0, "rationale": ""}

    total = len(expected)
    parts = [f"预期 {total} 用例，匹配 {match_count}"]
    if mismatches:
        parts.append(f"不一致 {len(mismatches)}")
    if missing_actual:
        parts.append(f"未运行 {len(missing_actual)}")
    if missing_expected:
        parts.append(f"未定义 {len(missing_expected)}")
    return {
        "match": match_count,
        "mismatch": mismatches,
        "missing_actual": missing_actual,
        "missing_expected": missing_expected,
        "per_case": per_case,
        "summary_text": "；".join(parts),
    }


# ---------------------------------------------------------------- 报告生成
def _badge(status: str) -> str:
    label, kind = STATUS_LABELS.get(status, (status, "warn"))
    color = {"ok": "#16a34a", "bad": "#dc2626", "warn": "#d97706"}[kind]
    return f'<span class="badge" style="background:{color}">{label}</span>'


def _fmt_ms(ms: float) -> str:
    return f"{ms:.0f} ms" if ms < 1000 else f"{ms / 1000:.2f} s"


def _load_model_eval() -> list[dict] | None:
    p = ROOT / "tests" / "eval_result.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _model_eval_section(ev: list[dict]) -> str:
    total = len(ev)
    passed = sum(1 for e in ev if e.get("verdict") == "pass")
    high = sum(1 for e in ev if e.get("quality") == "high")
    moderate = sum(1 for e in ev if e.get("quality") == "moderate")
    na = total - passed - sum(1 for e in ev if e.get("verdict") not in ("pass", "fail"))
    color = "#16a34a" if passed == total else "#dc2626"
    cards = [
        ("总用例", total, "#0f172a"),
        ("通过", passed, "#16a34a"),
        ("高质量", high, "#16a34a"),
        ("中等", moderate, "#d97706"),
    ]
    card_html = "".join(
        f'<div class="card"><div class="num" style="color:{c}">{v}</div><div class="label">{k}</div></div>'
        for k, v, c in cards
    )
    rows = ""
    qc = {"high": "#16a34a", "moderate": "#d97706", "low": "#dc2626", "n/a": "#64748b"}
    for e in ev:
        q = e.get("quality", "n/a")
        qcolor = qc.get(q, "#64748b")
        issues = ", ".join(e.get("issues", [])) or "<span class='muted'>无</span>"
        rows += (
            f"<tr><td>{_badge(e.get('verdict',''))}</td>"
            f"<td class='mono'>{html.escape(e.get('test_id',''))}</td>"
            f"<td>{html.escape(e.get('domain',''))}</td>"
            f"<td class='num'>{e.get('kept',0)}/{e.get('dropped',0)}</td>"
            f"<td><span class='badge' style='background:{qcolor}'>{html.escape(q)}</span></td>"
            f"<td>{html.escape(e.get('summary',''))}</td>"
            f"<td><details><summary>问题</summary>{html.escape(issues)}</details></td></tr>"
        )
    return (
        f'<h2 style="color:{color}">模型语义质量评估 · {passed}/{total} 通过</h2>'
        f'<div class="cards">{card_html}</div>'
        f'<table><tr><th>评估</th><th>用例</th><th>领域</th><th class="num">kept/drop</th>'
        f'<th>质量</th><th>评估摘要</th><th>问题</th></tr>{rows}</table>'
    )


def render_html(meta: dict, items: list[dict], evaluation: dict | None = None) -> str:
    n = meta["total"]
    rate = (meta["passed"] / n * 100) if n else 100.0
    bar_color = "#16a34a" if rate >= 95 else ("#d97706" if rate >= 70 else "#dc2626")

    # 按测试类聚合
    classes: dict[str, Counter] = {}
    order: list[str] = []
    for it in items:
        k = f"{it['module']}.{it['class']}"
        if k not in classes:
            classes[k] = Counter()
            order.append(k)
        classes[k][it["status"]] += 1

    class_rows = []
    for k in order:
        c = classes[k]
        tot = sum(c.values())
        ok = tot - c["fail"] - c["error"]
        pct = ok * 100 / tot if tot else 100
        cc = "#16a34a" if c["fail"] + c["error"] == 0 else "#dc2626"
        cls_link = "".join(f"<div class='cls'>{html.escape(k)}</div>"
                           f"<small>{tot} 用例 · {c['fail'] + c['error']} 失败</small>")
        class_rows.append(
            f'<div class="cls-card"><div class="cls-bar" style="width:{pct:.1f}%;background:{cc}"></div>'
            f'{cls_link}<div class="cls-pct" style="color:{cc}">{pct:.0f}%</div></div>'
        )

    case_rows = []
    for it in items:
        short = it["id"].removeprefix(f"{it['module']}.")
        tb_html = (f"<pre>{html.escape(it['tb'])}</pre>" if it["tb"]
                   else "<span class='muted'>无</span>")
        case_rows.append(
            f"<tr><td>{_badge(it['status'])}</td>"
            f"<td class='mono'>{html.escape(short)}</td>"
            f"<td class='num'>{_fmt_ms(it['dur_ms'])}</td>"
            f"<td><details><summary>查看详情</summary>{tb_html}</details></td></tr>"
        )
    case_table = "".join(case_rows) or "<tr><td colspan=4 class='muted'>无用例</td></tr>"

    cards = [
        ("总用例", meta["total"], "#0f172a"),
        ("通过", meta["passed"], "#16a34a"),
        ("失败", meta["failed"], "#dc2626"),
        ("错误", meta["errors"], "#dc2626"),
        ("跳过", meta["skipped"], "#d97706"),
        ("耗时", _fmt_ms(meta["duration_ms"]), "#2563eb"),
    ]
    card_html = "".join(
        f'<div class="card"><div class="num" style="color:{color}">{v}</div><div class="label">{k}</div></div>'
        for k, v, color in cards
    )

    # 预期评估区块
    # 模型语义质量评估区块
    model_eval = _load_model_eval()
    model_eval_html = _model_eval_section(model_eval) if model_eval else ""

    eval_section = ""
    if evaluation:
        ev = evaluation
        ev_ok = len(ev["mismatch"]) == 0 and len(ev["missing_actual"]) == 0 and len(ev["missing_expected"]) == 0
        ev_color = "#16a34a" if ev_ok else "#dc2626"
        ev_cards = [
            ("匹配", ev["match"], "#16a34a"),
            ("不一致", len(ev["mismatch"]), "#dc2626"),
            ("未运行", len(ev["missing_actual"]), "#d97706"),
            ("未定义", len(ev["missing_expected"]), "#d97706"),
        ]
        ev_card_html = "".join(
            f'<div class="card"><div class="num" style="color:{c}">{v}</div><div class="label">{k}</div></div>'
            for k, v, c in ev_cards
        )
        # 不一致表
        mismatch_rows = ""
        for m in ev["mismatch"]:
            mismatch_rows += (
                f"<tr><td class='mono'>{html.escape(m['id'])}</td>"
                f"<td>{_badge(m['expected'])}</td><td>{_badge(m['actual'])}</td>"
                f"<td><details><summary>预期依据</summary>{html.escape(m['rationale'])}</details></td></tr>"
            )
        mismatch_table = mismatch_rows and (
            "<h2>预期不一致</h2><table>"
            "<tr><th>用例</th><th>预期</th><th>实际</th><th>预期依据</th></tr>"
            f"{mismatch_rows}</table>"
        ) or ""
        # 未运行/未定义
        missing_html = ""
        if ev["missing_actual"]:
            missing_html += f"<p class='muted'>预期有但未运行：{', '.join(html.escape(x) for x in ev['missing_actual'])}</p>"
        if ev["missing_expected"]:
            missing_html += f"<p class='muted'>实际有但预期未定义：{', '.join(html.escape(x) for x in ev['missing_expected'])}</p>"
        # 每用例预期对照（可折叠）
        per_case_rows = ""
        for cid, pc in sorted(ev["per_case"].items()):
            vc = {"match": "#16a34a", "mismatch": "#dc2626",
                  "missing_actual": "#d97706", "missing_expected": "#d97706"}.get(pc["verdict"], "#64748b")
            per_case_rows += (
                f"<tr><td class='mono'>{html.escape(cid)}</td>"
                f"<td>{html.escape(pc['category'])}</td>"
                f"<td class='num'>{pc['samples']}</td>"
                f"<td>{_badge(pc['expected']) if pc['expected'] in STATUS_LABELS else html.escape(str(pc['expected']))}</td>"
                f"<td>{_badge(pc['actual']) if pc['actual'] in STATUS_LABELS else html.escape(str(pc['actual']))}</td>"
                f"<td><span class='badge' style='background:{vc}'>{pc['verdict']}</span></td>"
                f"<td><details><summary>依据</summary>{html.escape(pc['rationale'])}</details></td></tr>"
            )
        per_case_table = per_case_rows and (
            "<h2>预期对照明细</h2><table>"
            "<tr><th>用例</th><th>类别</th><th class='num'>样本数</th><th>预期</th><th>实际</th><th>评估</th><th>依据</th></tr>"
            f"{per_case_rows}</table>"
        ) or ""
        eval_section = (
            f'<h2 style="color:{ev_color}">预期评估 · {html.escape(ev["summary_text"])}</h2>'
            f'<div class="cards">{ev_card_html}</div>'
            f'{mismatch_table}{missing_html}{per_case_table}'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>llm-platform 测试报告</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system,"Segoe UI","Microsoft YaHei",sans-serif; background:#f1f5f9; color:#0f172a; }}
  header {{ background:#0f172a; color:#f8fafc; padding:22px 28px; }}
  header h1 {{ margin:0 0 6px; font-size:20px; }}
  header .sub {{ color:#94a3b8; font-size:13px; }}
  main {{ padding:22px 28px 40px; max-width:1080px; margin:0 auto; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:12px; margin:18px 0; }}
  .card {{ background:#fff; border-radius:12px; padding:14px 16px; box-shadow:0 1px 3px rgba(15,23,42,.08); text-align:center; }}
  .card .num {{ font-size:22px; font-weight:700; }}
  .card .label {{ color:#64748b; font-size:12px; margin-top:2px; }}
  .rate-bar {{ background:#e2e8f0; border-radius:999px; height:12px; overflow:hidden; margin:10px 0 4px; }}
  .rate-bar span {{ display:block; height:100%; border-radius:999px; }}
  h2 {{ font-size:15px; margin:26px 0 10px; color:#334155; }}
  .cls-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:10px; }}
  .cls-card {{ position:relative; background:#fff; border-radius:10px; padding:12px 14px; box-shadow:0 1px 3px rgba(15,23,42,.08); overflow:hidden; }}
  .cls-bar {{ position:absolute; left:0; top:0; bottom:0; opacity:.10; }}
  .cls-card small {{ color:#64748b; }}
  .cls-pct {{ position:absolute; right:12px; top:12px; font-weight:700; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 1px 3px rgba(15,23,42,.08); }}
  th,td {{ text-align:left; padding:9px 12px; border-bottom:1px solid #f1f5f9; font-size:13px; vertical-align:top; }}
  th {{ background:#f8fafc; color:#64748b; font-weight:600; }}
  .mono {{ font-family:ui-monospace,Consolas,monospace; }}
  .num {{ text-align:right; white-space:nowrap; }}
  .muted {{ color:#94a3b8; }}
  .badge {{ color:#fff; font-size:11px; padding:2px 8px; border-radius:999px; }}
  details {{ font-size:12px; }}
  pre {{ background:#0f172a; color:#f8fafc; padding:10px; border-radius:8px; overflow:auto; white-space:pre-wrap; }}
  footer {{ text-align:center; color:#94a3b8; font-size:12px; margin-top:30px; }}
</style></head><body>
<header>
  <h1>llm-platform 测试报告</h1>
  <div class="sub">时间 {html.escape(meta['timestamp'])} · 命令 python -m unittest discover -s tests · 总用例 {n}</div>
</header>
<main>
  <div class="cards">{card_html}</div>
  <div class="rate-bar"><span style="width:{rate:.1f}%;background:{bar_color}"></span></div>
  <div style="color:{bar_color};font-size:13px;font-weight:600">通过率 {rate:.1f}%</div>
  {eval_section}
  {model_eval_html}
  <h2>按测试类</h2>
  <div class="cls-grid">{''.join(class_rows)}</div>
  <h2>用例明细</h2>
  <table>
    <tr><th>状态</th><th>用例</th><th class="num">耗时</th><th>失败详情</th></tr>
    {case_table}
  </table>
  <footer>由 tests/run_and_report.py 生成（零依赖，自包含单文件）</footer>
</main></body></html>
"""


def render_json(meta: dict, items: list[dict], evaluation: dict | None = None) -> dict:
    out = {"meta": meta, "tests": items}
    if evaluation is not None:
        out["evaluation"] = {
            "match": evaluation["match"],
            "mismatch": evaluation["mismatch"],
            "missing_actual": evaluation["missing_actual"],
            "missing_expected": evaluation["missing_expected"],
            "summary_text": evaluation["summary_text"],
            "per_case": evaluation["per_case"],
        }
    return out


# ---------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_and_report.py", description="运行测试并生成可视化报告（HTML+JSON）。")
    p.add_argument("--html", type=Path, default=ROOT / "tests" / "report.html")
    p.add_argument("--json", type=Path, default=ROOT / "tests" / "report.json")
    p.add_argument("--pattern", default="test*.py", help="discover 的文件模式（默认 test*.py）")
    p.add_argument("--start-dir", type=Path, default=ROOT / "tests")
    p.add_argument("--fail-fast", action="store_true")
    p.add_argument("--expected", type=Path, default=ROOT / "tests" / "expected.json",
                   help="预期定义 JSON（默认 tests/expected.json）；不存在则跳过评估")
    p.add_argument("--no-expected", action="store_true", help="跳过预期评估")
    return p


def main() -> int:
    args = build_parser().parse_args()
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(args.start_dir), top_level_dir=str(ROOT), pattern=args.pattern)
    result = CollectingResult()
    result.failfast = args.fail_fast

    t0 = time.perf_counter()
    suite.run(result)
    duration_ms = (time.perf_counter() - t0) * 1000

    items = sorted(result.items, key=lambda x: (x["module"], x["class"], x["name"]))
    meta = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(items),
        "passed": sum(1 for i in items if i["status"] == "pass"),
        "failed": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "duration_ms": round(duration_ms, 2),
    }

    evaluation = None
    if not args.no_expected:
        expected = load_expected(args.expected)
        if expected:
            evaluation = evaluate(items, expected)
            print(f"预期评估: {evaluation['summary_text']}")
        else:
            print(f"预期评估: 跳过（未找到 {args.expected}）")

    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(render_html(meta, items, evaluation), encoding="utf-8")
    args.json.write_text(json.dumps(render_json(meta, items, evaluation), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Ran {meta['total']} tests · pass {meta['passed']} / fail {meta['failed']} / error {meta['errors']} / skip {meta['skipped']} · {_fmt_ms(meta['duration_ms'])}")
    print(f"HTML 报告: {args.html}")
    print(f"JSON 数据: {args.json}")

    for i in items:
        if i["status"] in ("fail", "error"):
            print(f"\n---- {i['id']} [{i['status']}] ----\n{i['tb'].rstrip()}")
    if evaluation:
        for m in evaluation["mismatch"]:
            print(f"\n---- 预期不一致: {m['id']} · 预期 {m['expected']} / 实际 {m['actual']} ----\n{m['rationale']}")
    return meta["failed"] + meta["errors"]


if __name__ == "__main__":
    raise SystemExit(main())