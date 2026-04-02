"""
分析Spider benchmark的错误案例
"""
import csv
from collections import defaultdict, Counter
import re

def analyze_error_cases(csv_file):
    # 读取CSV文件
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"总错误案例数: {len(rows)}\n")

    # 1. 统计失败原因分布
    print("=" * 80)
    print("1. 失败原因统计")
    print("=" * 80)
    failure_reasons = Counter()
    for row in rows:
        reason = row.get('失败原因', '未知')
        if reason.strip():
            failure_reasons[reason] += 1

    for reason, count in failure_reasons.most_common():
        percentage = (count / len(rows)) * 100
        print(f"{reason}: {count} ({percentage:.1f}%)")

    # 2. 统计数据库分布
    print("\n" + "=" * 80)
    print("2. 错误案例最多的数据库")
    print("=" * 80)
    db_errors = Counter()
    for row in rows:
        db = row.get('数据库', '未知')
        db_errors[db] += 1

    for db, count in db_errors.most_common(15):
        print(f"{db}: {count}")

    # 3. 大数据库专门分析
    print("\n" + "=" * 80)
    print("3. 大数据库专门分析 (car_1, world_1, student_transcripts_tracking)")
    print("=" * 80)

    large_dbs = ['car_1', 'world_1', 'student_transcripts_tracking']

    for target_db in large_dbs:
        db_rows = [r for r in rows if r.get('数据库') == target_db]
        print(f"\n--- {target_db} ({len(db_rows)} 个错误) ---")

        # 统计该数据库的失败原因
        db_reasons = Counter()
        for row in db_rows:
            reason = row.get('失败原因', '未知')
            if reason.strip():
                db_reasons[reason] += 1

        print("失败原因分布:")
        for reason, count in db_reasons.most_common():
            print(f"  {reason}: {count}")

    # 4. 每个失败原因的典型示例
    print("\n" + "=" * 80)
    print("4. 典型错误案例示例（每个类别3个）")
    print("=" * 80)

    for reason, _ in failure_reasons.most_common(10):
        reason_rows = [r for r in rows if r.get('失败原因', '').strip() == reason]
        if not reason_rows:
            continue

        print(f"\n【{reason}】(共{len(reason_rows)}个)")
        for i, row in enumerate(reason_rows[:3], 1):
            print(f"\n--- 示例 {i} ---")
            print(f"数据库: {row.get('数据库', 'N/A')}")
            print(f"问题: {row.get('问题', 'N/A')[:100]}...")
            print(f"\nGold SQL:")
            print(row.get('Gold SQL', 'N/A')[:200])
            print(f"\n预测 SQL:")
            print(row.get('预测 SQL', 'N/A')[:200])
            print(f"\n正确执行结果:")
            print(row.get('正确执行结果', 'N/A')[:150])
            print(f"\n实际执行结果:")
            print(row.get('实际执行结果', 'N/A')[:150])
            print(f"耗时: {row.get('耗时(s)', 'N/A')}s")
            if row.get('错误信息', '').strip():
                print(f"错误信息: {row.get('错误信息', 'N/A')}")

    # 5. 分析额外输出列的问题
    print("\n" + "=" * 80)
    print("5. 额外输出列问题分析")
    print("=" * 80)
    extra_col_rows = [r for r in rows if r.get('失败原因', '').strip() == '额外输出列']
    print(f"额外输出列错误总数: {len(extra_col_rows)}")

    # 统计是否有规律
    has_select_star = 0
    has_join = 0
    for row in extra_col_rows:
        pred_sql = row.get('预测 SQL', '').upper()
        if 'SELECT *' in pred_sql or 'SELECT*' in pred_sql:
            has_select_star += 1
        if 'JOIN' in pred_sql:
            has_join += 1

    print(f"使用 SELECT * 的: {has_select_star}")
    print(f"使用 JOIN 的: {has_join}")

    # 6. 分析JOIN相关错误
    print("\n" + "=" * 80)
    print("6. JOIN相关错误分析")
    print("=" * 80)
    join_errors = []
    for row in rows:
        reason = row.get('失败原因', '')
        pred_sql = row.get('预测 SQL', '').upper()
        gold_sql = row.get('Gold SQL', '').upper()

        if 'JOIN' in pred_sql or 'JOIN' in gold_sql:
            join_errors.append({
                'db': row.get('数据库', ''),
                'reason': reason,
                'gold_has_join': 'JOIN' in gold_sql,
                'pred_has_join': 'JOIN' in pred_sql,
                'question': row.get('问题', '')[:80]
            })

    print(f"涉及JOIN的错误: {len(join_errors)}")

    # 统计 JOIN 相关的失败原因
    join_reason_counter = Counter()
    for err in join_errors:
        join_reason_counter[err['reason']] += 1

    print("\nJOIN相关错误的原因分布:")
    for reason, count in join_reason_counter.most_common():
        print(f"  {reason}: {count}")

    # 7. 统计 LIMIT 使用情况
    print("\n" + "=" * 80)
    print("7. LIMIT 使用分析")
    print("=" * 80)

    with_limit = [r for r in rows if 'LIMIT' in r.get('预测 SQL', '').upper()]
    gold_with_limit = [r for r in rows if 'LIMIT' in r.get('Gold SQL', '').upper()]

    print(f"预测SQL使用LIMIT的: {len(with_limit)} ({len(with_limit)/len(rows)*100:.1f}%)")
    print(f"Gold SQL使用LIMIT的: {len(gold_with_limit)} ({len(gold_with_limit)/len(rows)*100:.1f}%)")

    # 统计预测使用了LIMIT但Gold没有的
    excess_limit = [r for r in rows if 'LIMIT' in r.get('预测 SQL', '').upper()
                    and 'LIMIT' not in r.get('Gold SQL', '').upper()]
    print(f"预测使用了LIMIT但Gold没有的: {len(excess_limit)}")

    # 8. 聚合函数分析
    print("\n" + "=" * 80)
    print("8. 聚合函数分析")
    print("=" * 80)

    aggregate_funcs = ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN']

    for func in aggregate_funcs:
        pred_has = [r for r in rows if func in r.get('预测 SQL', '').upper()]
        gold_has = [r for r in rows if func in r.get('Gold SQL', '').upper()]
        print(f"{func}: 预测{len(pred_has)}次, Gold{len(gold_has)}次")

    # 9. 列别名差异分析
    print("\n" + "=" * 80)
    print("9. 列别名差异分析")
    print("=" * 80)

    alias_diffs = [r for r in rows if r.get('失败原因', '').strip() == '列别名差异']
    print(f"列别名差异总数: {len(alias_diffs)}")

    # 统计预测SQL中有别名的比例
    pred_with_alias = 0
    for row in alias_diffs:
        pred_sql = row.get('预测 SQL', '')
        if ' AS ' in pred_sql.upper():
            pred_with_alias += 1

    print(f"预测SQL使用了别名的: {pred_with_alias} ({pred_with_alias/len(alias_diffs)*100:.1f}%)")

    # 10. 错误信息统计
    print("\n" + "=" * 80)
    print("10. 错误信息统计")
    print("=" * 80)

    error_messages = Counter()
    for row in rows:
        err_msg = row.get('错误信息', '').strip()
        if err_msg:
            # 提取错误类型
            err_type = err_msg.split(':')[0] if ':' in err_msg else err_msg
            error_messages[err_type[:50]] += 1

    print("最常见的错误信息类型:")
    for err_type, count in error_messages.most_common(10):
        print(f"  {err_type}: {count}")

if __name__ == '__main__':
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    analyze_error_cases(r'D:\GraduationProject\results\spider_results_incorrect_only.csv')
