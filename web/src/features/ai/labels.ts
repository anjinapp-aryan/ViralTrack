/** Display names for the AI taxonomy. Words only: no value here is computed. */

export const STATUS_LABEL: Record<string, string> = {
  CONFIRMED_AI: 'Confirmed AI',
  LIKELY_AI: 'Likely AI',
  POSSIBLY_AI: 'Possibly AI',
  NOT_AI: 'Not AI (creator says)',
  UNKNOWN: 'Unclassified',
}

export const STATUS_HINT: Record<string, string> = {
  CONFIRMED_AI:
    'The creator disclosed synthetic content to the platform, or states it is AI-generated and names how.',
  LIKELY_AI:
    'A creator statement, a named generation tool, or several AI labels.',
  POSSIBLY_AI:
    'One weak AI label, or AI tools named in what may be a video about them.',
  NOT_AI: 'The creator states that no AI was used.',
  UNKNOWN: 'Not enough evidence either way. Not the same as human-made.',
}

export const CATEGORY_LABEL: Record<string, string> = {
  AI_MUSIC_VIDEO: 'AI music video',
  AI_MUSIC_AUDIO: 'AI music / audio',
  AI_VIDEO_WITH_MUSIC: 'AI video with soundtrack',
  AI_NORMAL_VIDEO: 'AI story / explainer',
  NORMAL_NON_AI: 'Normal / non-AI',
  UNKNOWN: 'Category unclear',
}

export const FORMAT_LABEL: Record<string, string> = {
  short_form: 'Short-form by duration (≤ 3 min)',
  long_form: 'Long-form',
  live: 'Live',
  unknown: 'Length unknown',
  live_other: 'Live / other',
}

/** Why platform-verified Shorts are not offered: shown wherever the format is chosen or counted. */
export const VERIFIED_SHORTS_UNAVAILABLE =
  'Unavailable: the YouTube Data API reports no Shorts flag, so no video can be verified as a YouTube Short. Short-form here means a length of 3 minutes or less.'

export const CONFIDENCE_LABEL: Record<string, string> = {
  high: 'High evidence',
  medium: 'Medium evidence',
  low: 'Low evidence',
  none: 'No evidence',
}

const regionNames = new Intl.DisplayNames(['en'], { type: 'region' })
const languageNames = new Intl.DisplayNames(['en'], { type: 'language' })

export function countryName(code: string | null | undefined): string {
  if (!code || code === 'unknown') return 'Unknown'
  try {
    return regionNames.of(code) ?? code
  } catch {
    return code
  }
}

export function languageName(code: string | null | undefined): string {
  if (!code || code === 'unknown') return 'Unknown'
  try {
    return languageNames.of(code) ?? code
  } catch {
    return code
  }
}

const DAY_MS = 24 * 3600 * 1000

/** True when the earliest collection time is more than 24 hours ago. */
export function isStale(
  iso: string | null | undefined,
  now: Date = new Date()
): boolean {
  if (!iso) return false
  const t = Date.parse(iso)
  return !Number.isNaN(t) && now.getTime() - t > DAY_MS
}

export function countOf(
  counts: { key: string; count: number }[] | undefined,
  key: string
): number {
  return counts?.find((c) => c.key === key)?.count ?? 0
}

export function label(map: Record<string, string>, key: string): string {
  return map[key] ?? key
}
