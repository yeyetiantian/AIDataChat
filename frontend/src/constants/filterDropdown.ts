/** 筛选器时间类型字段（显示比较运算符 + 日期选择器） */
export const TIME_FILTER_FIELDS = ['condition_met_time', 'alarm_time'] as const

/** 筛选器数字类型字段（显示比较运算符 + 数字输入，保留一位小数） */
export const NUMERIC_FILTER_FIELDS = ['duration_sec', 'freeze_frame'] as const

/** 筛选器字符串类型字段（显示比较运算符 + 手动输入） */
export const STRING_FILTER_FIELDS = ['expression', 'alarm_value'] as const

/** 筛选器下拉静态数据 */
export const STATIC_DROPDOWN_DATA: Record<string, string[]> = {
  person: ['张三', '李四', '王五'],
  vehicle_type: ['SUV', '轿车'],
  vehicle: ['LSGNB8P50TS013215', 'LSGNB8P52TS035135', 'LSGNB8P56TS013218'],
  task: ['C1-2 PHEV 工程车基本工作信息', 'C1UL 静态电流监控5-13'],
  rule_name: ['车辆实时EREV工作比例', '休眠持续时间', '横向控制激活次数及时长统计'],
  rule_type: ['统计', '报警'],
}
