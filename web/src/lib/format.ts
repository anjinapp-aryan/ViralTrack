/**
 * Display formatting only. Nothing here computes a metric: every number shown comes from the API.
 * A missing value is rendered as text that says so, never as 0.
 */

const compactFormat = new Intl.NumberFormat('en', {
  notation: 'compact',
  maximumFractionDigits: 1,
})
const fullFormat = new Intl.NumberFormat('en')
const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
const dateFormat = new Intl.DateTimeFormat('en', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
})
const dateTimeFormat = new Intl.DateTimeFormat('en', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZoneName: 'short',
})

export function compactNumber(value: number | null | undefined): string | null {
  return value == null ? null : compactFormat.format(value)
}

export function fullNumber(value: number | null | undefined): string | null {
  return value == null ? null : fullFormat.format(value)
}

/** 47 -> "0:47", 731 -> "12:11", 3725 -> "1:02:05". Unknown or non-positive -> null. */
export function duration(seconds: number | null | undefined): string | null {
  if (seconds == null || !Number.isFinite(seconds) || seconds <= 0) return null
  const s = Math.floor(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const r = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${r}` : `${m}:${r}`
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
]

/** "3 days ago". Unknown or unparsable -> null. */
export function relativeTime(
  iso: string | null | undefined,
  now: Date = new Date()
): string | null {
  if (!iso) return null
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return null
  const diff = (t - now.getTime()) / 1000
  for (const [unit, size] of UNITS) {
    if (Math.abs(diff) >= size)
      return relative.format(Math.round(diff / size), unit)
  }
  return 'just now'
}

export function absoluteDate(iso: string | null | undefined): string | null {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : dateFormat.format(t)
}

export function absoluteDateTime(
  iso: string | null | undefined
): string | null {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : dateTimeFormat.format(t)
}

/** True for a known length of 1 to 180 seconds: the API's `up_to_3_min` duration filter. */
export function isUpToThreeMinutes(
  seconds: number | null | undefined
): boolean {
  return seconds != null && seconds > 0 && seconds <= 180
}
