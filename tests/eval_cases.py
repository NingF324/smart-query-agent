"""Week7 端到端评测样例集。"""
from typing import Dict, List

from services.evaluation_service import EvaluationCase, SafetySqlCase


THIS_MONTH_ORDER_COUNT = "SELECT COUNT(*) AS count FROM orders WHERE EXTRACT(MONTH FROM order_date) = EXTRACT(MONTH FROM CURRENT_DATE)"
LAST_MONTH_ORDER_COUNT = "SELECT COUNT(*) AS count FROM orders WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND order_date < DATE_TRUNC('month', CURRENT_DATE)"
THIS_YEAR_ORDER_COUNT = "SELECT COUNT(*) AS count FROM orders WHERE EXTRACT(YEAR FROM order_date) = EXTRACT(YEAR FROM CURRENT_DATE)"
LAST_30_DAYS_ORDER_COUNT = "SELECT COUNT(*) AS count FROM orders WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'"
LAST_7_DAYS_ORDER_COUNT = "SELECT COUNT(*) AS count FROM orders WHERE order_date >= CURRENT_DATE - INTERVAL '7 days'"
USER_COUNT = "SELECT COUNT(*) AS count FROM users"
PRODUCT_COUNT = "SELECT COUNT(*) AS count FROM products"

CATEGORY_SALES_TOP_10 = """
SELECT p.category AS dimension, SUM(oi.quantity * oi.unit_price) AS total_sales
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN users u ON o.user_id = u.user_id
JOIN products p ON oi.product_id = p.product_id
GROUP BY p.category
ORDER BY total_sales DESC
LIMIT 10
""".strip()
CATEGORY_SALES_TOP_5 = CATEGORY_SALES_TOP_10.replace("LIMIT 10", "LIMIT 5")
CITY_SALES_TOP_10 = CATEGORY_SALES_TOP_10.replace("p.category AS dimension", "u.city AS dimension").replace("GROUP BY p.category", "GROUP BY u.city")
CITY_SALES_TOP_5 = CITY_SALES_TOP_10.replace("LIMIT 10", "LIMIT 5")
PRODUCT_RATING_TOP_10 = """
SELECT p.product_name, AVG(r.rating) AS avg_rating
FROM reviews r
JOIN products p ON r.product_id = p.product_id
GROUP BY p.product_id, p.product_name
HAVING COUNT(*) >= 5
ORDER BY avg_rating DESC
LIMIT 10
""".strip()
PRODUCT_RATING_TOP_5 = PRODUCT_RATING_TOP_10.replace("LIMIT 10", "LIMIT 5")
USER_CITY_DISTRIBUTION = """
SELECT city, COUNT(*) AS user_count
FROM users
GROUP BY city
ORDER BY user_count DESC
LIMIT 10
""".strip()
PRODUCT_CATEGORY_DISTRIBUTION = """
SELECT category, COUNT(*) AS product_count
FROM products
GROUP BY category
ORDER BY product_count DESC
LIMIT 10
""".strip()
ORDER_TREND = """
SELECT DATE(order_date) AS order_day, AVG(total_amount) AS avg_amount
FROM orders
GROUP BY DATE(order_date)
ORDER BY order_day
LIMIT 30
""".strip()


