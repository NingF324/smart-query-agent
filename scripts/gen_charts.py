"""Generate comprehensive analysis charts for Spider test results."""
import json
import sqlite3
import re
from pathlib import Path
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

spider_db_path = Path("E:/spider_data/spider_data/database")
save_dir = Path("results")

with open("results/spider_results_20260331_194621.json", "r", encoding="utf-8") as f:
    data = json.load(f)
cases = data["cases"]


def norm_sql(s):
    return re.sub(r"\s+", " ", s.strip()).lower()


def execute_sql(sql, db_id):
    db_file = spider_db_path / db_id / f"{db_id}.sqlite"
    try:
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()
        cur.execute(sql.rstrip(";"))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return None


def check_result(gold_sql, pred_sql, db_id):
    g = execute_sql(gold_sql, db_id)
    p = execute_sql(pred_sql, db_id)
    if g is None or p is None:
        return False

    def _norm(row):
        return tuple(str(v).strip().lower() if isinstance(v, str) else v for v in row)

    return set(_norm(r) for r in g) == set(_norm(r) for r in p)


# ── Re-evaluate all cases ──
print("Re-evaluating all cases with fixed comparison...")
all_results = []
db_stats = {}

for c in cases:
    db_id = c["db_id"]
    pred_sql = c["predicted_sql"]
    sql_match = norm_sql(c["gold_sql"]) == norm_sql(pred_sql) if pred_sql.strip() else False
    result_match = check_result(c["gold_sql"], pred_sql, db_id) if pred_sql.strip() else False

    all_results.append({
        "db_id": db_id,
        "question": c["question"],
        "gold_sql": c["gold_sql"],
        "pred_sql": pred_sql,
        "sql_match": sql_match,
        "result_match": result_match,
        "error": c["error"],
        "time": c["execution_time"],
    })

    db_stats.setdefault(db_id, {"total": 0, "sql_ok": 0, "res_ok": 0, "times": []})
    db_stats[db_id]["total"] += 1
    if sql_match:
        db_stats[db_id]["sql_ok"] += 1
    if result_match:
        db_stats[db_id]["res_ok"] += 1
    db_stats[db_id]["times"].append(c["execution_time"])

total = len(all_results)
valid = total
sql_ok_count = sum(1 for r in all_results if r["sql_match"])
res_ok_count = sum(1 for r in all_results if r["result_match"])
both_ok = sum(1 for r in all_results if r["sql_match"] and r["result_match"])
result_only = sum(1 for r in all_results if r["result_match"] and not r["sql_match"])
both_fail = sum(1 for r in all_results if not r["result_match"] and not r["sql_match"])
errors = sum(1 for r in all_results if r["error"])
times = [r["time"] for r in all_results]

print(f"Done. ResOK={res_ok_count}/{total} ({res_ok_count/total*100:.1f}%)")

# ── Failure categories ──
true_fail = [r for r in all_results if not r["result_match"] and not r["error"] and r["pred_sql"].strip()]
fail_cats = Counter()
for r in true_fail:
    gs = norm_sql(r["gold_sql"])
    ps = norm_sql(r["pred_sql"])
    if "join" in gs and "join" not in ps:
        fail_cats["缺少 JOIN"] += 1
    elif "limit" in ps and "limit" not in gs:
        fail_cats["多余的 LIMIT"] += 1
    elif "distinct" in ps and "distinct" not in gs:
        fail_cats["多余的 DISTINCT"] += 1
    elif "order by" in ps and "order by" not in gs:
        fail_cats["多余的 ORDER BY"] += 1
    elif gs.count("select") > 1 and ps.count("select") <= 1:
        fail_cats["缺少子查询"] += 1
    elif ps.count("select") > 1 and gs.count("select") <= 1:
        fail_cats["多余的子查询"] += 1
    elif "having" in gs and "having" not in ps:
        fail_cats["缺少 HAVING"] += 1
    else:
        fail_cats["逻辑错误"] += 1


# ═══════════════════════════════════════════════════════════════════════
# FIGURE: 4-panel comprehensive chart
# ═══════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(20, 14))
fig.suptitle(
    "Spider Dev Set \u5168\u91cf\u6d4b\u8bd5\u5206\u6790\u62a5\u544a  (n=1034)",
    fontsize=18, fontweight="bold", y=0.98,
)

