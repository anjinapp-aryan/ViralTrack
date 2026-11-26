/**
 * AI Content Intelligence as a whole: the real router, providers and components, with `fetch` answered by
 * synthetic API responses. Checks the views, every filter's request, the states, the data labels, the policy
 * wording and accessibility (axe-core).
 */
import {
  FORBIDDEN_TEXT,
  capabilities,
  ready,
  video,
} from '@/test-utils/fixtures'
import { json, renderApp } from '@/test-utils/render-app'
import axe from 'axe-core'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { page as browserPage, userEvent } from 'vitest/browser'
import type {
  AiCountries,
  AiOpportunities,
  AiSummary,
  AiVideo,
  CorpusMeta,
} from '@/lib/api/client'

const NOW = new Date().toISOString()

function meta(overrides: Partial<CorpusMeta> = {}): CorpusMeta {
  return {
    platform: 'youtube',
    data_origin: 'test',
    demo: true,
    period: '30d',
    candidates_examined: 14,
    candidate_limit: 500,
    candidate_limit_reached: false,
    excluded_gaming: 1,
    signals_missing: 1,
    collected_from: NOW,
    collected_to: NOW,
    classifier_version: 'ai-content-rules/1.0.0',
    notes: [
      "Counts describe the collected corpus examined for this answer, not the platform and not any country's market.",
    ],
    ...overrides,
  }
}

function aiVideo(
  id: string,
  title: string,
  over: Partial<AiVideo> = {}
): AiVideo {
  return {
    video: video({ id, title, url: `https://www.youtube.com/watch?v=${id}` }),
    classification: {
      status: 'LIKELY_AI',
      confidence: 'medium',
      category: 'AI_MUSIC_VIDEO',
      reason: 'a generation tool is named and the content is labelled as AI',
      category_reason: 'music (music video) with AI visuals (music video)',
      evidence_sources: ['title'],
      evidence: [
        'generation tool named: kling (visual)',
        'AI content label: aimusicvideo',
      ],
      classifier_version: 'ai-content-rules/1.0.0',
      classified_at: NOW,
    },
    format: {
      format_type: 'short_form',
      format_confidence: 'medium',
      reason: 'length 50 s (at most 180 s) and the creator tagged it #shorts',
      duration_seconds: 50,
    },
    country: {
      discovery_countries: ['IN'],
      discovery_source: 'viraltrack_regional_collection',
      creator_country: 'IN',
      creator_country_source: 'creator_declared_channel_country',
      creator_country_confidence: 'medium',
      language_code: 'kn',
      language_source: 'platform_metadata_or_data_source_text_detection',
    },
    ...over,
  }
}

const ITEMS = [
  aiVideo('aiKnMusic01', 'Amma Magana Haadu | AI music video'),
  aiVideo('aiEnLofi004', 'Lo-fi beats to study', {
    country: {
      discovery_countries: [],
      discovery_source: null,
      creator_country: null,
      creator_country_source: null,
      creator_country_confidence: 'none',
      language_code: null,
      language_source: null,
    },
  }),
]

const SUMMARY: AiSummary = {
  meta: meta(),
  matching: 7,
  by_status: [
    { key: 'LIKELY_AI', count: 5 },
    { key: 'UNKNOWN', count: 4 },
    { key: 'CONFIRMED_AI', count: 2 },
    { key: 'NOT_AI', count: 1 },
    { key: 'POSSIBLY_AI', count: 1 },
  ],
  by_category: [
    { key: 'AI_MUSIC_VIDEO', count: 3 },
    { key: 'AI_MUSIC_AUDIO', count: 1 },
  ],
  by_format: [
    { key: 'short_form', count: 5 },
    { key: 'long_form', count: 2 },
  ],
  by_confidence: [{ key: 'medium', count: 4 }],
  by_creator_country: [
    { key: 'IN', count: 3 },
    { key: 'US', count: 2 },
    { key: 'unknown', count: 1 },
  ],
  by_discovery_country: [
    { key: 'IN', count: 3 },
    { key: 'KR', count: 1 },
  ],
  by_language: [
    { key: 'kn', count: 3 },
    { key: 'en', count: 3 },
  ],
  recent: [ITEMS[0]],
}

