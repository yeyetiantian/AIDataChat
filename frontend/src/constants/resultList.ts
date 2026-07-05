/** 筛选器上可查看结果列表的字段 */
export const RESULT_VIEW_FIELDS = ['rule_name', 'task'] as const

export interface ResultListItem {
  id: number
  vin: string
  rule: string
  ruleType: string
  preTime: string
  alarmTime: string
  duration: number
  alarmData: string
  freezeFrame: string
  highPrecision: string
  downsampled: string
}

export const RESULT_VIN_OPTIONS = [
  'LSGNB8P50TS013215',
  'LSGNB8P52TS035135',
  'LSGNB8P56TS013218',
]

export const RESULT_RULE_OPTIONS = [
  '车辆实时EREV工作比例',
  '横向控制激活次数及时长统计',
  '休眠持续时间',
]

export const RESULT_LIST_DATA: ResultListItem[] = [
  { id: 1, vin: 'LSGUNB95RA033722', rule: '横向控制激活次数及时长统计', ruleType: '统计', preTime: '2025-05-14 13:28:15.395', alarmTime: '2025-05-14 13:28:15.432', duration: 0.04, alarmData: '[MtrBtorgAchvd: 26.3500, -26.400...]', freezeFrame: 'VeVTAR_e_VMCFIt', highPrecision: '高精度数据', downsampled: 'RBF输出 MF4输出' },
  { id: 2, vin: 'LSGUNB95RA033722', rule: '横向控制激活次数及时长统计', ruleType: '统计', preTime: '2025-05-14 13:14:46.611', alarmTime: '2025-05-14 13:14:46.641', duration: 0.03, alarmData: '[MtrBtorgAchvd: 3.1500, 2.0000...]', freezeFrame: 'VeVTAR_e_VMCFIt', highPrecision: '高精度数据', downsampled: 'RBF输出 MF4输出' },
  { id: 3, vin: 'LSGUNB95RA033722', rule: '横向控制激活次数及时长统计', ruleType: '统计', preTime: '2025-05-14 13:08:20.238', alarmTime: '2025-05-14 13:08:20.427', duration: 0.03, alarmData: '[MtrBtorgAchvd: 2.3500, 0.6500...]', freezeFrame: 'VeVTAR_e_VMCFIt', highPrecision: '高精度数据', downsampled: 'RBF输出 MF4输出' },
  { id: 4, vin: 'LSGUNB95RA033722', rule: '横向控制激活次数及时长统计', ruleType: '统计', preTime: '2025-05-14 13:08:16.658', alarmTime: '2025-05-14 13:08:16.689', duration: 0.03, alarmData: '[MtrBtorgAchvd: 2.0000, -22.6000...]', freezeFrame: 'VeVTAR_e_VMCFIt', highPrecision: '高精度数据', downsampled: 'RBF输出 MF4输出' },
  { id: 5, vin: 'LSGUNB95RA033722', rule: '横向控制激活次数及时长统计', ruleType: '统计', preTime: '2025-05-14 13:08:16.578', alarmTime: '2025-05-14 13:08:16.609', duration: 0.03, alarmData: '[MtrBtorgAchvd: 1.8000, -19.6500...]', freezeFrame: 'VeVTAR_e_VMCFIt', highPrecision: '高精度数据', downsampled: 'RBF输出 MF4输出' },
  { id: 6, vin: 'LSGUNB95RA033722', rule: '横向控制激活次数及时长统计', ruleType: '统计', preTime: '2025-05-14 13:08:16.498', alarmTime: '2025-05-14 13:08:16.538', duration: 0.04, alarmData: '[MtrBtorgAchvd: 5.8500, -12.4000...]', freezeFrame: 'VeVTAR_e_VMCFIt', highPrecision: '高精度数据', downsampled: 'RBF输出 MF4输出' },
]
