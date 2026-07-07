import type { PivotConfig } from '@/types'

export interface StoredReportConfig {
  id: string
  name: string
  config: PivotConfig
  savedAt: string
}

const REPORT_CONFIG_STORAGE_KEY = 'aidata-chat:report-configs'

function canUseStorage() {
  return typeof window !== 'undefined' && !!window.localStorage
}

function createStoredConfigId() {
  return `cfg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export function clonePivotConfig(config: PivotConfig): PivotConfig {
  return JSON.parse(JSON.stringify(config)) as PivotConfig
}

function normalizeStoredReportConfig(value: unknown): StoredReportConfig | null {
  if (!value || typeof value !== 'object') return null

  const candidate = value as Partial<StoredReportConfig>
  if (typeof candidate.id !== 'string') return null
  if (typeof candidate.name !== 'string') return null
  if (!candidate.config || typeof candidate.config !== 'object') return null
  if (typeof candidate.savedAt !== 'string') return null

  return {
    id: candidate.id,
    name: candidate.name,
    config: clonePivotConfig(candidate.config as PivotConfig),
    savedAt: candidate.savedAt,
  }
}

export function loadStoredReportConfigs(): StoredReportConfig[] {
  if (!canUseStorage()) return []

  try {
    const raw = window.localStorage.getItem(REPORT_CONFIG_STORAGE_KEY)
    if (!raw) return []

    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []

    return parsed
      .map(normalizeStoredReportConfig)
      .filter((item): item is StoredReportConfig => item !== null)
      .sort((a, b) => new Date(b.savedAt).getTime() - new Date(a.savedAt).getTime())
  } catch {
    return []
  }
}

export function saveStoredReportConfig(name: string, config: PivotConfig): StoredReportConfig {
  if (!canUseStorage()) {
    throw new Error('当前浏览器不支持本地缓存')
  }

  const normalizedName = name.trim() || '未命名报表'
  const existingConfigs = loadStoredReportConfigs()
  const existingItem = existingConfigs.find(item => item.name === normalizedName)

  const savedItem: StoredReportConfig = {
    id: existingItem?.id ?? createStoredConfigId(),
    name: normalizedName,
    config: clonePivotConfig(config),
    savedAt: new Date().toISOString(),
  }

  try {
    const nextConfigs = [
      savedItem,
      ...existingConfigs.filter(item => item.name !== normalizedName),
    ]
    window.localStorage.setItem(REPORT_CONFIG_STORAGE_KEY, JSON.stringify(nextConfigs))
  } catch {
    throw new Error('保存配置失败，请检查浏览器缓存权限')
  }

  return savedItem
}

export function clearStoredReportConfigs() {
  if (!canUseStorage()) {
    throw new Error('当前浏览器不支持本地缓存')
  }

  try {
    window.localStorage.removeItem(REPORT_CONFIG_STORAGE_KEY)
  } catch {
    throw new Error('清空配置失败，请检查浏览器缓存权限')
  }
}