const CONTENT = {
  data: ITEMS,
  meta: {
    ...meta(),
    sort: 'views' as const,
    page: 1,
    page_size: 24,
    returned: 2,
    total: 2,
    has_more: false,
  },
}

const COUNTRIES: AiCountries = {
  meta: meta(),
  basis: 'creator',
  data: [
    {
      country: 'IN',
      items: 3,
      by_category: [{ key: 'AI_MUSIC_VIDEO', count: 3 }],
      by_format: [{ key: 'short_form', count: 3 }],
      by_language: [{ key: 'kn', count: 3 }],
      by_published_day: [{ key: '2026-11-20', count: 1 }],
    },
    {
      country: 'US',
      items: 2,
      by_category: [{ key: 'AI_MUSIC_AUDIO', count: 1 }],
      by_format: [{ key: 'long_form', count: 2 }],
      by_language: [{ key: 'en', count: 2 }],
      by_published_day: [{ key: '2026-11-18', count: 2 }],
    },
  ],
}

const OPPS: AiOpportunities = {
  meta: meta(),
  basis: 'creator',
  min_items: 3,
  data: [
    {
      key: 'AI_MUSIC_VIDEO|short_form|kn|IN|creator',
      category: 'AI_MUSIC_VIDEO',
      format_type: 'short_form',
      language_code: 'kn',
      country: 'IN',
      country_basis: 'creator',
      item_count: 3,
      newest_published_at: NOW,
      themes: [
        { term: 'amma', items: 3 },
        { term: 'emotional', items: 3 },
      ],
      summary:
        '3 short-form (up to 3 min) AI music videos in Kannada from creators who list India as their country appear in the collected corpus; recurring themes: amma, emotional.',
      evidence: [
        {
          id: 'aiKnMusic01',
          url: 'https://www.youtube.com/watch?v=aiKnMusic01',
          title: 'Amma Magana Haadu',
          creator_name: 'Synthetic channel a1',
          published_at: NOW,
          views: ITEMS[0].video.metrics.views,
          status: 'LIKELY_AI',
          category: 'AI_MUSIC_VIDEO',
        },
      ],
      brief: {
        opportunity_title:
          'Original Kannada music video (short-form (up to 3 min)) on amma, emotional',
        country: 'IN',
        country_basis: 'creator',
        language_code: 'kn',
        category: 'AI_MUSIC_VIDEO',
        format_type: 'short_form',
        audience_hypothesis: 'A hypothesis to test, not audience data.',
        theme: 'amma, emotional',
        original_creative_angle: 'Tell a new story about amma, emotional.',
        suggested_duration: 'about 50 s',
        hook_concept: 'Show the emotional core in the first two seconds.',
        story_outline: ['Opening image', 'Verse', 'Chorus'],
        music_direction: 'An original composition in Kannada.',
        visual_direction: 'A visual style you define; vertical 9:16.',
        platform_recommendations: ['YouTube Shorts (vertical, up to 3 min)'],
        rights_checklist: [
          'Lyrics, melody, arrangement and script are newly written; nothing is taken from the supporting videos.',
          'No cloned voice of a real singer or person without their written consent.',
        ],
        generated_by: 'template',
        note: 'Written from fixed templates and the collected metadata; no language model was used.',
      },
    },
  ],
}

function api(extra: Record<string, Response | (() => Response) | Error> = {}) {
  return {
    '/api/v1/capabilities': json(capabilities),
    '/api/v1/health/ready': json(ready),
    '/api/v1/ai/summary': json(SUMMARY),
    '/api/v1/ai/content': json(CONTENT),
    '/api/v1/ai/countries': json(COUNTRIES),
    '/api/v1/ai/opportunities': json(OPPS),
    ...extra,
  }
}

