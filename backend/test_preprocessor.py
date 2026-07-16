"""批量测试 query_preprocessor.py 的解析效果。

用法：
    python test_preprocessor.py              # 运行所有用例
    python test_preprocessor.py 信号         # 只测含"信号"的用例
"""

from __future__ import annotations

from services.query_preprocessor import preprocess_chart_query


# ============================================================
# 测试用例
# ============================================================

TEST_CASES = [
    "生成雷达图，对比维度包括[平均值，最大值，最小值]，统计信号[VehSpdAvgDrvn_1,LIB1StatOfChrg,LIB1CellMinVltg,EngActStdyStTorq,VehOdo]的报警值，不要指定图例，关联任务：ND EREV 工程车基本工作信息_5377_1，数据筛选时间从2025-08-29 00:00:00 到 2025-09-04 23:59:59",
    "生成散点图，统计横轴信号[VehSpdAvgDrvn_1]与纵轴信号[HVBSOC_BatSOC]的报警值做对比，关联任务：ND EREV 工程车基本工作信息_5377_1，数据筛选时间从2025-08-29 00:00:00 到 2025-09-04 23:59:59",
    "生成区域图，统计横轴信号[HVBSOC_BatSOC、VehSpdAvgDrvn_1、VehOdo、HiVltgBatMinCellVltg、MtrBCntrlModeAchvd]的报警值，关联任务：ND EREV 工程车基本工作信息_5377_1，数据筛选时间从2025-08-29 00:00:00 到 2025-09-04 23:59:59",
    "生成折线图，统计横轴信号[EngActStdyStTorq、MtrBTorqAchvd、HiVltgBatMinCellVltg、OtsAirTmpCrVal、MtrATorqAchvd、HiVltgBatAvgTemp]的报警值，不指定图例，关联任务：ND EREV 工程车基本工作信息_5377_1，数据筛选时间从2025-08-29 00:00:00 到 2025-09-04 23:59:59"
]


def main():
    for input_text in TEST_CASES:
        print("=" * 60)
        pq = preprocess_chart_query(input_text)
        print(pq.to_prompt_section())
        print("=" * 60)
    


if __name__ == "__main__":
    main()
