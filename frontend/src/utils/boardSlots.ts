const BOARD_SLOT_STORAGE_KEY = 'aidata-chat-board-slot-map'

type SlotMappedBoard = {
  id: number
  created_at: string
}

type BoardSlotMap = Record<string, number>

function isValidSlotIndex(slotIndex: number, maxSlots: number) {
  return Number.isInteger(slotIndex) && slotIndex >= 0 && slotIndex < maxSlots
}

function getFirstEmptySlot(usedSlots: Set<number>, maxSlots: number) {
  for (let index = 0; index < maxSlots; index += 1) {
    if (!usedSlots.has(index)) return index
  }
  return null
}

function sortBoardsByCreatedOrder<T extends SlotMappedBoard>(charts: T[]) {
  return [...charts].sort((a, b) => {
    const timeA = Date.parse(a.created_at || '') || 0
    const timeB = Date.parse(b.created_at || '') || 0
    if (timeA !== timeB) return timeA - timeB
    return Number(a.id) - Number(b.id)
  })
}

function readBoardSlotMap(): BoardSlotMap {
  if (typeof window === 'undefined') return {}

  try {
    const rawValue = window.localStorage.getItem(BOARD_SLOT_STORAGE_KEY)
    if (!rawValue) return {}

    const parsed = JSON.parse(rawValue)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}

    return Object.fromEntries(
      Object.entries(parsed).filter((entry): entry is [string, number] => typeof entry[1] === 'number'),
    )
  } catch {
    return {}
  }
}

function writeBoardSlotMap(slotMap: BoardSlotMap) {
  if (typeof window === 'undefined') return

  try {
    window.localStorage.setItem(BOARD_SLOT_STORAGE_KEY, JSON.stringify(slotMap))
  } catch {
    // Ignore storage errors and fall back to in-memory ordering.
  }
}

export function clearBoardSlotMap() {
  writeBoardSlotMap({})
}

export function syncBoardSlotMap<T extends SlotMappedBoard>(charts: T[], maxSlots: number) {
  const persistedSlotMap = readBoardSlotMap()
  const normalizedSlotMap: BoardSlotMap = {}
  const usedSlots = new Set<number>()

  for (const chart of sortBoardsByCreatedOrder(charts)) {
    const chartKey = String(chart.id)
    const slotIndex = persistedSlotMap[chartKey]
    if (!isValidSlotIndex(slotIndex, maxSlots) || usedSlots.has(slotIndex)) continue

    normalizedSlotMap[chartKey] = slotIndex
    usedSlots.add(slotIndex)
  }

  for (const chart of sortBoardsByCreatedOrder(charts)) {
    const chartKey = String(chart.id)
    if (chartKey in normalizedSlotMap) continue

    const nextSlotIndex = getFirstEmptySlot(usedSlots, maxSlots)
    if (nextSlotIndex == null) break

    normalizedSlotMap[chartKey] = nextSlotIndex
    usedSlots.add(nextSlotIndex)
  }

  writeBoardSlotMap(normalizedSlotMap)
  return normalizedSlotMap
}

export function assignBoardSlot<T extends SlotMappedBoard>(
  boardId: number,
  slotIndex: number,
  charts: T[],
  maxSlots: number,
) {
  const normalizedSlotMap = syncBoardSlotMap(charts, maxSlots)
  if (!isValidSlotIndex(slotIndex, maxSlots)) return normalizedSlotMap

  const boardKey = String(boardId)
  const previousSlotIndex = normalizedSlotMap[boardKey]
  const conflictingBoardKey = Object.keys(normalizedSlotMap).find(
    key => key !== boardKey && normalizedSlotMap[key] === slotIndex,
  )

  normalizedSlotMap[boardKey] = slotIndex

  if (conflictingBoardKey) {
    if (isValidSlotIndex(previousSlotIndex, maxSlots)) {
      normalizedSlotMap[conflictingBoardKey] = previousSlotIndex
    } else {
      delete normalizedSlotMap[conflictingBoardKey]
    }
  }

  writeBoardSlotMap(normalizedSlotMap)
  return normalizedSlotMap
}

export function removeBoardSlot(boardId: number) {
  const slotMap = readBoardSlotMap()
  const boardKey = String(boardId)

  if (!(boardKey in slotMap)) return

  delete slotMap[boardKey]
  writeBoardSlotMap(slotMap)
}

export function buildBoardSlots<T extends SlotMappedBoard>(charts: T[], maxSlots: number) {
  const slotMap = syncBoardSlotMap(charts, maxSlots)
  const slots = Array.from({ length: maxSlots }, () => null as T | null)

  for (const chart of charts) {
    const slotIndex = slotMap[String(chart.id)]
    if (!isValidSlotIndex(slotIndex, maxSlots)) continue

    slots[slotIndex] = chart
  }

  return slots
}