# ── 1. Result Distribution Pie ──
ax1 = fig.add_subplot(2, 3, 1)
labels = ["Result\nMatch", "SQL+Result\nMatch", "Fail", "Error"]
sizes = [result_only, both_ok, both_fail, errors]
colors = ["#4CAF50", "#2196F3", "#FF9800", "#F44336"]
filtered = [(l, s, c) for l, s, c in zip(labels, sizes, colors) if s > 0]
fl, fs, fc = zip(*filtered)
wedges, texts, autotexts = ax1.pie(
    fs, labels=fl, colors=fc, autopct="%1.1f%%",
    startangle=90, textprops={"fontsize": 10},
    pctdistance=0.75,
)
for t in autotexts:
    t.set_fontsize(9)
    t.set_fontweight("bold")
ax1.set_title(f"\u7ed3\u679c\u5206\u5e03 (Res Match: {res_ok_count/total*100:.1f}%)", fontsize=12, pad=10)

# ── 2. Accuracy Metrics Bar ──
ax2 = fig.add_subplot(2, 3, 2)
metrics = ["SQL Exact\nMatch", "Result\nMatch (EX)", "Failure\nRate", "Error\nRate"]
values = [
    sql_ok_count / valid * 100,
    res_ok_count / valid * 100,
    both_fail / valid * 100,
    errors / valid * 100,
]
bar_colors = ["#2196F3", "#4CAF50", "#FF9800", "#F44336"]
bars = ax2.bar(metrics, values, color=bar_colors, width=0.6, edgecolor="white", linewidth=1.5)
for bar, val in zip(bars, values):
    ax2.text(
        bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
        f"{val:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold",
    )
ax2.set_ylim(0, 100)
ax2.set_ylabel("\u767e\u5206\u6bd4 (%)", fontsize=10)
ax2.set_title("\u51c6\u786e\u7387\u6307\u6807", fontsize=12)
ax2.axhline(y=50, color="gray", linestyle="--", alpha=0.3)
ax2.grid(axis="y", alpha=0.2)

# ── 3. Per-Database Result Accuracy (sorted) ──
ax3 = fig.add_subplot(2, 3, 3)
sorted_dbs = sorted(db_stats.items(), key=lambda x: x[1]["res_ok"] / x[1]["total"])
db_names = [d[0] for d in sorted_dbs]
res_accs = [d[1]["res_ok"] / d[1]["total"] * 100 for d in sorted_dbs]
sql_accs = [d[1]["sql_ok"] / d[1]["total"] * 100 for d in sorted_dbs]
y_pos = np.arange(len(db_names))

bars1 = ax3.barh(y_pos, res_accs, height=0.4, color="#4CAF50", alpha=0.85, label="Result Match")
ax3.barh(y_pos + 0.4, sql_accs, height=0.4, color="#2196F3", alpha=0.85, label="SQL Match")
ax3.set_yticks(y_pos + 0.2)
ax3.set_yticklabels(db_names, fontsize=7)
ax3.set_xlim(0, 105)
ax3.set_xlabel("\u51c6\u786e\u7387 (%)", fontsize=10)
ax3.set_title("\u5404\u6570\u636e\u5e93\u51c6\u786e\u7387", fontsize=12)
ax3.legend(fontsize=8, loc="lower right")
ax3.axvline(x=69.1, color="red", linestyle="--", alpha=0.5, linewidth=1)
ax3.text(69.2, len(db_names) - 0.5, f"\u5e73\u5747 69.1%", fontsize=7, color="red")

# ── 4. Failure Category Breakdown ──
ax4 = fig.add_subplot(2, 3, 4)
cats = fail_cats.most_common()
cat_names = [c[0] for c in cats]
cat_vals = [c[1] for c in cats]
cat_colors = plt.cm.Set2(np.linspace(0, 1, len(cats)))
wedges2, texts2, autotexts2 = ax4.pie(
    cat_vals, labels=cat_names, colors=cat_colors,
    autopct="%1.1f%%", startangle=140, textprops={"fontsize": 9},
    pctdistance=0.8,
)
for t in autotexts2:
    t.set_fontsize(8)
ax4.set_title(f"\u5931\u8d25\u5206\u7c7b (n={len(true_fail)})", fontsize=12, pad=10)

# ── 5. Performance Distribution ──
ax5 = fig.add_subplot(2, 3, 5)
ax5.hist(times, bins=40, color="#2196F3", edgecolor="white", alpha=0.8)
avg_t = np.mean(times)
p50 = np.median(times)
p95 = np.percentile(times, 95)
ax5.axvline(x=avg_t, color="red", linestyle="--", linewidth=1.5, label=f"Avg={avg_t:.1f}s")
ax5.axvline(x=p50, color="green", linestyle="--", linewidth=1.5, label=f"P50={p50:.1f}s")
ax5.axvline(x=p95, color="orange", linestyle="--", linewidth=1.5, label=f"P95={p95:.1f}s")
ax5.set_xlabel("\u54cd\u5e94\u65f6\u95f4 (\u79d2)", fontsize=10)
ax5.set_ylabel("\u7528\u4f8b\u6570", fontsize=10)
ax5.set_title(f"\u6027\u80fd\u5206\u5e03 (Avg={avg_t:.1f}s, Total={sum(times)/3600:.1f}h)", fontsize=12)
ax5.legend(fontsize=8)

