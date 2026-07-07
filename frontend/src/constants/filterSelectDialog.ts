export interface FilterSelectDialogColumn {
  field: string
  label: string
}

export interface FilterSelectDialogFieldConfig {
  title?: string
  head?: FilterSelectDialogColumn[]
  valueKey?: string
  labelKey?: string
}

/** 筛选器下拉超过该条数时使用弹窗选择 */
export const FILTER_DROPDOWN_DIALOG_THRESHOLD = 30

/** 各字段弹窗选择配置（未配置则使用筛选器 label 作为单列表头） */
export const FILTER_SELECT_DIALOG_CONFIG: Record<string, FilterSelectDialogFieldConfig> = {
  vehicle: {
    title: '车辆列表',
    head: [
      { field: 'vinPatacId', label: '泛亚编号' },
      { field: 'name', label: 'VIN' },
      { field: 'rmuCode', label: 'RMU模块号' },
    ],
  },
  signal2: {
    title: '信号选择',
    head: [{ field: 'name', label: '信号列表' }],
    valueKey: 'value',
    labelKey: 'label',
  },
}
