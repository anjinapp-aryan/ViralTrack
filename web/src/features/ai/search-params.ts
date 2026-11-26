/**
 * AI Content Intelligence state lives in the URL, so a view can be reloaded or shared. Values are limited to
 * what the API accepts; anything else falls back to the default instead of reaching the API.
 */
import { z } from 'zod'
import type {
  AiVideo,
  AiContentParams,
  AiCountriesParams,
  AiOpportunitiesParams,
  AiSummaryParams,
} from '@/lib/api/client'
import { PERIODS } from '@/features/discover/search-params'

export const STATUSES = [
  'CONFIRMED_AI',
  'LIKELY_AI',
  'POSSIBLY_AI',
  'NOT_AI',
  'UNKNOWN',
] as const
export const DEFAULT_STATUSES = ['CONFIRMED_AI', 'LIKELY_AI'] as const
export const CATEGORIES = [
  'AI_MUSIC_VIDEO',
  'AI_MUSIC_AUDIO',
  'AI_VIDEO_WITH_MUSIC',
  'AI_NORMAL_VIDEO',
  'NORMAL_NON_AI',
  'UNKNOWN',
] as const
/** URL format choices. live_other = a live or upcoming broadcast, or no usable length. */
export const FORMAT_CHOICES = ['short_form', 'long_form', 'live_other'] as const
const FORMAT_PARAM: Record<
  (typeof FORMAT_CHOICES)[number],
  ('short_form' | 'long_form' | 'live' | 'unknown')[]
> = {
  short_form: ['short_form'],
  long_form: ['long_form'],
  live_other: ['live', 'unknown'],
}

export const DEFAULT_PERIOD = '30d'
const PAGE_SIZE = 24
const CODE = /^([A-Z]{2}|unknown)$/
const LANG = /^([a-z]{2,3}|unknown)$/
const periodValues = PERIODS.map((p) => p.value) as [string, ...string[]]

const list = <T extends z.ZodTypeAny>(item: T) =>
  z.array(item).max(20).optional().catch(undefined)

export const aiSearchSchema = z.object({
  period: z.enum(periodValues).optional().catch(undefined),
  status: list(z.enum(STATUSES)),
  category: list(z.enum(CATEGORIES)),
  format: z.enum(FORMAT_CHOICES).optional().catch(undefined),
  basis: z.enum(['creator', 'discovery']).optional().catch(undefined),
  country: list(z.string().regex(CODE)),
  language: list(z.string().regex(LANG)),
  sort: z.enum(['views', 'published_at']).optional().catch(undefined),
  page: z.number().int().min(1).max(20).optional().catch(undefined),
})

export type AiSearch = z.infer<typeof aiSearchSchema>
export type Category = (typeof CATEGORIES)[number]

type Common = {
  period: string
  status?: AiSummaryParams['status']
  category?: AiSummaryParams['category']
  format?: AiSummaryParams['format']
  language?: string[]
  platform: 'youtube'
}

/** `scope`: the categories a focused page is limited to; the user's choice narrows it further. */
function common(s: AiSearch, scope?: readonly Category[]): Common {
  const p: Common = { period: s.period ?? DEFAULT_PERIOD, platform: 'youtube' }
  if (s.status?.length) p.status = s.status
  const chosen = scope
    ? (s.category ?? []).filter((c) => scope.includes(c))
    : (s.category ?? [])
  if (chosen.length) p.category = chosen
  else if (scope) p.category = [...scope]
  if (s.format) p.format = FORMAT_PARAM[s.format]
  if (s.language?.length) p.language = s.language
  return p
}

function withCountry<T extends Common>(
  p: T,
  s: AiSearch
): T & { creator_country?: string[]; discovery_country?: string[] } {
  if (!s.country?.length) return p
  return (s.basis ?? 'creator') === 'creator'
    ? { ...p, creator_country: s.country }
    : { ...p, discovery_country: s.country }
}

export function summaryParams(
  s: AiSearch,
  scope?: readonly Category[]
): AiSummaryParams {
  return withCountry(common(s, scope), s)
}

/** The same window without country or language filters: the options the pickers offer. */
export function optionParams(s: AiSearch): AiSummaryParams {
  const { language: _language, ...rest } = common(s)
  return rest
}

export function contentParams(
  s: AiSearch,
  scope?: readonly Category[]
): AiContentParams {
  return {
    ...withCountry(common(s, scope), s),
    sort: s.sort ?? 'views',
    page: s.page ?? 1,
    page_size: PAGE_SIZE,
  }
}

/** Every country of the window (the explorer lists them all and selects locally). */
export function countriesParams(s: AiSearch): AiCountriesParams {
  return { ...common(s), basis: s.basis ?? 'creator' }
}

export function opportunitiesParams(s: AiSearch): AiOpportunitiesParams {
  return { ...withCountry(common(s), s), basis: s.basis ?? 'creator' }
}

export function activeFilters(s: AiSearch): number {
  return [
    s.period && s.period !== DEFAULT_PERIOD,
    s.status?.length,
    s.category?.length,
    s.format,
    s.country?.length,
    s.language?.length,
  ].filter(Boolean).length
}

export const AI_CATEGORY_SET = new Set<string>(CATEGORIES.slice(0, 4))

/** The opportunity group this video would belong to: same category, format, language and creator country. */
export function opportunitySearch(item: AiVideo): Partial<AiSearch> {
  const { classification: c, format, country } = item
  const fmt = format.format_type
  const search: Partial<AiSearch> = {
    basis: 'creator',
    status: [...new Set([...DEFAULT_STATUSES, c.status])].filter(
      (s) => s !== 'NOT_AI' && s !== 'UNKNOWN'
    ) as AiSearch['status'],
    format: fmt === 'short_form' || fmt === 'long_form' ? fmt : 'live_other',
  }
  if (AI_CATEGORY_SET.has(c.category))
    search.category = [c.category as Category]
  if (country.language_code) search.language = [country.language_code]
  if (country.creator_country) search.country = [country.creator_country]
  return search
}
