/** 筛选器时间类型字段（显示比较运算符 + 日期选择器） */
export const TIME_FILTER_FIELDS = ['condition_met_time', 'alarm_time', 'trigger_time'] as const

/** 筛选器数字类型字段（显示比较运算符 + 数字输入，保留一位小数） */
export const NUMERIC_FILTER_FIELDS = ['duration_sec', 'freeze_frame'] as const

/** 筛选器字符串类型字段（显示比较运算符 + 手动输入） */
export const STRING_FILTER_FIELDS = ['expression', 'alarm_value'] as const

/** 筛选器联动接口字段（task / rule_name / vehicle / alarm_time / trigger_time） */
export const API_FILTER_FIELDS = ['task', 'rule_name', 'vehicle', 'alarm_time', 'trigger_time'] as const

/** 筛选器联动接口下拉字段 */
export const API_DROPDOWN_FILTER_FIELDS = ['task', 'rule_name', 'vehicle'] as const

/** 筛选器变更时需刷新信号列表的字段 */
export const SIGNAL_TRIGGER_FILTER_FIELDS = ['task', 'rule_name'] as const

/** 筛选器变更时需刷新信号下拉（signal2）的字段 */
export const SIGNAL_DROPDOWN_TRIGGER_FIELDS = ['task', 'rule_name', 'vehicle'] as const

/** 信号筛选器下拉联动 focusField */
export const SIGNAL_FILTER_DROPDOWN_FOCUS = 'signal2'

/** 筛选器下拉静态数据 */
export const STATIC_DROPDOWN_DATA: Record<string, string[]> = {
  person: ['张三', '李四', '王五'],
  vehicle_type: ['SUV', '轿车'],
  rule_type: ['统计', '报警'],
}
