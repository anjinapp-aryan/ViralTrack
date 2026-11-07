/**
 * Discover state lives in the URL, so a view can be reloaded or shared. Values are limited to what the API
 * accepts (docs/api/openapi-v1.json); anything else falls back to the default instead of reaching the API.
 */
import { z } from 'zod'
import type { DiscoverParams } from '@/lib/api/client'

export const PERIODS = [
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '90d', label: 'Last 90 days' },
  { value: '365d', label: 'Last 12 months' },
  { value: 'all', label: 'All collected' },
] as const

export const CREATOR_SIZES = [
  { value: 'any', label: 'Any size (up to 1M)' },
  { value: 'up_to_10k', label: 'Up to 10K followers' },
  { value: 'up_to_100k', label: 'Up to 100K followers' },
  { value: 'up_to_1m', label: 'Up to 1M followers' },
] as const

export const DURATIONS = [
  { value: 'any', label: 'Any length' },
  { value: 'up_to_3_min', label: 'Up to 3 min' },
  { value: 'over_3_min', label: 'Over 3 min' },
] as const

export const SORT_LABELS: Record<string, string> = {
  views: 'Most views',
  published_at: 'Newest',
}

const PAGE_SIZE = 24
const MAX_PAGE = Math.floor(1000 / PAGE_SIZE) // the API's 1000-item window

const periodValues = PERIODS.map((p) => p.value) as [string, ...string[]]

export const discoverSearchSchema = z.object({
  q: z.string().trim().min(1).max(200).optional().catch(undefined),
  period: z.enum(periodValues).optional().catch(undefined),
  creator_size: z
    .enum(['any', 'up_to_10k', 'up_to_100k', 'up_to_1m'])
    .optional()
    .catch(undefined),
  duration: z
    .enum(['any', 'up_to_3_min', 'over_3_min'])
    .optional()
    .catch(undefined),
  sort: z.enum(['views', 'published_at']).optional().catch(undefined),
  niche: z.string().trim().min(1).max(100).optional().catch(undefined),
  region: z
    .string()
    .regex(/^[A-Z]{2}$/)
    .optional()
    .catch(undefined),
  min_views: z.number().int().min(0).max(1e12).optional().catch(undefined),
  page: z.number().int().min(1).max(MAX_PAGE).optional().catch(undefined),
})

export type DiscoverSearch = z.infer<typeof discoverSearchSchema>

export const DEFAULT_PERIOD = '30d'

/** URL state -> API parameters. Text search does not accept the discover-only filters, so they are dropped. */
export function toApiParams(s: DiscoverSearch): DiscoverParams {
  const params: DiscoverParams = {
    period: s.period ?? DEFAULT_PERIOD,
    duration: s.duration ?? 'any',

    page: s.page ?? 1,
    page_size: PAGE_SIZE,
    platform: 'youtube',
  }
  if (s.niche) params.niche = s.niche
  if (s.q) {
    // topic search has one order (relevance); the API refuses a sort with a query
    params.query = s.q
  } else {
    params.sort = s.sort ?? 'views'
    params.creator_size = s.creator_size ?? 'any'
    if (s.region) params.region = s.region
    if (s.min_views != null) params.min_views = s.min_views
  }
  return params
}

export function activeFilterCount(s: DiscoverSearch): number {
  return [
    s.q,
    s.niche,
    s.region,
    s.min_views,
    s.creator_size && s.creator_size !== 'any' ? s.creator_size : undefined,
    s.duration && s.duration !== 'any' ? s.duration : undefined,
  ].filter((v) => v != null).length
}
