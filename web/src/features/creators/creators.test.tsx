/**
 * The Creators pages as a whole: the real router, providers and components, with `fetch` answered by synthetic
 * API responses. Checks every state, the policy rules, navigation and accessibility (axe-core).
 */
import {
  FORBIDDEN_TEXT,
  capabilities,
  creator,
  creatorsPage,
  page,
  ready,
  video,
} from '@/test-utils/fixtures'
import { json, renderApp } from '@/test-utils/render-app'
import axe from 'axe-core'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'

const ID = 'UC0000000000000000000a'
const OTHER = 'UC0000000000000000000b'
const LIST = creatorsPage([
  { creator: creator(), videos_in_result: 3 },
  {
    creator: creator({
      id: OTHER,
      name: 'Faceless History',
      handle: null,
      followers: null,
    }),
    videos_in_result: 1,
  },
])
const VIDEOS = page(
  [
    video({ id: 'newest01', title: 'Newest upload', creator: creator() }),
    video({
      id: 'older002',
      title: 'An older upload',
      published_at: '2026-09-01T10:00:00Z',
      creator: creator(),
      metrics: { views: null, likes: null, comments: null },
      duration_seconds: null,
    }),
  ],
  {
    sort: 'published_at',
    total: 2,
    notes: [
      'Newest collected videos of this creator, ordered by publication time.',
    ],
  }
)
const DETAIL = {
  data: {
    creator: creator(),
    origin: 'test' as const,
    demo: true,
    notes: [
      'Only the platform follower and upload counts are shown here, each null when hidden or not reported.',
    ],
  },
}

function api(extra: Record<string, Response | (() => Response) | Error> = {}) {
  return {
    '/api/v1/capabilities': json(capabilities),
    '/api/v1/health/ready': json(ready),
    '/api/v1/creators': json(LIST),
    [`/api/v1/creators/${ID}`]: json(DETAIL),
    [`/api/v1/creators/${ID}/videos`]: json(VIDEOS),
    ...extra,
  }
}

