import { describe, expect, it } from 'vitest'
import {
  absoluteDate,
  compactNumber,
  duration,
  fullNumber,
  isUpToThreeMinutes,
  relativeTime,
} from './format'

describe('format', () => {
  it('keeps unknown values unknown instead of turning them into 0', () => {
    expect(compactNumber(null)).toBeNull()
    expect(compactNumber(undefined)).toBeNull()
    expect(fullNumber(null)).toBeNull()
    expect(duration(null)).toBeNull()
    expect(relativeTime(null)).toBeNull()
    expect(absoluteDate('not a date')).toBeNull()
  })

  it('keeps a real zero', () => {
    expect(compactNumber(0)).toBe('0')
    expect(fullNumber(0)).toBe('0')
  })

  it('formats counts compactly and in full', () => {
    expect(compactNumber(2_577_753)).toBe('2.6M')
    expect(compactNumber(49_000)).toBe('49K')
    expect(fullNumber(2_577_753)).toBe('2,577,753')
  })

  it.each([
    [47, '0:47'],
    [731, '12:11'],
    [3725, '1:02:05'],
  ])('formats %i seconds as %s', (s, text) => {
    expect(duration(s)).toBe(text)
  })

  it('treats a zero or negative length as unknown', () => {
    expect(duration(0)).toBeNull()
    expect(duration(-5)).toBeNull()
  })

  it.each([
    [null, false],
    [0, false],
    [1, true],
    [180, true],
    [181, false],
  ])(
    'up-to-3-minutes for %s is %s (the API duration filter)',
    (s, expected) => {
      expect(isUpToThreeMinutes(s)).toBe(expected)
    }
  )

  it('formats relative time from a fixed clock', () => {
    const now = new Date('2026-11-07T12:00:00Z')
    expect(relativeTime('2026-11-04T12:00:00Z', now)).toBe('3 days ago')
    expect(relativeTime('2026-11-07T11:59:50Z', now)).toBe('just now')
  })
})
