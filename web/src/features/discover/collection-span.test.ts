import { describe, expect, it } from 'vitest'
import type { Video } from '@/lib/api/client'
import { collectionSpan } from './collection-span'

const NOW = new Date('2026-11-25T18:00:00Z')

function video(firstSeen: string | null): Video {
  return {
    metrics: {
      views: {
        foundation_first_seen_at: firstSeen,
      } as Video['metrics']['views'],
      likes: null,
      comments: null,
    },
  } as Video
}

describe('collectionSpan', () => {
  it('is null when no item reports when it was collected', () => {
    expect(collectionSpan([], NOW)).toBeNull()
    expect(collectionSpan([video(null)], NOW)).toBeNull()
  })

  it('reports the oldest and newest collection time and is fresh within 24 hours', () => {
    const span = collectionSpan(
      [video('2026-11-25T12:58:20Z'), video('2026-11-25T12:57:50Z')],
      NOW
    )
    expect(span?.oldest).toBe('2026-11-25T12:57:50Z')
    expect(span?.newest).toBe('2026-11-25T12:58:20Z')
    expect(span?.stale).toBe(false)
  })

  it('is stale when any item was collected more than 24 hours ago', () => {
    const span = collectionSpan(
      [video('2026-11-25T17:00:00Z'), video('2026-11-24T17:59:00Z')],
      NOW
    )
    expect(span?.stale).toBe(true)
    expect(span?.oldestDay).not.toBe(span?.newestDay)
  })

  it('ignores items without a collection time', () => {
    const span = collectionSpan(
      [video(null), video('2026-11-25T10:00:00Z')],
      NOW
    )
    expect(span?.oldest).toBe('2026-11-25T10:00:00Z')
  })
})
