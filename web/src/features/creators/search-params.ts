/**
 * Creators state lives in the URL. Values are limited to what the API accepts (docs/api/openapi-v1.json);
 * anything else falls back to the default instead of reaching the API.
 */
import { z } from 'zod'
import type { CreatorVideosParams, CreatorsParams } from '@/lib/api/client'
import { DEFAULT_PERIOD, PERIODS } from '@/features/discover/search-params'

export const CREATORS_PAGE_SIZE = 24
/** the API lists at most 1000 creators, and at most 200 videos of one creator */
export const CREATORS_WINDOW = 1000
export const CREATOR_VIDEOS_WINDOW = 200

const periodValues = PERIODS.map((p) => p.value) as [string, ...string[]]

export const creatorsSearchSchema = z.object({
  period: z.enum(periodValues).optional().catch(undefined),
  creator_size: z
    .enum(['any', 'up_to_10k', 'up_to_100k', 'up_to_1m'])
    .optional()
    .catch(undefined),
  region: z
    .string()
    .regex(/^[A-Z]{2}$/)
    .optional()
    .catch(undefined),
  page: z
    .number()
    .int()
    .min(1)
    .max(Math.floor(CREATORS_WINDOW / CREATORS_PAGE_SIZE))
    .optional()
    .catch(undefined),
})

export type CreatorsSearch = z.infer<typeof creatorsSearchSchema>

export function toCreatorsParams(s: CreatorsSearch): CreatorsParams {
  const params: CreatorsParams = {
    period: s.period ?? DEFAULT_PERIOD,
    creator_size: s.creator_size ?? 'any',
    page: s.page ?? 1,
    page_size: CREATORS_PAGE_SIZE,
    platform: 'youtube',
  }
  if (s.region) params.region = s.region
  return params
}

export function activeCreatorFilters(s: CreatorsSearch): number {
  return [
    s.period && s.period !== DEFAULT_PERIOD ? s.period : undefined,
    s.creator_size && s.creator_size !== 'any' ? s.creator_size : undefined,
    s.region,
  ].filter((v) => v != null).length
}

/** The videos of one creator: a period and a page; the order is fixed (newest first) by the API. */
export const creatorVideosSearchSchema = z.object({
  period: z.enum(periodValues).optional().catch(undefined),
  page: z
    .number()
    .int()
    .min(1)
    .max(Math.floor(CREATOR_VIDEOS_WINDOW / CREATORS_PAGE_SIZE))
    .optional()
    .catch(undefined),
})

export type CreatorVideosSearch = z.infer<typeof creatorVideosSearchSchema>

export function toCreatorVideosParams(
  s: CreatorVideosSearch
): CreatorVideosParams {
  return {
    period: s.period ?? 'all',
    page: s.page ?? 1,
    page_size: CREATORS_PAGE_SIZE,
    platform: 'youtube',
  }
}