COUNT_CASES = [
    ("count_01", "本月订单总数是多少？", THIS_MONTH_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_02", "这个月有多少订单？", THIS_MONTH_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_03", "统计本月订单数量", THIS_MONTH_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_04", "上个月订单总数是多少？", LAST_MONTH_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_05", "上月有多少订单？", LAST_MONTH_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_06", "今年订单总数是多少？", THIS_YEAR_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_07", "今年一共下了多少订单？", THIS_YEAR_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_08", "最近30天订单数量是多少？", LAST_30_DAYS_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_09", "近30天订单总数", LAST_30_DAYS_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_10", "最近7天订单数量是多少？", LAST_7_DAYS_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_11", "近7天有多少订单？", LAST_7_DAYS_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_12", "用户总数是多少？", USER_COUNT, ["count", "users"]),
    ("count_13", "一共有多少用户？", USER_COUNT, ["count", "users"]),
    ("count_14", "产品总数是多少？", PRODUCT_COUNT, ["count", "products"]),
    ("count_15", "一共有多少产品？", PRODUCT_COUNT, ["count", "products"]),
    ("count_16", "本月订单一共多少单？", THIS_MONTH_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_17", "最近30天一共多少订单？", LAST_30_DAYS_ORDER_COUNT, ["count", "orders", "time"]),
    ("count_18", "最近7天一共多少订单？", LAST_7_DAYS_ORDER_COUNT, ["count", "orders", "time"]),
]

RANKING_CASES = [
    ("rank_01", "各品类销售额排行", CATEGORY_SALES_TOP_10, ["ranking", "sales", "category"]),
    ("rank_02", "各品类销售额前5名", CATEGORY_SALES_TOP_5, ["ranking", "sales", "category"]),
    ("rank_03", "各城市销售额排行", CITY_SALES_TOP_10, ["ranking", "sales", "city"]),
    ("rank_04", "各城市销售额前5名", CITY_SALES_TOP_5, ["ranking", "sales", "city"]),
    ("rank_05", "评分最高的产品排行", PRODUCT_RATING_TOP_10, ["ranking", "rating", "product"]),
    ("rank_06", "评分最高的前5个产品", PRODUCT_RATING_TOP_5, ["ranking", "rating", "product"]),
    ("rank_07", "Top 10 城市销售额排行", CITY_SALES_TOP_10, ["ranking", "sales", "city"]),
    ("rank_08", "Top 5 品类销售额排行", CATEGORY_SALES_TOP_5, ["ranking", "sales", "category"]),
    ("rank_09", "产品评分 Top 10", PRODUCT_RATING_TOP_10, ["ranking", "rating", "product"]),
    ("rank_10", "产品评分前5名", PRODUCT_RATING_TOP_5, ["ranking", "rating", "product"]),
    ("rank_11", "销售额按城市排行", CITY_SALES_TOP_10, ["ranking", "sales", "city"]),
    ("rank_12", "销售额按品类排行", CATEGORY_SALES_TOP_10, ["ranking", "sales", "category"]),
    ("rank_13", "各城市销售额Top 5", CITY_SALES_TOP_5, ["ranking", "sales", "city"]),
    ("rank_14", "各品类销售额Top 10", CATEGORY_SALES_TOP_10, ["ranking", "sales", "category"]),
]

DISTRIBUTION_CASES = [
    ("dist_01", "用户城市分布", USER_CITY_DISTRIBUTION, ["distribution", "users", "city"]),
    ("dist_02", "各城市用户分布", USER_CITY_DISTRIBUTION, ["distribution", "users", "city"]),
    ("dist_03", "用户按城市分布", USER_CITY_DISTRIBUTION, ["distribution", "users", "city"]),
    ("dist_04", "产品品类分布", PRODUCT_CATEGORY_DISTRIBUTION, ["distribution", "products", "category"]),
    ("dist_05", "各品类产品分布", PRODUCT_CATEGORY_DISTRIBUTION, ["distribution", "products", "category"]),
    ("dist_06", "产品按品类分布", PRODUCT_CATEGORY_DISTRIBUTION, ["distribution", "products", "category"]),
    ("dist_07", "城市用户占比", USER_CITY_DISTRIBUTION, ["distribution", "users", "city"]),
    ("dist_08", "品类产品占比", PRODUCT_CATEGORY_DISTRIBUTION, ["distribution", "products", "category"]),
    ("dist_09", "用户城市分布前10", USER_CITY_DISTRIBUTION, ["distribution", "users", "city"]),
    ("dist_10", "产品品类分布前10", PRODUCT_CATEGORY_DISTRIBUTION, ["distribution", "products", "category"]),
]

TREND_CASES = [
    ("trend_01", "订单金额趋势如何？", ORDER_TREND, ["trend", "orders"]),
    ("trend_02", "最近订单变化趋势", ORDER_TREND, ["trend", "orders"]),
    ("trend_03", "订单平均金额趋势", ORDER_TREND, ["trend", "orders"]),
    ("trend_04", "订单趋势怎么看？", ORDER_TREND, ["trend", "orders"]),
    ("trend_05", "订单增长趋势", ORDER_TREND, ["trend", "orders"]),
    ("trend_06", "订单变化情况", ORDER_TREND, ["trend", "orders"]),
]

FOLLOW_UP_CASES = [
    ("follow_01", "那上个月呢？", LAST_MONTH_ORDER_COUNT, [{"role": "user", "content": "本月订单总数是多少？"}], ["follow_up", "count", "orders"]),
    ("follow_02", "那今年呢？", THIS_YEAR_ORDER_COUNT, [{"role": "user", "content": "本月订单总数是多少？"}], ["follow_up", "count", "orders"]),
    ("follow_03", "那最近30天呢？", LAST_30_DAYS_ORDER_COUNT, [{"role": "user", "content": "本月订单总数是多少？"}], ["follow_up", "count", "orders"]),
    ("follow_04", "那最近7天呢？", LAST_7_DAYS_ORDER_COUNT, [{"role": "user", "content": "本月订单总数是多少？"}], ["follow_up", "count", "orders"]),
    ("follow_05", "只看前5个", CATEGORY_SALES_TOP_5, [{"role": "user", "content": "各品类销售额排行"}], ["follow_up", "ranking", "sales"]),
    ("follow_06", "按城市统计", CITY_SALES_TOP_10, [{"role": "user", "content": "各品类销售额排行"}], ["follow_up", "ranking", "sales"]),
    ("follow_07", "那前5名呢？", PRODUCT_RATING_TOP_5, [{"role": "user", "content": "评分最高的产品排行"}], ["follow_up", "ranking", "rating"]),
    ("follow_08", "只看前5个", CITY_SALES_TOP_5, [{"role": "user", "content": "各城市销售额排行"}], ["follow_up", "ranking", "sales"]),
]

SAFETY_SQL_CASES = [
    SafetySqlCase(case_id="safety_01", sql="SELECT * FROM users; DROP TABLE users", expected_reason="分号", tags=["safety", "injection"]),
    SafetySqlCase(case_id="safety_02", sql="DROP TABLE users", expected_reason="只允许 SELECT", tags=["safety", "ddl"]),
    SafetySqlCase(case_id="safety_03", sql="UPDATE users SET username = 'hack'", expected_reason="update", tags=["safety", "dml"]),
    SafetySqlCase(case_id="safety_04", sql="INSERT INTO users(username) VALUES ('hack')", expected_reason="insert", tags=["safety", "dml"]),
    SafetySqlCase(case_id="safety_05", sql="SELECT * FROM users -- comment", expected_reason="注释", tags=["safety", "comment"]),
    SafetySqlCase(case_id="safety_06", sql="SELECT * FROM users /* hack */", expected_reason="注释", tags=["safety", "comment"]),
    SafetySqlCase(case_id="safety_07", sql="ALTER TABLE users ADD COLUMN hacked INT", expected_reason="alter", tags=["safety", "ddl"]),
    SafetySqlCase(case_id="safety_08", sql="GRANT ALL PRIVILEGES ON users TO public", expected_reason="grant", tags=["safety", "permission"]),
]


def _build_case(case_id: str, question: str, expected_sql: str, tags: List[str], chat_history: List[Dict[str, str]] | None = None) -> EvaluationCase:
    return EvaluationCase(
        case_id=case_id,
        question=question,
        expected_sql=expected_sql,
        expected_result_sql=expected_sql,
        chat_history=chat_history or [],
        tags=tags,
    )


def get_week7_eval_cases() -> List[EvaluationCase]:
    """返回 50+ 端到端评测样例。"""
    cases: List[EvaluationCase] = []

    for case_id, question, expected_sql, tags in COUNT_CASES:
        cases.append(_build_case(case_id, question, expected_sql, tags))

    for case_id, question, expected_sql, tags in RANKING_CASES:
        cases.append(_build_case(case_id, question, expected_sql, tags))

    for case_id, question, expected_sql, tags in DISTRIBUTION_CASES:
        cases.append(_build_case(case_id, question, expected_sql, tags))

    for case_id, question, expected_sql, tags in TREND_CASES:
        cases.append(_build_case(case_id, question, expected_sql, tags))

    for case_id, question, expected_sql, chat_history, tags in FOLLOW_UP_CASES:
        cases.append(_build_case(case_id, question, expected_sql, tags, chat_history=chat_history))

    return cases


def get_week7_smoke_cases() -> List[EvaluationCase]:
    """返回适合快速回归的子集。"""
    target_ids = {
        "count_01",
        "count_04",
        "rank_01",
        "rank_03",
        "dist_01",
        "trend_01",
        "follow_01",
        "follow_05",
        "follow_06",
        "follow_07",
    }
    return [case for case in get_week7_eval_cases() if case.case_id in target_ids]


def get_week7_safety_sql_cases() -> List[SafetySqlCase]:
    """返回 SQL 安全拦截专项样例。"""
    return list(SAFETY_SQL_CASES)
