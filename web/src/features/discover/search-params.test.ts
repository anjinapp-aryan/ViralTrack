import { describe, expect, it } from 'vitest'
import { discoverSearchSchema, toApiParams } from './search-params'

describe('discover search params', () => {
  it('sends safe defaults: bounded creator size, approved sort, first page', () => {
    expect(toApiParams({})).toEqual({
      period: '30d',
      duration: 'any',
      sort: 'views',
      page: 1,
      page_size: 24,
      platform: 'youtube',
      creator_size: 'any',
    })
  })

  it('drops the discover-only filters when searching by text (the API refuses them)', () => {
    const params = toApiParams({
      q: 'local llm',
      creator_size: 'up_to_10k',
      region: 'US',
      min_views: 5,
      niche: 'demo',
    })
    expect(params.query).toBe('local llm')
    expect(params).not.toHaveProperty('sort') // relevance is the only order of topic search
    expect(params.niche).toBe('demo')
    expect(params).not.toHaveProperty('creator_size')
    expect(params).not.toHaveProperty('region')
    expect(params).not.toHaveProperty('min_views')
  })

  it.each([
    ['sort', 'engagement_rate'],
    ['sort', 'views_per_hour_24h'],
    ['sort', 'outlier_score'],
    ['period', 'forever'],
    ['creator_size', 'unlimited'],
    ['duration', 'shorts'],
    ['region', 'us'],
    ['page', 0],
    ['page', 999],
    ['min_views', -1],
  ])('ignores an unsupported %s value in the URL (%s)', (key, value) => {
    const parsed = discoverSearchSchema.parse({ [key]: value })
    expect(parsed[key as keyof typeof parsed]).toBeUndefined()
  })

  it('only ever asks for an approved sort', () => {
    for (const sort of [
      'views',
      'published_at',
      'engagement_rate',
      'viral_score',
    ]) {
      const p = toApiParams(discoverSearchSchema.parse({ sort }))
      expect(['views', 'published_at']).toContain(p.sort)
      expect(p.sort).not.toBe('relevance')
    }
  })
})
