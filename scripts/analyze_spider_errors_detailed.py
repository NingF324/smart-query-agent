"""
深入分析Spider benchmark的错误案例
"""
import csv
from collections import defaultdict, Counter
import re

def analyze_logic_errors(csv_file):
    # 读取CSV文件
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("=" * 80)
    print("深入分析：逻辑错误案例详解")
    print("=" * 80)

    logic_rows = [r for r in rows if r.get('失败原因', '').strip() == '逻辑错误']
    print(f"逻辑错误总数: {len(logic_rows)}\n")

    # 分析逻辑错误的各种类型
    join_issues = 0
    where_clause_issues = 0
    column_value_issues = 0
    table_join_issues = 0

    for row in logic_rows:
        gold_sql = row.get('Gold SQL', '')
        pred_sql = row.get('预测 SQL', '')
        actual_result = row.get('实际执行结果', '')

        # 检测JOIN问题
        if 'JOIN' in gold_sql.upper() and 'JOIN' in pred_sql.upper():
            join_issues += 1

        # 检测WHERE条件问题
        if 'WHERE' in gold_sql.upper() and 'WHERE' in pred_sql.upper():
            where_clause_issues += 1

        # 检测结果为空的情况
        if '(empty)' in actual_result:
            column_value_issues += 1

    print("逻辑错误分类:")
    print(f"  - 涉及JOIN操作的: {join_issues}")
    print(f"  - 涉及WHERE条件的: {where_clause_issues}")
    print(f"  - 结果为空的: {column_value_issues}")

    # 详细的逻辑错误示例
    print("\n" + "=" * 80)
    print("逻辑错误详细案例（前10个）")
    print("=" * 80)

    for i, row in enumerate(logic_rows[:10], 1):
        print(f"\n--- 案例 {i} ---")
        print(f"数据库: {row.get('数据库', 'N/A')}")
        print(f"问题: {row.get('问题', 'N/A')}")
        print(f"\nGold SQL:")
        print(row.get('Gold SQL', 'N/A'))
        print(f"\n预测 SQL:")
        print(row.get('预测 SQL', 'N/A'))
        print(f"\n正确结果: {row.get('正确执行结果', 'N/A')[:150]}")
        print(f"实际结果: {row.get('实际执行结果', 'N/A')[:150]}")