# ── 6. DB Size vs Accuracy Scatter ──
ax6 = fig.add_subplot(2, 3, 6)
db_sizes = [db_stats[d]["total"] for d in db_names]
db_accs = [db_stats[d]["res_ok"] / db_stats[d]["total"] * 100 for d in db_names]
db_avg_t = [np.mean(db_stats[d]["times"]) for d in db_names]
scatter = ax6.scatter(db_sizes, db_accs, c=db_avg_t, cmap="RdYlGn_r", s=100, edgecolors="black", linewidth=0.5, alpha=0.8)
cbar = plt.colorbar(scatter, ax=ax6)
cbar.set_label("\u5e73\u5747\u54cd\u5e94\u65f6\u95f4 (s)", fontsize=9)
for i, db in enumerate(db_names):
    ax6.annotate(db[:10], (db_sizes[i], db_accs[i]), fontsize=6, ha="center", va="bottom", xytext=(0, 5), textcoords="offset points")
ax6.set_xlabel("\u7528\u4f8b\u6570", fontsize=10)
ax6.set_ylabel("Result Match (%)", fontsize=10)
ax6.set_title("\u6570\u636e\u5e93\u89c4\u6a21 vs \u51c6\u786e\u7387 (\u989c\u8272=\u8017\u65f6)", fontsize=12)
ax6.grid(alpha=0.2)

plt.tight_layout(rect=[0, 0, 1, 0.95])
chart_path = save_dir / "spider_analysis_chart.png"
fig.savefig(chart_path, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"Chart saved: {chart_path}")


# ═══════════════════════════════════════════════════════════════════════
# FIGURE 2: Detailed per-database performance heatmap
# ═══════════════════════════════════════════════════════════════════════
fig2, ax_hm = plt.subplots(figsize=(14, 8))

sorted_dbs_full = sorted(db_stats.items(), key=lambda x: x[1]["res_ok"] / x[1]["total"], reverse=True)
hm_names = [d[0][:25] for d in sorted_dbs_full]
hm_res = [d[1]["res_ok"] / d[1]["total"] * 100 for d in sorted_dbs_full]
hm_sql = [d[1]["sql_ok"] / d[1]["total"] * 100 for d in sorted_dbs_full]
hm_time = [np.mean(d[1]["times"]) for d in sorted_dbs_full]
hm_n = [d[1]["total"] for d in sorted_dbs_full]

y_pos2 = np.arange(len(hm_names))
height = 0.25

bars_r = ax_hm.barh(y_pos2, hm_res, height=height, color="#4CAF50", alpha=0.85, label="Result Match %")
ax_hm.barh(y_pos2 + height, hm_sql, height=height, color="#2196F3", alpha=0.85, label="SQL Match %")

ax_hm2 = ax_hm.twiny()
ax_hm2.barh(y_pos2 + 2 * height, hm_time, height=height, color="#FF9800", alpha=0.7, label="Avg Time (s)")

ax_hm.set_yticks(y_pos2 + height)
ax_hm.set_yticklabels([f"{n} (n={c})" for n, c in zip(hm_names, hm_n)], fontsize=8)
ax_hm.set_xlim(0, 110)
ax_hm2.set_xlim(0, max(hm_time) * 1.3)
ax_hm.set_xlabel("\u51c6\u786e\u7387 (%)", fontsize=10)
ax_hm2.set_xlabel("\u5e73\u5747\u54cd\u5e94\u65f6\u95f4 (\u79d2)", fontsize=10, color="#FF9800")
ax_hm.set_title("\u5168\u6570\u636e\u5e93\u7efc\u5408\u5bf9\u6bd4", fontsize=14, fontweight="bold", pad=20)

lines1, labels1 = ax_hm.get_legend_handles_labels()
lines2, labels2 = ax_hm2.get_legend_handles_labels()
ax_hm.legend(lines1 + lines2, labels1 + labels2, loc="lower right", fontsize=9)

ax_hm.grid(axis="x", alpha=0.15)
plt.tight_layout()
hm_path = save_dir / "spider_db_heatmap.png"
fig2.savefig(hm_path, dpi=150, bbox_inches="tight")
plt.close(fig2)
print(f"Heatmap saved: {hm_path}")

print("\nAll charts generated.")
