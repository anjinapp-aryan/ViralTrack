/**
 * Synthetic TEST fixtures shaped by the generated OpenAPI types. They are not observations and are only used
 * by tests. The derived block deliberately carries values, so tests can prove the UI does not display them.
 */
import type {
  Capabilities,
  MetricValue,
  Readiness,
  Video,
  VideoPage,
} from '@/lib/api/client'

const raw = (value: number): MetricValue => ({
  value,
  kind: 'raw',
  source: 'youtube-data-api',
  provider: 'youtube',
  origin: 'test',
  collected_at: null,
  foundation_first_seen_at: '2026-11-01T10:00:00Z',
  note: null,
})

const derived = (value: number): MetricValue => ({
  ...raw(value),
  kind: 'derived',
  source: 'niche-finder',
  note: 'Calculated by niche-finder from YouTube data; not a YouTube metric.',
})

export function video(overrides: Partial<Video> = {}): Video {
  return {
    id: 'vid00001',
    platform: 'youtube',
    url: 'https://www.youtube.com/watch?v=vid00001',
    title: 'Local LLM on a laptop in 10 minutes',
    thumbnail_url: 'https://i.ytimg.com/vi/vid00001/hqdefault.jpg',
    published_at: '2026-10-20T12:00:00Z',
    duration_seconds: 603,
    content_type: 'video',
    category: 'Science & Technology',
    language: 'en',
    region: null,
    creator: {
      id: 'UC0000000000000000000a',
      platform: 'youtube',
      name: 'Tiny AI Lab',
      handle: '@tinyailab',
      url: 'https://www.youtube.com/@tinyailab',
      followers: raw(800),
      content_count: raw(24),
    },
    metrics: { views: raw(49000), likes: raw(2600), comments: raw(171) },
    derived: {
      engagement_rate: derived(5.655),
      views_per_hour_lifetime: derived(1234.5),
    },
    origin: 'test',
    retrieved_at: '2026-11-07T10:00:00Z',
    ...overrides,
  }
}

export function page(
  items: Video[],
  meta: Partial<VideoPage['meta']> = {}
): VideoPage {
  return {
    data: items,
    meta: {
      platform: 'youtube',
      sort: 'views',
      page: 1,
      page_size: 24,
      returned: items.length,
      has_more: false,
      total: items.length,
      data_origin: 'test',
      demo: true,
      notes: [],
      ...meta,
    },
  }
}

export const capabilities: Capabilities = {
  api_version: 'v1',
  page_size_max: 100,
  result_window_max: 1000,
  platforms: [
    {
      platform: 'youtube',
      available: true,
      reason: null,
      data_origin: 'test',
      capabilities: [],
    },
    {
      platform: 'instagram',
      available: false,
      reason: 'No approved data source.',
      data_origin: null,
      capabilities: [],
    },
    {
      platform: 'tiktok',
      available: false,
      reason: 'No approved data source.',
      data_origin: null,
      capabilities: [],
    },
  ],
  filters: [],
  sorts: [
    { name: 'views', available: true, applies_to: 'browse', reason: null },
    {
      name: 'published_at',
      available: true,
      applies_to: 'browse',
      reason: null,
    },
    {
      name: 'relevance',
      available: true,
      applies_to: 'topic_search',
      description: 'Topic search only.',
    },
    {
      name: 'engagement_rate',
      available: false,
      applies_to: 'browse',
      reason: 'the foundation orders hidden like counts as zero',
    },
    {
      name: 'views_per_hour_24h',
      available: false,
      applies_to: 'browse',
      reason: 'no snapshot time is reported',
    },
  ],
  metrics: [
    {
      name: 'views',
      kind: 'raw',
      sortable: true,
      description: 'views as reported',
    },
    {
      name: 'likes',
      kind: 'raw',
      sortable: false,
      description: 'null when hidden',
    },
  ],
}

export const ready: Readiness = {
  status: 'ready',
  service: 'viraltrack-api',
  version: '1.0.0',
  checks: { youtube: { status: 'ok', required: true } },
}

/** Words for values ViralTrack must never display. */
export const FORBIDDEN_TEXT = [
  /\bvsr\b/i,
  /outlier/i,
  /viral score/i,
  /\brpm\b/i,
  /engagement/i,
  /per hour/i,
  /\bvph\b/i,
  /acceleration/i,
  /breakout/i,
]
