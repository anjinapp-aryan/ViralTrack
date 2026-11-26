import type { Video } from '@/lib/api/client'
import { absoluteDate } from '@/lib/format'

const DAY_MS = 24 * 3600 * 1000

/**
 * When the shown videos entered the dataset: the oldest and newest `foundation_first_seen_at` of their
 * view counts (the time the foundation first stored each video). Null when no item reports it. The page is
 * stale when any item was collected more than 24 hours ago; that is judged on the oldest item, so a page is
 * never called fresh because of its newest row alone.
 */
export function collectionSpan(
  items: Video[],
  now: Date = new Date()
): {
  oldest: string
  newest: string
  oldestDay: string
  newestDay: string
  stale: boolean
} | null {
  let oldest: [number, string] | null = null
  let newest: [number, string] | null = null
  for (const v of items) {
    const iso = v.metrics.views?.foundation_first_seen_at
    const t = iso ? Date.parse(iso) : NaN
    if (!iso || Number.isNaN(t)) continue
    if (!oldest || t < oldest[0]) oldest = [t, iso]
    if (!newest || t > newest[0]) newest = [t, iso]
  }
  if (!oldest || !newest) return null
  return {
    oldest: oldest[1],
    newest: newest[1],
    oldestDay: absoluteDate(oldest[1]) ?? '',
    newestDay: absoluteDate(newest[1]) ?? '',
    stale: now.getTime() - oldest[0] > DAY_MS,
  }
}
