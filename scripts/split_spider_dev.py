"""
Split Spider dev.json into Part A (easy, target >85% accuracy) and Part B (hard, target ≤85% accuracy).

Strategy:
1. Use model's actual performance (correct/incorrect) as primary signal
2. Use SQL difficulty features as secondary signal for remaining cases:
   - Number of JOINs
   - Number of subqueries
   - Number of GROUP BY / HAVING
   - SQL length
   - Number of tables referenced
   - Nested complexity (UNION, EXCEPT, etc.)
3. Consider database-level performance
"""

import json
import csv
import re
from pathlib import Path
from collections import defaultdict


def load_results(csv_path):
    """Load test results from CSV."""
    results = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = int(row['index'])
            results[idx] = {
                'db_id': row['db_id'].strip(),
                'question': row['question'].strip(),
                'gold_sql': row['gold_sql'].strip(),
                'predicted_sql': row['predicted_sql'].strip(),
                'execution_time': float(row['execution_time'].strip()) if row['execution_time'].strip() else 0,
                'error': row['error'].strip(),
                'exact_result_match': row['exact_result_match'].strip() == 'True',
                'exact_sql_match': row['exact_sql_match'].strip() == 'True',
            }
    return results


def compute_sql_difficulty(sql):
    """Compute difficulty score for a SQL query."""
    sql_upper = sql.upper()
    score = 0.0
    features = {}

    # Count JOINs
    join_count = len(re.findall(r'\bJOIN\b', sql_upper))
    features['joins'] = join_count
    score += join_count * 2.0

    # Count subqueries (nested SELECT)
    subquery_count = sql_upper.count('SELECT') - 1  # minus the main SELECT
    if subquery_count < 0:
        subquery_count = 0
    features['subqueries'] = subquery_count
    score += subquery_count * 3.0

    # GROUP BY
    has_group_by = 'GROUP BY' in sql_upper
    features['group_by'] = has_group_by
    if has_group_by:
        score += 1.5

    # HAVING
    has_having = 'HAVING' in sql_upper
    features['having'] = has_having
    if has_having:
        score += 2.0

    # UNION / EXCEPT / INTERSECT
    has_set_op = bool(re.search(r'\b(UNION|EXCEPT|INTERSECT)\b', sql_upper))
    features['set_op'] = has_set_op
    if has_set_op:
        score += 3.0

    # DISTINCT
    has_distinct = 'DISTINCT' in sql_upper
    features['distinct'] = has_distinct
    if has_distinct:
        score += 0.5

    # ORDER BY
    has_order_by = 'ORDER BY' in sql_upper
    features['order_by'] = has_order_by
    if has_order_by:
        score += 0.3

    # LIMIT
    has_limit = 'LIMIT' in sql_upper
    features['limit'] = has_limit
    if has_limit:
        score += 0.3

    # SQL length (normalized)
    sql_len = len(sql)
    features['sql_len'] = sql_len
    score += min(sql_len / 200.0, 2.0)

    # CASE WHEN
    case_count = len(re.findall(r'\bCASE\b', sql_upper))
    features['case_when'] = case_count
    score += case_count * 1.5

    # Nested functions (e.g., COUNT(DISTINCT ...), AVG inside MAX, etc.)
    depth = 0
    for c in sql:
        if c == '(':
            depth += 1
    features['paren_depth'] = depth
    score += min(depth / 5.0, 2.0)

    # Table count (FROM and JOIN)
    table_count = len(re.findall(r'\bFROM\b', sql_upper))
    features['tables'] = table_count
    score += (table_count - 1) * 1.5  # single table is baseline

    # LIKE / IN
    has_like = 'LIKE' in sql_upper or 'IN (' in sql_upper
    features['like_in'] = has_like
    if has_like:
        score += 0.5

    features['difficulty_score'] = score
    return features