function params(calls: string[], path: string) {
  const all = calls.filter((c) => c.startsWith(path))
  return new URL(all[all.length - 1], 'http://x').searchParams
}

/** Every request to `path` made after the first `since` calls. */
function sent(calls: string[], path: string, since = 0) {
  return calls
    .slice(since)
    .filter((c) => c.startsWith(path))
    .map((c) => new URL(c, 'http://x').searchParams)
}

async function seriousViolations(root: Element) {
  const result = await axe.run(root, { resultTypes: ['violations'] })
  return result.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id}: ${v.nodes.length}`)
}

afterEach(async () => {
  vi.unstubAllGlobals()
  document.documentElement.className = ''
  await browserPage.viewport(1280, 900)
})

const PAGES = [
  '/ai',
  '/ai/discover',
  '/ai/countries',
  '/ai/music',
  '/ai/video',
  '/ai/opportunities',
  '/ai/briefs',
]

type Screen = Awaited<ReturnType<typeof renderApp>>['screen']

async function openContent(screen: Screen) {
  await userEvent.click(
    screen.getByRole('button', { name: /Content: AI status and category/ })
  )
}

describe('AI workspace navigation', () => {
  it('makes AI Intelligence the first navigation group and keeps Explore and Reference', async () => {
    await browserPage.viewport(1280, 900) // the sidebar is off-canvas on narrow screens
    const { screen } = await renderApp('/ai', api())
    await expect
      .element(screen.getByText('Classification funnel'))
      .toBeInTheDocument()
    const sidebar =
      document.querySelector('[data-sidebar="sidebar"]') ?? document.body
    const links = [...sidebar.querySelectorAll('a')].map((a) =>
      a.textContent?.trim()
    )
    const ai = [
      'Overview',
      'Browse AI Content',
      'Country Explorer',
      'AI Music Intelligence',
      'AI Video Intelligence',
      'Content Opportunities',
      'Creative Briefs',
    ]
    for (const name of [...ai, 'Discover', 'Creators', 'Data sources'])
      expect(links).toContain(name)
    expect(links.indexOf('Overview')).toBeLessThan(links.indexOf('Discover'))
  })

  it('moves between AI pages and keeps the shared filters', async () => {
    const { screen, router } = await renderApp(
      '/ai?language=%5B%22kn%22%5D',
      api()
    )
    await expect
      .element(screen.getByText('Classification funnel'))
      .toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'AI workspace' })
    await userEvent.click(nav.getByRole('link', { name: 'Country Explorer' }))
    await expect
      .poll(() => router.state.location.pathname)
      .toBe('/ai/countries')
    expect(router.state.location.search).toMatchObject({ language: ['kn'] })
    await expect
      .element(
        screen.getByRole('heading', { level: 1, name: 'Country Explorer' })
      )
      .toBeInTheDocument()
  })
})

describe('AI overview', () => {
  it('shows the classification funnel with every status, including zeros', async () => {
    const { screen } = await renderApp(
      '/ai',
      api({
        '/api/v1/ai/summary': json({
          ...SUMMARY,
          by_status: SUMMARY.by_status.filter((c) => c.key !== 'NOT_AI'),
        }),
      })
    )
    const funnel = screen.getByRole('region', { name: 'Classification funnel' })
    await expect
      .element(funnel.getByText('1. Collected videos examined'))
      .toBeInTheDocument()
    await expect
      .element(funnel.getByText('14', { exact: true }))
      .toBeInTheDocument()
    await expect
      .element(funnel.getByText('13', { exact: true }))
      .toBeInTheDocument()
    const statuses = screen.getByRole('list', {
      name: 'Classified videos by AI status',
    })
    // a real zero is written as 0
    await expect
      .element(statuses.getByRole('link', { name: /Not AI \(creator says\)/ }))
      .toHaveTextContent(/says\)0/)
    await expect
      .element(statuses.getByRole('link', { name: /Unclassified/ }))
      .toHaveTextContent(/Unclassified4/)
  })

  it('opens a status group in AI Discover when it is selected', async () => {
    const { screen, router, calls } = await renderApp('/ai', api())
    const statuses = screen.getByRole('list', {
      name: 'Classified videos by AI status',
    })
    await userEvent.click(statuses.getByRole('link', { name: /Possibly AI/ }))
    await expect.poll(() => router.state.location.pathname).toBe('/ai/discover')
    await expect
      .poll(() =>
        sent(calls, '/api/v1/ai/content').some(
          (q) => q.getAll('status').join() === 'POSSIBLY_AI'
        )
      )
      .toBe(true)
  })

  it('marks platform-verified Shorts as unavailable, never as zero', async () => {
    const { screen } = await renderApp('/ai', api())
    const format = screen.getByRole('region', { name: 'Format' })
    await expect
      .element(format.getByText('Platform-verified Shorts'))
      .toBeInTheDocument()
    await expect
      .element(format.getByText('Unavailable', { exact: true }))
      .toBeInTheDocument()
    await expect.element(format.getByText(/no Shorts flag/)).toBeInTheDocument()
    await expect
      .element(format.getByText('Short-form by duration (≤ 3 min)'))
      .toBeInTheDocument()
  })

  it('explains a real zero and offers the groups that do have videos', async () => {
    const { screen } = await renderApp(
      '/ai',
      api({
        '/api/v1/ai/summary': json({
          ...SUMMARY,
          matching: 0,
          by_category: [],
          by_format: [],
          recent: [],
        }),
      })
    )
    await expect
      .element(screen.getByText('No video matches these filters'))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText(/This is a real zero, not missing data/))
      .toBeInTheDocument()
    await expect
      .element(screen.getByRole('link', { name: /Inspect 1 Possibly AI/ }))
      .toBeInTheDocument()
    await expect
      .element(screen.getByRole('link', { name: /Inspect 4 Unclassified/ }))
      .toBeInTheDocument()
  })

  it('asks for the default AI statuses only, and shows no restricted value', async () => {
    const { screen, calls } = await renderApp('/ai', api())
    await expect
      .element(screen.getByText('Classification funnel'))
      .toBeInTheDocument()
    const q = params(calls, '/api/v1/ai/summary')
    expect(q.get('period')).toBe('30d')
    expect(q.getAll('status')).toEqual([]) // the API default: confirmed and likely
    const text = document.body.textContent ?? ''
    // "ViralTrack" is the product name; the word "viral" on its own must not appear
    for (const pattern of [...FORBIDDEN_TEXT, /\bscore\b/i, /\bviral\b/i])
      expect(text).not.toMatch(pattern)
  })

  it('labels real data as real', async () => {
    const { screen } = await renderApp(
      '/ai',
      api({
        '/api/v1/ai/summary': json({
          ...SUMMARY,
          meta: meta({ demo: false, data_origin: 'real_provider_data' }),
        }),
      })
    )
    await expect
      .element(screen.getByText('Real collected data'))
      .toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/TEST data|DEMO data/)
  })

  it('marks a corpus collected more than a day ago as stale', async () => {
    const old = '2026-01-01T00:00:00Z'
    const { screen } = await renderApp(
      '/ai',
      api({
        '/api/v1/ai/summary': json({
          ...SUMMARY,
          meta: meta({ collected_from: old, collected_to: old }),
        }),
      })
    )
    await expect
      .element(screen.getByText('Stale: collected over 24 h ago').first())
      .toBeInTheDocument()
  })
})

describe('AI filters', () => {
  it('keeps content filters collapsed until opened, then sends status and category', async () => {
    const { screen, calls } = await renderApp('/ai', api())
    await expect
      .element(screen.getByText('Classification funnel'))
      .toBeInTheDocument()
    await expect
      .element(screen.getByRole('button', { name: 'Possibly AI' }))
      .not.toBeInTheDocument()
    await openContent(screen)
    await userEvent.click(screen.getByRole('button', { name: 'Possibly AI' }))
    await expect
      .poll(() => params(calls, '/api/v1/ai/summary').getAll('status'))
      .toEqual(['CONFIRMED_AI', 'LIKELY_AI', 'POSSIBLY_AI'])
    await userEvent.click(
      screen.getByRole('button', { name: 'AI music / audio' })
    )
    await expect
      .poll(() => params(calls, '/api/v1/ai/summary').getAll('category'))
      .toEqual(['AI_MUSIC_AUDIO'])
  })

  it('offers duration-based short-form, long-form and live, and disables verified Shorts', async () => {
    const { screen, calls } = await renderApp('/ai', api())
    await expect
      .element(screen.getByText('Classification funnel'))
      .toBeInTheDocument()
    await expect
      .element(screen.getByRole('radio', { name: 'Verified Shorts' }))
      .toBeDisabled()
    await userEvent.click(screen.getByRole('radio', { name: 'Long-form' }))
    await expect
      .poll(() => params(calls, '/api/v1/ai/summary').getAll('format'))
      .toEqual(['long_form'])
    await userEvent.click(screen.getByRole('radio', { name: 'Live / other' }))
    await expect
      .poll(() => params(calls, '/api/v1/ai/summary').getAll('format'))
      .toEqual(['live', 'unknown'])
  })

  it('counts active filters, removes one, and resets them all', async () => {
    const { screen, router } = await renderApp('/ai', api())
    const count = screen.getByTestId('active-filter-count')
    await expect.element(count).toHaveTextContent(/No filters/)
    await userEvent.click(screen.getByRole('button', { name: 'Language: all' }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Kannada/ }))
    await userEvent.keyboard('{Escape}')
    await userEvent.click(screen.getByRole('radio', { name: 'Long-form' }))
    await expect.element(count).toHaveTextContent('2 active filters')
    await userEvent.click(
      screen.getByRole('button', { name: 'Remove filter Language: Kannada' })
    )
    await expect.element(count).toHaveTextContent('1 active filter')
    await expect
      .poll(() => router.state.location.search)
      .toEqual({ format: 'long_form' })
    await userEvent.click(screen.getByRole('button', { name: 'Reset filters' }))
    await expect.element(count).toHaveTextContent(/No filters/)
  })

  it('filters by creator country or by discovery market, never mixing the two', async () => {
    const { screen, calls } = await renderApp('/ai', api())
    await expect
      .element(screen.getByText('Classification funnel'))
      .toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Country: all' }))
    await userEvent.click(screen.getByRole('checkbox', { name: /India/ }))
    await expect
      .poll(() =>
        sent(calls, '/api/v1/ai/summary').some(
          (q) => q.getAll('creator_country').join() === 'IN'
        )
      )
      .toBe(true)
    await userEvent.keyboard('{Escape}')
    const before = calls.length
    await userEvent.click(
      screen.getByRole('radio', { name: 'Discovery market' })
    )
    await userEvent.click(screen.getByRole('button', { name: 'Country: all' }))
    await userEvent.click(screen.getByRole('checkbox', { name: /South Korea/ }))
    await expect
      .poll(() =>
        sent(calls, '/api/v1/ai/summary', before).some(
          (q) => q.getAll('discovery_country').join() === 'KR'
        )
      )
      .toBe(true)
    expect(
      sent(calls, '/api/v1/ai/summary', before).some((q) =>
        q.has('creator_country')
      )
    ).toBe(false)
    await userEvent.keyboard('{Escape}')
  })

  it('filters by language, including several at once', async () => {
    const { screen, calls } = await renderApp('/ai', api())
    await expect
      .element(screen.getByText('Classification funnel'))
      .toBeInTheDocument()
    const has = (langs: string) =>
      sent(calls, '/api/v1/ai/summary').some(
        (q) => q.getAll('language').join() === langs
      )
    await userEvent.click(screen.getByRole('button', { name: 'Language: all' }))
    const picker = screen.getByRole('group', {
      name: 'Language in the collected corpus (items)',
    })
    await userEvent.click(picker.getByRole('checkbox', { name: /Kannada/ }))
    await expect.poll(() => has('kn')).toBe(true)
    // In the test iframe the re-anchored popover can sit outside the viewport, so the second choice is a
    // DOM click. A real browser at 1280 px was checked separately: both clicks land (language=["hi","en"]).
    ;(
      picker.getByRole('checkbox', { name: /English/ }).element() as HTMLElement
    ).click()
    await expect.poll(() => has('kn,en')).toBe(true)
  })
})

describe('AI Discover and the focused pages', () => {
  it('shows status, confidence, evidence, country source, language, format, date and source link', async () => {
    const { screen } = await renderApp('/ai/discover', api())
    const card = screen.getByRole('article', {
      name: 'Amma Magana Haadu | AI music video',
    })
    await expect.element(card.getByText('Likely AI')).toBeInTheDocument()
    await expect.element(card.getByText('Medium evidence')).toBeInTheDocument()
    await expect
      .element(card.getByText(/generation tool named: kling/).first())
      .toBeInTheDocument()
    await expect
      .element(card.getByText('India (declared by the creator)'))
      .toBeInTheDocument()
    await expect.element(card.getByText('Kannada')).toBeInTheDocument()
    await expect
      .element(card.getByText('Short-form by duration (≤ 3 min)'))
      .toBeInTheDocument()
    await expect
      .element(card.getByRole('link', { name: /Open source/ }))
      .toHaveAttribute('href', 'https://www.youtube.com/watch?v=aiKnMusic01')
    const other = screen.getByRole('article', { name: 'Lo-fi beats to study' })
    await expect
      .element(other.getByText('No regional collection'))
      .toBeInTheDocument()
    expect(screen.container.querySelector('img')).toBeNull()
  })

  it('analyses an opportunity from a card with its category, format, language and country', async () => {
    const { screen, router, calls } = await renderApp('/ai/discover', api())
    const card = screen.getByRole('article', {
      name: 'Amma Magana Haadu | AI music video',
    })
    await userEvent.click(
      card.getByRole('link', { name: 'Analyze opportunity' })
    )
    await expect
      .poll(() => router.state.location.pathname)
      .toBe('/ai/opportunities')
    await expect
      .poll(() => {
        const all = sent(calls, '/api/v1/ai/opportunities')
        const q = all[all.length - 1]
        return q
          ? [
              q.getAll('category').join(),
              q.getAll('format').join(),
              q.getAll('language').join(),
              q.getAll('creator_country').join(),
            ]
          : null
      })
      .toEqual(['AI_MUSIC_VIDEO', 'short_form', 'kn', 'IN'])
  })

  it('sends only the approved sorts', async () => {
    const { screen, calls } = await renderApp('/ai/discover', api())
    await expect
      .element(screen.getByText('2 matching videos'))
      .toBeInTheDocument()
    expect(params(calls, '/api/v1/ai/content').get('sort')).toBe('views')
    await userEvent.click(screen.getByRole('radio', { name: 'Newest' }))
    await expect
      .poll(() => params(calls, '/api/v1/ai/content').get('sort'))
      .toBe('published_at')
  })

  it('limits AI Music Intelligence to music categories, with a tab per category', async () => {
    const { screen, calls } = await renderApp('/ai/music', api())
    await expect
      .element(
        screen.getByRole('heading', { level: 1, name: 'AI Music Intelligence' })
      )
      .toBeInTheDocument()
    await expect
      .poll(() => params(calls, '/api/v1/ai/content').getAll('category'))
      .toEqual(['AI_MUSIC_VIDEO', 'AI_MUSIC_AUDIO'])
    await userEvent.click(
      screen.getByRole('radio', { name: /AI music video \(3\)/ })
    )
    await expect
      .poll(() => params(calls, '/api/v1/ai/content').getAll('category'))
      .toEqual(['AI_MUSIC_VIDEO'])
  })

  it('limits AI Video Intelligence to soundtrack and story categories', async () => {
    const { screen, calls } = await renderApp('/ai/video', api())
    await expect
      .element(
        screen.getByRole('heading', { level: 1, name: 'AI Video Intelligence' })
      )
      .toBeInTheDocument()
    await expect
      .poll(() => params(calls, '/api/v1/ai/content').getAll('category'))
      .toEqual(['AI_VIDEO_WITH_MUSIC', 'AI_NORMAL_VIDEO'])
  })

  it('explains an empty result instead of showing zeros', async () => {
    const { screen } = await renderApp(
      '/ai/discover',
      api({
        '/api/v1/ai/content': json({
          data: [],
          meta: { ...CONTENT.meta, returned: 0, total: 0 },
        }),
      })
    )
    await expect
      .element(screen.getByText('No collected video matches these filters'))
      .toBeInTheDocument()
  })

  it('shows a loading state, then an error with an explicit retry', async () => {
    const pending = await renderApp(
      '/ai/discover',
      api({
        '/api/v1/ai/content': () => new Promise<Response>(() => {}) as never,
      })
    )
    await expect
      .element(
        pending.screen.getByRole('status', { name: 'Loading AI videos' })
      )
      .toBeInTheDocument()
    vi.unstubAllGlobals()
    const { screen, calls } = await renderApp(
      '/ai/discover',
      api({
        '/api/v1/ai/content': json(
          {
            error: { code: 'provider_unavailable', message: 'x', details: [] },
          },
          503
        ),
      })
    )
    await expect
      .element(screen.getByText('The data source is unavailable'))
      .toBeInTheDocument()
    const count = () =>
      calls.filter((c) => c.startsWith('/api/v1/ai/content')).length
    expect(count()).toBe(1)
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await expect.poll(count).toBe(2)
  })
})

describe('Country Explorer', () => {
  it('starts worldwide, searches countries and shows a selected country', async () => {
    const { screen, calls } = await renderApp('/ai/countries', api())
    await expect
      .element(screen.getByText('Worldwide (the whole collected corpus)'))
      .toBeInTheDocument()
    const box = screen.getByRole('searchbox', { name: 'Search countries' })
    await userEvent.fill(box, 'united')
    const list = screen.getByRole('complementary', { name: 'Countries' })
    await expect
      .element(list.getByRole('button', { name: /United States/ }))
      .toBeInTheDocument()
    await expect
      .element(list.getByRole('button', { name: /India/ }))
      .not.toBeInTheDocument()
    await userEvent.fill(box, '')
    await userEvent.click(list.getByRole('button', { name: /India/ }))
    await expect
      .element(screen.getByRole('heading', { level: 2, name: 'India' }))
      .toBeInTheDocument()
    await expect.element(screen.getByText('2026-11-20')).toBeInTheDocument()
    // the explorer lists every country; selecting one never filters the list request
    expect(
      sent(calls, '/api/v1/ai/countries').some((q) => q.has('country'))
    ).toBe(false)
  })

  it('compares two countries side by side and says the counts are not market share', async () => {
    const { screen } = await renderApp('/ai/countries', api())
    const list = screen.getByRole('complementary', { name: 'Countries' })
    await userEvent.click(list.getByRole('button', { name: /India/ }))
    await userEvent.click(list.getByRole('button', { name: /United States/ }))
    await expect
      .element(screen.getByRole('heading', { level: 2, name: 'India' }))
      .toBeInTheDocument()
    await expect
      .element(screen.getByRole('heading', { level: 2, name: 'United States' }))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText(/not any country's market/).first())
      .toBeInTheDocument()
  })
})

describe('Opportunities and creative briefs', () => {
  it('shows opportunities with their evidence and an original brief with the rights checklist', async () => {
    const { screen } = await renderApp('/ai/opportunities', api())
    await expect.element(screen.getByText(/3 short-form/)).toBeInTheDocument()
    await expect
      .element(screen.getByText('3 supporting videos'))
      .toBeInTheDocument()
    await userEvent.click(screen.getByText('Original creative brief'))
    await expect
      .element(screen.getByText(/no language model was used/))
      .toBeInTheDocument()
    await expect
      .element(screen.getByRole('checkbox', { name: /No cloned voice/ }))
      .toBeInTheDocument()
  })

  it('lists the briefs open and copies one as text without any network request', async () => {
    const writeText = vi.fn(async (_text: string) => {})
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    const { screen, calls } = await renderApp('/ai/briefs', api())
    await expect
      .element(screen.getByText('Rights and originality checklist'))
      .toBeVisible()
    const before = calls.length
    await userEvent.click(
      screen.getByRole('button', { name: 'Copy brief as text' })
    )
    await expect
      .element(screen.getByRole('button', { name: 'Copied' }))
      .toBeInTheDocument()
    expect(writeText).toHaveBeenCalledWith(
      expect.stringContaining('Rights and originality checklist:')
    )
    expect(calls.length).toBe(before)
  })

  it('explains when no opportunity has enough evidence', async () => {
    const { screen } = await renderApp(
      '/ai/opportunities',
      api({ '/api/v1/ai/opportunities': json({ ...OPPS, data: [] }) })
    )
    await expect
      .element(screen.getByText(/No group of at least 3 matching AI videos/))
      .toBeInTheDocument()
  })
})

describe('AI accessibility, themes and layout', () => {
  it.each(PAGES)(
    'has no serious accessibility violation on %s',
    async (path) => {
      const { screen } = await renderApp(path, api())
      await expect
        .element(screen.getByText('TEST data').first())
        .toBeInTheDocument()
      expect(await seriousViolations(screen.container)).toEqual([])
    }
  )

  it.each(['/ai', '/ai/discover', '/ai/countries'])(
    'has no serious accessibility violation in the dark theme on %s',
    async (path) => {
      document.cookie = 'vite-ui-theme=dark; path=/'
      try {
        const { screen } = await renderApp(path, api())
        await expect
          .element(screen.getByText('TEST data').first())
          .toBeInTheDocument()
        await expect
          .poll(() => document.documentElement.classList.contains('dark'))
          .toBe(true)
        expect(await seriousViolations(screen.container)).toEqual([])
      } finally {
        document.cookie = 'vite-ui-theme=; path=/; max-age=0'
      }
    }
  )

  it.each([
    [375, 800, 'phone'],
    [768, 1024, 'tablet'],
    [1280, 900, 'desktop'],
  ])(
    'fits a %ipx wide (%s) screen without horizontal page scrolling',
    async (width, height) => {
      await browserPage.viewport(width as number, height as number)
      for (const path of ['/ai', '/ai/discover', '/ai/countries']) {
        const { screen } = await renderApp(path, api())
        await expect
          .element(screen.getByText('TEST data').first())
          .toBeInTheDocument()
        expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(
          width as number
        )
        vi.unstubAllGlobals()
      }
    }
  )

  it('makes no request outside the local API', async () => {
    const calls: string[] = []
    for (const path of PAGES) {
      const r = await renderApp(path, api())
      await expect
        .element(r.screen.getByText('TEST data').first())
        .toBeInTheDocument()
      calls.push(...r.calls)
      vi.unstubAllGlobals()
    }
    expect(calls.length).toBeGreaterThan(0)
    expect(calls.every((c) => c.startsWith('/api/v1/'))).toBe(true)
  })
})