def analyze_join_specific_issues(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("\n" + "=" * 80)
    print("JOIN操作深入分析")
    print("=" * 80)

    # 筛选涉及JOIN的错误
    join_errors = []
    for row in rows:
        pred_sql = row.get('预测 SQL', '')
        gold_sql = row.get('Gold SQL', '')
        if 'JOIN' in pred_sql.upper() or 'JOIN' in gold_sql.upper():
            join_errors.append(row)

    print(f"涉及JOIN的错误案例: {len(join_errors)}\n")

    # 分析JOIN类型
    inner_join_pred = sum(1 for r in join_errors if 'INNER JOIN' in r.get('预测 SQL', '').upper())
    left_join_pred = sum(1 for r in join_errors if 'LEFT JOIN' in r.get('预测 SQL', '').upper())
    inner_join_gold = sum(1 for r in join_errors if 'INNER JOIN' in r.get('Gold SQL', '').upper())
    left_join_gold = sum(1 for r in join_errors if 'LEFT JOIN' in r.get('Gold SQL', '').upper())

    print("JOIN类型统计:")
    print(f"预测SQL - INNER JOIN: {inner_join_pred}, LEFT JOIN: {left_join_pred}")
    print(f"Gold SQL - INNER JOIN: {inner_join_gold}, LEFT JOIN: {left_join_gold}")

    # 分析LEFT JOIN问题
    print("\n" + "=" * 80)
    print("LEFT JOIN 问题分析")
    print("=" * 80)

    # 预测用了LEFT JOIN但Gold用的是普通JOIN
    left_vs_normal = []
    for row in join_errors:
        pred_sql = row.get('预测 SQL', '').upper()
        gold_sql = row.get('Gold SQL', '').upper()
        if 'LEFT JOIN' in pred_sql and 'LEFT JOIN' not in gold_sql and 'JOIN' in gold_sql:
            left_vs_normal.append(row)

    print(f"预测使用LEFT JOIN但Gold使用普通JOIN的案例: {len(left_vs_normal)}")
    print(f"占所有JOIN错误的: {len(left_vs_normal)/len(join_errors)*100:.1f}%")

    if len(left_vs_normal) > 0:
        print("\n示例1:")
        print(f"数据库: {left_vs_normal[0].get('数据库', 'N/A')}")
        print(f"问题: {left_vs_normal[0].get('问题', 'N/A')}")
        print(f"\nGold SQL:")
        print(left_vs_normal[0].get('Gold SQL', 'N/A'))
        print(f"\n预测 SQL:")
        print(left_vs_normal[0].get('预测 SQL', 'N/A'))
        print(f"\n正确结果: {left_vs_normal[0].get('正确执行结果', 'N/A')[:200]}")
        print(f"实际结果: {left_vs_normal[0].get('实际执行结果', 'N/A')[:200]}")

    # 分析外键关系理解错误
    print("\n" + "=" * 80)
    print("外键/JOIN关系理解错误")
    print("=" * 80)

    foreign_key_errors = []
    for row in join_errors:
        actual_result = row.get('实际执行结果', '')
        gold_result = row.get('正确执行结果', '')

        # 检测结果差异很大（可能是JOIN条件错误）
        if '(empty)' in actual_result and gold_result and '(empty)' not in gold_result:
            foreign_key_errors.append(row)

    print(f"因JOIN条件导致结果为空的案例: {len(foreign_key_errors)}")

    if len(foreign_key_errors) > 0:
        print("\n示例:")
        print(f"数据库: {foreign_key_errors[0].get('数据库', 'N/A')}")
        print(f"问题: {foreign_key_errors[0].get('问题', 'N/A')}")
        print(f"\nGold SQL:")
        print(foreign_key_errors[0].get('Gold SQL', 'N/A'))
        print(f"\n预测 SQL:")
        print(foreign_key_errors[0].get('预测 SQL', 'N/A'))
        print(f"\n正确结果: {foreign_key_errors[0].get('正确执行结果', 'N/A')[:200]}")
        print(f"实际结果: {foreign_key_errors[0].get('实际执行结果', 'N/A')[:200]}")

def analyze_value_matching_issues(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("\n" + "=" * 80)
    print("值匹配问题分析")
    print("=" * 80)

    # 分析WHERE条件中的值匹配问题
    value_mismatch = []
    for row in rows:
        pred_sql = row.get('预测 SQL', '').upper()
        gold_sql = row.get('Gold SQL', '').upper()

        # 检测字面量差异
        pred_literals = re.findall(r"'([^']*)'|\"([^\"]*)\"", pred_sql)
        gold_literals = re.findall(r"'([^']*)'|\"([^\"]*)\"", gold_sql)

        pred_values = set([v[0] if v[0] else v[1] for v in pred_literals])
        gold_values = set([v[0] if v[0] else v[1] for v in gold_literals])

        if pred_values != gold_values and pred_values and gold_values:
            value_mismatch.append({
                'row': row,
                'pred_values': pred_values,
                'gold_values': gold_values
            })

    print(f"WHERE条件值不匹配的案例: {len(value_mismatch)}")

    if len(value_mismatch) > 0:
        print("\n示例:")
        row = value_mismatch[0]['row']
        print(f"数据库: {row.get('数据库', 'N/A')}")
        print(f"问题: {row.get('问题', 'N/A')}")
        print(f"\n预测SQL中的值: {value_mismatch[0]['pred_values']}")
        print(f"Gold SQL中的值: {value_mismatch[0]['gold_values']}")
        print(f"\nGold SQL:")
        print(row.get('Gold SQL', 'N/A'))
        print(f"\n预测 SQL:")
        print(row.get('预测 SQL', 'N/A'))
        print(f"\n正确结果: {row.get('正确执行结果', 'N/A')[:150]}")
        print(f"实际结果: {row.get('实际执行结果', 'N/A')[:150]}")

def analyze_column_ordering(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("\n" + "=" * 80)
    print("列顺序问题分析")
    print("=" * 80)

    # 分析列顺序问题
    column_order_issues = []
    for row in rows:
        reason = row.get('失败原因', '').strip()
        if 'ORDER BY' in reason or '列别名差异' in reason:
            column_order_issues.append(row)

    print(f"列顺序相关错误: {len(column_order_issues)}")

if __name__ == '__main__':
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    csv_file = r'D:\GraduationProject\results\spider_results_incorrect_only.csv'

    analyze_logic_errors(csv_file)
    analyze_join_specific_issues(csv_file)
    analyze_value_matching_issues(csv_file)
    analyze_column_ordering(csv_file)