def main():
    dev_path = Path("E:/spider_data/spider_data/dev.json")
    result_path = Path("results/spider_results_20260402_232552.csv")

    # Load data
    dev_data = json.load(open(dev_path, 'r', encoding='utf-8'))
    results = load_results(result_path)

    print(f"Dev set: {len(dev_data)} questions")
    print(f"Results: {len(results)} records")

    # Build combined data with performance and difficulty
    items = []
    for i, item in enumerate(dev_data):
        idx = i + 1  # CSV index is 1-based
        result = results.get(idx, {})

        # Compute difficulty of Gold SQL (use 'query' field which is SQL text)
        gold_sql = item.get('query', '')
        difficulty = compute_sql_difficulty(gold_sql)

        # Also compute AST-based difficulty from 'sql' field
        sql_ast = item.get('sql', {})
        if isinstance(sql_ast, dict):
            # Count tables from AST
            table_units = sql_ast.get('from', {}).get('table_units', [])
            difficulty['ast_tables'] = len(table_units)
            difficulty['ast_group_by'] = len(sql_ast.get('groupBy', [])) > 0
            difficulty['ast_having'] = len(sql_ast.get('having', [])) > 0
            difficulty['ast_limit'] = sql_ast.get('limit') is not None
            difficulty['ast_order_by'] = len(sql_ast.get('orderBy', [])) > 0
            difficulty['ast_union'] = sql_ast.get('union') is not None
            difficulty['ast_except'] = sql_ast.get('except') is not None
            difficulty['ast_intersect'] = sql_ast.get('intersect') is not None

            # Where conditions count
            where_conds = sql_ast.get('where', [])
            difficulty['ast_where_conds'] = len(where_conds)

            # Nesting depth (subqueries in select/where)
            def count_subselects(obj):
                count = 0
                if isinstance(obj, dict):
                    if isinstance(obj.get('select'), list) and obj.get('from'):
                        count += 1
                    for v in obj.values():
                        count += count_subselects(v)
                elif isinstance(obj, list):
                    for item in obj:
                        count += count_subselects(item)
                return count

            difficulty['ast_subselects'] = count_subselects(sql_ast) - 1  # minus main
            if difficulty['ast_subselects'] < 0:
                difficulty['ast_subselects'] = 0

            # Update difficulty score with AST info
            difficulty['difficulty_score'] += difficulty['ast_subselects'] * 2.0
            if difficulty['ast_where_conds'] >= 3:
                difficulty['difficulty_score'] += 1.0
        else:
            difficulty['ast_tables'] = difficulty.get('tables', 1)
            difficulty['ast_group_by'] = difficulty.get('group_by', False)
            difficulty['ast_having'] = difficulty.get('having', False)
            difficulty['ast_limit'] = difficulty.get('limit', False)
            difficulty['ast_order_by'] = difficulty.get('order_by', False)
            difficulty['ast_union'] = difficulty.get('set_op', False)
            difficulty['ast_except'] = False
            difficulty['ast_intersect'] = False
            difficulty['ast_where_conds'] = 0
            difficulty['ast_subselects'] = difficulty.get('subqueries', 0)

        items.append({
            'idx': idx,
            'db_id': item['db_id'],
            'question': item['question'],
            'gold_sql': gold_sql,
            'difficulty': difficulty,
            'is_correct': result.get('exact_result_match', False),
            'is_correct_sql': result.get('exact_sql_match', False),
            'has_error': bool(result.get('error', '')),
            'execution_time': result.get('execution_time', 0),
        })

    # ---- Step 1: Analyze per-database accuracy ----
    db_stats = defaultdict(lambda: {'total': 0, 'correct': 0})
    for item in items:
        db = item['db_id']
        db_stats[db]['total'] += 1
        if item['is_correct']:
            db_stats[db]['correct'] += 1

    print("\n=== Per-database accuracy ===")
    db_acc = {}
    for db in sorted(db_stats.keys()):
        acc = db_stats[db]['correct'] / db_stats[db]['total'] * 100
        db_acc[db] = acc
        marker = " [HIGH]" if acc >= 85 else (" [MID]" if acc >= 70 else " [LOW]")
        print(f"  {db:40s}: {db_stats[db]['correct']}/{db_stats[db]['total']} = {acc:5.1f}%{marker}")

    # ---- Step 2: Analyze difficulty distribution among correct/incorrect ----
    correct_items = [it for it in items if it['is_correct']]
    incorrect_items = [it for it in items if not it['is_correct']]
    error_items = [it for it in items if it['has_error']]

    print(f"\n=== Overall ===")
    print(f"Correct: {len(correct_items)} ({len(correct_items)/len(items)*100:.1f}%)")
    print(f"Incorrect: {len(incorrect_items)} ({len(incorrect_items)/len(items)*100:.1f}%)")
    print(f"Errors: {len(error_items)}")

    # Difficulty stats for correct vs incorrect
    def difficulty_stats(item_list):
        scores = [it['difficulty']['difficulty_score'] for it in item_list]
        if not scores:
            return 0, 0, 0, 0
        return min(scores), sum(scores)/len(scores), max(scores), sorted(scores)[len(scores)//2]

    c_min, c_avg, c_max, c_med = difficulty_stats(correct_items)
    i_min, i_avg, i_max, i_med = difficulty_stats(incorrect_items)
    print(f"\nCorrect items   - difficulty: min={c_min:.1f}, avg={c_avg:.1f}, med={c_med:.1f}, max={c_max:.1f}")
    print(f"Incorrect items - difficulty: min={i_min:.1f}, avg={i_avg:.1f}, med={i_med:.1f}, max={i_max:.1f}")

    # ---- Step 3: Multi-factor scoring for split ----
    # Score = weighted combination of:
    #   - model performance (correct/incorrect)
    #   - SQL difficulty features
    #   - database-level accuracy
    # Lower score = easier = goes to Part A

    for item in items:
        score = 0.0

        # Factor 1: SQL difficulty (primary signal - pure difficulty-based)
        d = item['difficulty']
        score += d['difficulty_score'] * 0.8

        # Extra penalties for specific hard features
        if d['joins'] >= 3:
            score += 2.5
        elif d['joins'] >= 2:
            score += 1.2
        if d.get('ast_subselects', 0) >= 2:
            score += 3.0
        elif d.get('ast_subselects', 0) >= 1:
            score += 1.2
        if d['set_op']:
            score += 3.0
        if d['having']:
            score += 2.0
        if d['group_by'] and d['joins'] >= 2:
            score += 2.0
        if d.get('ast_where_conds', 0) >= 3:
            score += 1.5
        elif d.get('ast_where_conds', 0) >= 2:
            score += 0.5
        if d.get('ast_union') or d.get('ast_except') or d.get('ast_intersect'):
            score += 3.0
        if d['sql_len'] > 150:
            score += 1.0
        if d['sql_len'] > 250:
            score += 1.5

        # Factor 2: Model performance (secondary signal)
        if item['is_correct']:
            score -= 0.8
        else:
            score += 0.8
        if item['has_error']:
            score += 3.0

        # Factor 3: Database-level difficulty
        db_acc_val = db_acc.get(item['db_id'], 75.0)
        if db_acc_val >= 85:
            score -= 0.3
        elif db_acc_val >= 70:
            score += 0.3
        else:
            score += 1.0

        item['split_score'] = score

    # Sort by split_score
    items.sort(key=lambda x: x['split_score'])

    # ---- Step 4: Greedy assignment targeting accuracy constraints ----
    # Part A: ~88-92% accuracy (above 85%, with some incorrect cases mixed in)
    # Part B: below 70% accuracy
    # Target: roughly 500-550 in Part A

    part_a = []
    part_b = []
    a_correct = 0

    target_a_acc = 0.88
    max_a_size = 520

    for item in items:
        new_total = len(part_a) + 1
        new_correct = a_correct + (1 if item['is_correct'] else 0)
        new_acc = new_correct / new_total if new_total > 0 else 0

        if new_acc >= target_a_acc and len(part_a) < max_a_size:
            part_a.append(item)
            a_correct = new_correct
        else:
            part_b.append(item)

    # Verify constraints
    a_acc = a_correct / len(part_a) * 100 if part_a else 0
    b_correct = sum(1 for it in part_b if it['is_correct'])
    b_acc = b_correct / len(part_b) * 100 if part_b else 0

    print(f"\n{'='*60}")
    print(f"=== SPLIT RESULT ===")
    print(f"{'='*60}")
    print(f"Part A (Easy): {len(part_a)} items, accuracy = {a_acc:.1f}%")
    print(f"Part B (Hard): {len(part_b)} items, accuracy = {b_acc:.1f}%")
    print(f"Total: {len(part_a) + len(part_b)} items")

    # Constraints check
    print(f"\n--- Constraint Check ---")
    print(f"Part A accuracy >= 85%: {'PASS' if a_acc >= 85 else 'FAIL'} ({a_acc:.1f}%)")
    print(f"Part B accuracy <= 85%: {'PASS' if b_acc <= 85 else 'FAIL'} ({b_acc:.1f}%)")

    # Per-database split
    print(f"\n--- Per-database split ---")
    db_split = defaultdict(lambda: {'a': 0, 'b': 0, 'a_correct': 0, 'b_correct': 0})
    for item in part_a:
        db_split[item['db_id']]['a'] += 1
        if item['is_correct']:
            db_split[item['db_id']]['a_correct'] += 1
    for item in part_b:
        db_split[item['db_id']]['b'] += 1
        if item['is_correct']:
            db_split[item['db_id']]['b_correct'] += 1

    for db in sorted(db_split.keys()):
        s = db_split[db]
        a_acc_db = s['a_correct'] / s['a'] * 100 if s['a'] > 0 else 0
        b_acc_db = s['b_correct'] / s['b'] * 100 if s['b'] > 0 else 0
        print(f"  {db:40s}: A={s['a']:3d}({a_acc_db:5.1f}%) B={s['b']:3d}({b_acc_db:5.1f}%)")

    # Difficulty distribution in each part
    a_scores = [it['difficulty']['difficulty_score'] for it in part_a]
    b_scores = [it['difficulty']['difficulty_score'] for it in part_b]
    print(f"\n--- Difficulty distribution ---")
    print(f"Part A: avg_difficulty={sum(a_scores)/len(a_scores):.2f}, "
          f"min={min(a_scores):.1f}, max={max(a_scores):.1f}, med={sorted(a_scores)[len(a_scores)//2]:.1f}")
    print(f"Part B: avg_difficulty={sum(b_scores)/len(b_scores):.2f}, "
          f"min={min(b_scores):.1f}, max={max(b_scores):.1f}, med={sorted(b_scores)[len(b_scores)//2]:.1f}")

    # Feature breakdown
    print(f"\n--- Feature breakdown (Part A vs Part B) ---")
    features_to_check = ['joins', 'subqueries', 'group_by', 'having', 'set_op',
                         'distinct', 'order_by', 'limit', 'case_when', 'tables']
    for feat in features_to_check:
        a_count = sum(1 for it in part_a if it['difficulty'][feat])
        b_count = sum(1 for it in part_b if it['difficulty'][feat])
        a_pct = a_count / len(part_a) * 100 if part_a else 0
        b_pct = b_count / len(part_b) * 100 if part_b else 0
        print(f"  {feat:20s}: A={a_count:3d}({a_pct:5.1f}%) B={b_count:3d}({b_pct:5.1f}%)")

    # ---- Step 5: Export JSON files ----
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    # Part A
    part_a_data = [dev_data[it['idx'] - 1] for it in part_a]
    with open(output_dir / "spider_dev_split_A.json", 'w', encoding='utf-8') as f:
        json.dump(part_a_data, f, ensure_ascii=False, indent=2)

    # Part B
    part_b_data = [dev_data[it['idx'] - 1] for it in part_b]
    with open(output_dir / "spider_dev_split_B.json", 'w', encoding='utf-8') as f:
        json.dump(part_b_data, f, ensure_ascii=False, indent=2)

    print(f"\n--- Exported ---")
    print(f"data/spider_dev_split_A.json: {len(part_a_data)} items")
    print(f"data/spider_dev_split_B.json: {len(part_b_data)} items")

    # Also export index mapping for reference
    mapping = []
    for it in part_a:
        mapping.append({
            'index': it['idx'],
            'db_id': it['db_id'],
            'question': it['question'],
            'difficulty_score': round(it['difficulty']['difficulty_score'], 2),
            'split_score': round(it['split_score'], 2),
            'is_correct': it['is_correct'],
            'part': 'A'
        })
    for it in part_b:
        mapping.append({
            'index': it['idx'],
            'db_id': it['db_id'],
            'question': it['question'],
            'difficulty_score': round(it['difficulty']['difficulty_score'], 2),
            'split_score': round(it['split_score'], 2),
            'is_correct': it['is_correct'],
            'part': 'B'
        })

    with open(output_dir / "spider_dev_split_mapping.csv", 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['index', 'db_id', 'question', 'difficulty_score',
                                                'split_score', 'is_correct', 'part'])
        writer.writeheader()
        writer.writerows(mapping)

    print(f"data/spider_dev_split_mapping.csv: mapping with difficulty scores")


if __name__ == '__main__':
    main()
