import type { PivotConfig } from '@/types'

export interface MockBoardChart {
  title: string
  description: string
  chartType: 'bar' | 'line' | 'area' | 'point' | 'pie' | 'radar'
  pivotConfig: PivotConfig
  data: Record<string, any>[]
}

function createBaseConfig(partial: Partial<PivotConfig>): PivotConfig {
  return {
    filters: [],
    axes: [],
    legend: [],
    values: [],
    order_by: [],
    limit: 1000,
    having: [],
    grand_total: false,
    subtotals: false,
    ...partial,
  }
}

export function createMockBoardCharts(): MockBoardChart[] {
  return [
    {
      title: '各车型报警次数',
      description: '模拟数据: 车型维度的报警次数对比',
      chartType: 'bar',
      pivotConfig: createBaseConfig({
        axes: [{ field: 'vehicle_type', alias: '车型' }],
        values: [{ id: 'val_1', field: 'alarm_time', aggregation: 'count', alias: '报警次数' }],
      }),
      data: [
        { 车型: 'SUV', alarm_time: 128 },
        { 车型: '轿车', alarm_time: 96 },
        { 车型: 'MPV', alarm_time: 67 },
        { 车型: '跑车', alarm_time: 42 },
        { 车型: '皮卡', alarm_time: 25 },
      ],
    },
    {
      title: '近7日报警趋势',
      description: '模拟数据: 近 7 天报警数量变化',
      chartType: 'line',
      pivotConfig: createBaseConfig({
        axes: [{ field: 'alarm_time', alias: '报警时间', aggregation: 'day' }],
        values: [{ id: 'val_1', field: 'alarm_time', aggregation: 'count', alias: '报警次数' }],
        order_by: [{ field: 'alarm_time', direction: 'asc' }],
      }),
      data: [
        { 报警时间: '2026-06-29', alarm_time: 38 },
        { 报警时间: '2026-06-30', alarm_time: 44 },
        { 报警时间: '2026-07-01', alarm_time: 41 },
        { 报警时间: '2026-07-02', alarm_time: 57 },
        { 报警时间: '2026-07-03', alarm_time: 63 },
        { 报警时间: '2026-07-04', alarm_time: 59 },
        { 报警时间: '2026-07-05', alarm_time: 71 },
      ],
    },
    {
      title: '近7日前置条件持续时间',
      description: '模拟数据: 每日持续时间总量变化',
      chartType: 'area',
      pivotConfig: createBaseConfig({
        axes: [{ field: 'condition_met_time', alias: '前置条件满足时间', aggregation: 'day' }],
        values: [{ id: 'val_1', field: 'duration_sec', aggregation: 'sum', alias: '持续时间(秒)' }],
        order_by: [{ field: 'condition_met_time', direction: 'asc' }],
      }),
      data: [
        { 前置条件满足时间: '2026-06-29', duration_sec: 820 },
        { 前置条件满足时间: '2026-06-30', duration_sec: 910 },
        { 前置条件满足时间: '2026-07-01', duration_sec: 860 },
        { 前置条件满足时间: '2026-07-02', duration_sec: 1040 },
        { 前置条件满足时间: '2026-07-03', duration_sec: 1180 },
        { 前置条件满足时间: '2026-07-04', duration_sec: 1095 },
        { 前置条件满足时间: '2026-07-05', duration_sec: 1260 },
      ],
    },
    {
      title: '车型风险分布散点',
      description: '模拟数据: 平均持续时间与报警次数的分布关系',
      chartType: 'point',
      pivotConfig: createBaseConfig({
        axes: [{ field: 'vehicle_type', alias: '车型' }],
        values: [
          { id: 'val_1', field: 'duration_sec', aggregation: 'avg', alias: '平均持续时间(秒)' },
          { id: 'val_2', field: 'alarm_time', aggregation: 'count', alias: '报警次数' },
        ],
      }),
      data: [
        { 车型: 'SUV', duration_sec: 18, alarm_time: 128 },
        { 车型: '轿车', duration_sec: 11, alarm_time: 96 },
        { 车型: 'MPV', duration_sec: 24, alarm_time: 67 },
        { 车型: '跑车', duration_sec: 31, alarm_time: 42 },
        { 车型: '皮卡', duration_sec: 27, alarm_time: 25 },
        { 车型: '旅行车', duration_sec: 15, alarm_time: 58 },
      ],
    },
    {
      title: '规则类型占比',
      description: '模拟数据: 不同规则类型报警数量占比',
      chartType: 'pie',
      pivotConfig: createBaseConfig({
        axes: [{ field: 'rule_type', alias: '规则类型' }],
        values: [{ id: 'val_1', field: 'alarm_time', aggregation: 'count', alias: '报警次数' }],
      }),
      data: [
        { 规则类型: '横向控制', alarm_time: 132 },
        { 规则类型: '纵向控制', alarm_time: 104 },
        { 规则类型: '感知异常', alarm_time: 86 },
        { 规则类型: '执行器异常', alarm_time: 48 },
      ],
    },
    {
      title: '规则类型多指标雷达',
      description: '模拟数据: 规则类型的多指标综合对比',
      chartType: 'radar',
      pivotConfig: createBaseConfig({
        axes: [{ field: 'rule_type', alias: '规则类型' }],
        values: [
          { id: 'val_1', field: 'duration_sec', aggregation: 'avg', alias: '平均持续时间(秒)' },
          { id: 'val_2', field: 'alarm_time', aggregation: 'count', alias: '报警次数' },
          { id: 'val_3', field: 'vehicle', aggregation: 'count_distinct', alias: '车辆数' },
        ],
      }),
      data: [
        { 规则类型: '横向控制', duration_sec: 18, alarm_time: 132, vehicle: 24 },
        { 规则类型: '纵向控制', duration_sec: 15, alarm_time: 104, vehicle: 19 },
        { 规则类型: '感知异常', duration_sec: 22, alarm_time: 86, vehicle: 16 },
        { 规则类型: '执行器异常', duration_sec: 27, alarm_time: 48, vehicle: 11 },
        { 规则类型: '通信异常', duration_sec: 13, alarm_time: 57, vehicle: 14 },
      ],
    },
  ]
}
