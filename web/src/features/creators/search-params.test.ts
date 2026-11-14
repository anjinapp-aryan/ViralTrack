import { describe, expect, it } from 'vitest'
import {
  CREATOR_VIDEOS_WINDOW,
  CREATORS_PAGE_SIZE,
  creatorVideosSearchSchema,
  creatorsSearchSchema,
  toCreatorVideosParams,
  toCreatorsParams,
} from './search-params'

describe('creators search params', () => {
  it('sends safe defaults: a bounded creator size, the first page', () => {
    expect(toCreatorsParams({})).toEqual({
      period: '30d',
      creator_size: 'any',
      page: 1,
      page_size: 24,
      platform: 'youtube',
    })
  })

  it('sends the region only when one is chosen', () => {
    expect(toCreatorsParams({ region: 'US' }).region).toBe('US')
    expect(toCreatorsParams({})).not.toHaveProperty('region')
  })

  it.each([
    ['period', 'forever'],
    ['creator_size', 'unlimited'],
    ['region', 'us'],
    ['page', 0],
    ['page', 999],
  ])('ignores an unsupported %s in the URL (%s)', (key, value) => {
    const parsed = creatorsSearchSchema.parse({ [key]: value })
    expect(parsed[key as keyof typeof parsed]).toBeUndefined()
  })

  it('never offers a sort: the creators list has none', () => {
    const parsed = creatorsSearchSchema.parse({ sort: 'views' })
    expect(parsed).not.toHaveProperty('sort')
    expect(toCreatorsParams(parsed)).not.toHaveProperty('sort')
  })
})

describe('creator videos search params', () => {
  it('defaults to all collected videos, first page, 24 per page, YouTube', () => {
    expect(toCreatorVideosParams({})).toEqual({
      period: 'all',
      page: 1,
      page_size: CREATORS_PAGE_SIZE,
      platform: 'youtube',
    })
  })

  it('keeps the page within the 200-video window of the API', () => {
    const last = Math.floor(CREATOR_VIDEOS_WINDOW / CREATORS_PAGE_SIZE)
    expect(creatorVideosSearchSchema.parse({ page: last }).page).toBe(last)
    expect(creatorVideosSearchSchema.parse({ page: last + 1 }).page).toBe(
      undefined
    )
    expect(CREATORS_PAGE_SIZE * last).toBeLessThanOrEqual(CREATOR_VIDEOS_WINDOW)
  })

  it('ignores a sort or an invalid period in the URL', () => {
    const parsed = creatorVideosSearchSchema.parse({
      sort: 'vph',
      period: 'x',
    })
    expect(parsed).not.toHaveProperty('sort')
    expect(toCreatorVideosParams(parsed)).not.toHaveProperty('sort')
    expect(toCreatorVideosParams(parsed).period).toBe('all')
  })
})