async function seriousViolations(root: Element) {
  const result = await axe.run(root, { resultTypes: ['violations'] })
  return result.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id}: ${v.nodes.length}`)
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.documentElement.className = ''
})

describe('Creators list', () => {
  it('shows creators with raw follower counts, the video counts and the synthetic-data label', async () => {
    const { screen } = await renderApp('/creators', api())
    await expect.element(screen.getByText('Tiny AI Lab')).toBeInTheDocument()
    await expect
      .element(screen.getByText('Faceless History'))
      .toBeInTheDocument()
    await expect.element(screen.getByText('800')).toBeInTheDocument()
    await expect
      .element(screen.getByText(/3\s*videos in these results/))
      .toBeInTheDocument()
    await expect.element(screen.getByText('TEST data')).toBeInTheDocument()
    await expect
      .element(screen.getByText(/most viewed video of each creator/))
      .toBeInTheDocument()
  })

  it('says the list is not a ranking and shows the API notes as written', async () => {
    const { screen } = await renderApp('/creators', api())
    await expect
      .element(screen.getByText(/not a creator index and not a ranking/))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText(/not their whole channel/))
      .toBeInTheDocument()
  })

  it('writes hidden followers and a missing handle out instead of showing 0', async () => {
    const { screen } = await renderApp('/creators', api())
    await expect
      .element(screen.getByText('followers hidden or not reported'))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText('No handle reported'))
      .toBeInTheDocument()
  })

  it('calls only the creators endpoint, with a bounded size and no sort, and requests no image', async () => {
    const { screen, calls } = await renderApp('/creators', api())
    await expect.element(screen.getByText('Tiny AI Lab')).toBeInTheDocument()
    expect(calls.every((c) => c.startsWith('/api/v1/'))).toBe(true)
    const q = new URL(
      calls.find((c) => c.startsWith('/api/v1/creators'))!,
      'http://x'
    ).searchParams
    expect(q.get('creator_size')).toBe('any')
    expect(q.get('page_size')).toBe('24')
    expect(q.has('sort')).toBe(false)
    expect(screen.container.querySelector('img')).toBeNull()
  })

  it('shows no score, ranking, derived value or restricted label', async () => {
    const { screen } = await renderApp('/creators', api())
    await expect.element(screen.getByText('Tiny AI Lab')).toBeInTheDocument()
    const text = document.body.textContent ?? ''
    for (const pattern of [
      ...FORBIDDEN_TEXT,
      /\bgrade\b/i,
      /momentum/i,
      /projection/i,
      /\bscore\b/i,
      /top creator/i,
    ])
      expect(text).not.toMatch(pattern)
  })

  it('shows an empty state that explains why a creator may be missing', async () => {
    const { screen } = await renderApp(
      '/creators',
      api({ '/api/v1/creators': json(creatorsPage([])) })
    )
    await expect
      .element(screen.getByText('No creators match these filters'))
      .toBeInTheDocument()
    await expect
      .element(
        screen.getByText(/appears only when one of their videos matches/)
      )
      .toBeInTheDocument()
  })

  it('shows a loading skeleton while the request is pending', async () => {
    const { screen } = await renderApp(
      '/creators',
      api({
        '/api/v1/creators': () => new Promise<Response>(() => {}) as never,
      })
    )
    await expect
      .element(screen.getByRole('status', { name: 'Loading creators' }))
      .toBeInTheDocument()
  })

  it('shows a data-source error and retries only when asked', async () => {
    const { screen, calls } = await renderApp(
      '/creators',
      api({
        '/api/v1/creators': json(
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
      calls.filter((c) => c.startsWith('/api/v1/creators')).length
    await new Promise((r) => setTimeout(r, 300))
    expect(count()).toBe(1)
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await expect.poll(count).toBe(2)
  })

  it('explains how to start the API when it is not running', async () => {
    const down = new TypeError('Failed to fetch')
    const { screen } = await renderApp('/creators', {
      '/api/v1/capabilities': down,
      '/api/v1/health/ready': down,
      '/api/v1/creators': down,
    })
    await expect
      .element(screen.getByText('The ViralTrack API is not running'))
      .toBeInTheDocument()
  })

  it('moves to the next page within the API window', async () => {
    const { screen, calls } = await renderApp(
      '/creators',
      api({
        '/api/v1/creators': json({
          ...LIST,
          meta: { ...LIST.meta, has_more: true, total: 60 },
        }),
      })
    )
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await expect.poll(() => calls.some((c) => c.includes('page=2'))).toBe(true)
  })

  it('ignores a sort or an unsupported size put in the URL', async () => {
    const { screen, calls } = await renderApp(
      '/creators?sort=views&creator_size=unlimited',
      api()
    )
    await expect.element(screen.getByText('Tiny AI Lab')).toBeInTheDocument()
    const q = new URL(
      calls.find((c) => c.startsWith('/api/v1/creators'))!,
      'http://x'
    ).searchParams
    expect(q.has('sort')).toBe(false)
    expect(q.get('creator_size')).toBe('any')
  })

  it('leads from a creator card to the creator page and requests their videos', async () => {
    const { screen, calls } = await renderApp('/creators', api())
    await expect.element(screen.getByText('Tiny AI Lab')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: /Tiny AI Lab/ }))
    await expect
      .element(screen.getByRole('heading', { name: 'Tiny AI Lab', level: 1 }))
      .toBeInTheDocument()
    expect(
      calls.some((c) => c.startsWith(`/api/v1/creators/${ID}/videos`))
    ).toBe(true)
  })

  it('has no serious accessibility violations (light and dark)', async () => {
    const { screen } = await renderApp('/creators', api())
    await expect.element(screen.getByText('Tiny AI Lab')).toBeInTheDocument()
    expect(await seriousViolations(document.body)).toEqual([])
    document.documentElement.classList.add('dark')
    expect(await seriousViolations(document.body)).toEqual([])
  })
})

describe('Creator detail', () => {
  it('shows the profile counts as raw values with their source, and nothing else about the creator', async () => {
    const { screen } = await renderApp(`/creators/${ID}`, api())
    await expect
      .element(screen.getByRole('heading', { name: 'Tiny AI Lab', level: 1 }))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText('@tinyailab').first())
      .toBeInTheDocument()
    await expect.element(screen.getByText('Followers')).toBeInTheDocument()
    await expect
      .element(screen.getByText('Uploads on the platform'))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText('TEST data').first())
      .toBeInTheDocument()
    const text = document.body.textContent ?? ''
    for (const pattern of [
      ...FORBIDDEN_TEXT,
      /\bgrade\b/i,
      /momentum/i,
      /projection/i,
      /revenue/i,
      /milestone/i,
      /\bYPP\b/,
    ])
      expect(text).not.toMatch(pattern)
  })

  it('lists the videos in the order the API gives (newest first) with the API notes', async () => {
    const { screen } = await renderApp(`/creators/${ID}`, api())
    await expect.element(screen.getByText('Newest upload')).toBeInTheDocument()
    const titles = screen
      .getByRole('region', { name: 'Videos' })
      .getByRole('heading', { level: 3 })
      .elements()
      .map((e) => e.textContent)
    expect(titles).toEqual(['Newest upload', 'An older upload'])
    await expect
      .element(screen.getByText(/ordered by publication time/))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText('Newest', { exact: true }))
      .toBeInTheDocument()
  })

  it('shows a missing view count as missing, never as 0', async () => {
    const { screen } = await renderApp(`/creators/${ID}`, api())
    await expect
      .element(screen.getByText('An older upload'))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText('views not reported'))
      .toBeInTheDocument()
  })

  it('shows hidden followers as hidden', async () => {
    const hidden = {
      data: { ...DETAIL.data, creator: creator({ followers: null }) },
    }
    const { screen } = await renderApp(
      `/creators/${ID}`,
      api({ [`/api/v1/creators/${ID}`]: json(hidden) })
    )
    await expect
      .element(screen.getByText('Hidden or not reported', { exact: true }))
      .toBeInTheDocument()
  })

  it('asks for all videos, 24 per page and no sort by default', async () => {
    const { screen, calls } = await renderApp(`/creators/${ID}`, api())
    await expect.element(screen.getByText('Newest upload')).toBeInTheDocument()
    const q = new URL(
      calls.find((c) => c.includes('/videos'))!,
      'http://x'
    ).searchParams
    expect(q.get('period')).toBe('all')
    expect(q.get('page_size')).toBe('24')
    expect(q.has('sort')).toBe(false)
  })

  it('forwards a valid period from the URL and ignores a sort', async () => {
    const { screen, calls } = await renderApp(
      `/creators/${ID}?period=7d&sort=views`,
      api()
    )
    await expect.element(screen.getByText('Newest upload')).toBeInTheDocument()
    const q = new URL(
      calls.find((c) => c.includes('/videos'))!,
      'http://x'
    ).searchParams
    expect(q.get('period')).toBe('7d')
    expect(q.has('sort')).toBe(false)
  })

  it('opens the video details with the creator provenance and no derived value', async () => {
    const { screen } = await renderApp(`/creators/${ID}`, api())
    await userEvent.click(screen.getByRole('button', { name: /Newest upload/ }))
    await expect.element(screen.getByRole('dialog')).toBeInTheDocument()
    const text = document.body.textContent ?? ''
    for (const pattern of FORBIDDEN_TEXT) expect(text).not.toMatch(pattern)
  })

  it('says a creator is not collected, and does not request their videos', async () => {
    const notFound = json(
      { error: { code: 'not_found', message: 'not found', details: [] } },
      404
    )
    const { screen, calls } = await renderApp(
      `/creators/${ID}`,
      api({
        [`/api/v1/creators/${ID}`]: notFound,
        [`/api/v1/creators/${ID}/videos`]: notFound,
      })
    )
    await expect
      .element(screen.getByText('This creator is not in the collected data'))
      .toBeInTheDocument()
    expect(calls.some((c) => c.includes('/videos'))).toBe(false)
  })

  it('shows an empty video list with an honest message', async () => {
    const { screen } = await renderApp(
      `/creators/${ID}`,
      api({
        [`/api/v1/creators/${ID}/videos`]: json(
          page([], { sort: 'published_at', total: 0 })
        ),
      })
    )
    await expect
      .element(screen.getByText('No videos collected for this creator'))
      .toBeInTheDocument()
  })

  it('keeps the profile when only the video list fails, and retries only when asked', async () => {
    const { screen, calls } = await renderApp(
      `/creators/${ID}`,
      api({
        [`/api/v1/creators/${ID}/videos`]: json(
          { error: { code: 'provider_timeout', message: 'x', details: [] } },
          504
        ),
      })
    )
    await expect
      .element(screen.getByText('The data source did not answer in time'))
      .toBeInTheDocument()
    await expect
      .element(screen.getByRole('heading', { name: 'Tiny AI Lab', level: 1 }))
      .toBeInTheDocument()
    const count = () => calls.filter((c) => c.includes('/videos')).length
    await new Promise((r) => setTimeout(r, 300))
    expect(count()).toBe(1)
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await expect.poll(count).toBe(2)
  })

  it('has no serious accessibility violations (light and dark)', async () => {
    const { screen } = await renderApp(`/creators/${ID}`, api())
    await expect.element(screen.getByText('Newest upload')).toBeInTheDocument()
    expect(await seriousViolations(document.body)).toEqual([])
    document.documentElement.classList.add('dark')
    expect(await seriousViolations(document.body)).toEqual([])
  })

  it('requests no image from the platform', async () => {
    const { screen } = await renderApp(`/creators/${ID}`, api())
    await expect.element(screen.getByText('Newest upload')).toBeInTheDocument()
    expect(screen.container.querySelector('img')).toBeNull()
  })
})
