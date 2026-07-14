"""批量测试 query_preprocessor.py 的解析效果。

用法：
    python test_preprocessor.py              # 运行所有用例
    python test_preprocessor.py 信号         # 只测含"信号"的用例
"""

from __future__ import annotations

import sys
from services.query_preprocessor import preprocess_chart_query


# ============================================================
# 测试用例
# ============================================================

TEST_CASES = [
    # ---- 图表类型 ----
    ("生成柱状图", "bar"),
    ("折线图看趋势", "line"),
    ("饼图展示占比", "pie"),
    ("雷达图对比", "radar"),
    ("散点图分布", "point"),
    ("面积图累积", "area"),

    # ---- 时间范围 ----
    ("从2025-08-29~09-11每天的报警数量", "2025-08-29 ~ 2025-09-11"),
    ("最近一周的报警趋势", "近一周"),
    ("最近30天各规则报警情况", "近30天"),
    ("本月各车型报警次数", "本月"),

    # ---- 行维度 ----
    ("各车型报警次数", "车型"),
    ("各任务按规则分组", "任务名称、规则名称"),
    ("每天统计", "报警日期"),

    # ---- 图例 ----
    ("用规则做图例", "规则名称"),
    ("按车型分组", "车型"),

    # ---- 指标 ----
    ("报警次数", "报警次数, count"),
    ("平均时长", "平均时长, avg"),
    ("最长时间", "最长时间, max"),
    ("最短时间", "最短时间, min"),

    # ---- 横轴/纵轴 ----
    ("横轴为车型，纵轴为报警次数", "车型 / 报警次数"),
    ("以日期为横轴，数量为纵轴", "报警日期 / 数量"),
    ("x轴是时间，y轴是数量", "时间 / 数量"),

    # ---- 信号括号 ----
    ("信号[Hev,Hds]", "Hev, Hds"),
    ("信号【Hev】", "Hev"),
    ('信号"Hev，Hds"', "Hev, Hds"),
    ("信号（Hev）", "Hev"),
    ("横轴信号[ABC,XYZ]", "ABC, XYZ"),
    ("用信号[A,B]做图例", "A, B (legend)"),

    # ---- 完整组合 ----
    ("统计在任务[ND EREV 工程车基本工作信息_5377_1]中，从2025-08-29~09-11每天的报警数量，用规则做图例, 生成柱状图", "完整组合"),
    ("信号[温度,湿度,压力] 统计最近30天的数据 生成折线图", "多信号+时间+图表类型"),
]


def describe(pq) -> str:
    """格式化描述解析结果"""
    parts = []
    if pq.explicit_chart_type:
        parts.append(f"type={pq.explicit_chart_type}")
    if pq.time_range:
        parts.append(f"time={pq.time_range['start']}~{pq.time_range['end']}")
    if pq.group_by_fields:
        parts.append(f"axes=[{', '.join(pq.group_by_fields)}]")
    if pq.legend_field:
        parts.append(f"legend={pq.legend_field}")
    if pq.metrics:
        metrics_str = ", ".join(f"{m['label']}({m['aggregation']})" for m in pq.metrics)
        parts.append(f"metrics=[{metrics_str}]")
    if pq.task_ref:
        parts.append(f"task={pq.task_ref[:30]}...")
    return " | ".join(parts) if parts else "(empty)"


def main():
    filter_kw = sys.argv[1].lower() if len(sys.argv) > 1 else None

    passed = 0
    failed = 0
    total = len(TEST_CASES)

    for i, (input_text, expected) in enumerate(TEST_CASES, 1):
        if filter_kw and filter_kw not in input_text.lower():
            continue

        pq = preprocess_chart_query(input_text)
        result = describe(pq)
        status = "✅" if result != "(empty)" or pq.is_empty() == (expected == "") else "❌"

        if expected == "" and pq.is_empty():
            passed += 1
        elif expected != "" and not pq.is_empty():
            passed += 1
        else:
            failed += 1
            status = "❌"

        print(f"[{i:02d}/{total}] {status} {input_text[:50]:<50}")
        print(f"       → {result}")
        if status == "❌":
            print(f"       ✗ 期望: {expected}")
        print()

    print("=" * 60)
    print(f"总计: {total} 用例 | ✅ 通过: {passed} | ❌ 失败: {failed}")
    if failed == 0:
        print("全部通过！")


if __name__ == "__main__":
    main()
