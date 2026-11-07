/**
 * The Discover page as a whole: the real router, providers and components, with `fetch` answered by
 * synthetic API responses. Checks every state, the policy rules and accessibility (axe-core).
 */
import {
  FORBIDDEN_TEXT,
  capabilities,
  page,
  ready,
  video,
} from '@/test-utils/fixtures'
import { json, renderApp } from '@/test-utils/render-app'
import axe from 'axe-core'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'

const ITEMS = [
  video(),
  video({
    id: 'vid00002',
    title: 'History of the forgotten expedition',
    metrics: {
      views: { ...video().metrics.views!, value: 1_100_000 },
      likes: null,
      comments: null,
    },
    duration_seconds: 120,
  }),
]

function api(discover: Response | Error | (() => Response)) {
  return {
    '/api/v1/capabilities': json(capabilities),
    '/api/v1/health/ready': json(ready),
    '/api/v1/discover': discover,
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

describe('Discover page', () => {
  it('shows the results with the synthetic-data label', async () => {
    const { screen } = await renderApp(
      '/',
      api(() => json(page(ITEMS)))
    )
    await expect
      .element(screen.getByText('Local LLM on a laptop in 10 minutes'))
      .toBeInTheDocument()
    await expect.element(screen.getByText('TEST data')).toBeInTheDocument()
    await expect.element(screen.getByText(/Showing/)).toBeInTheDocument()
  })

  it('renders the skeleton while the request is pending', async () => {
    const { screen } = await renderApp('/', {
      ...api(json(page(ITEMS))),
      '/api/v1/discover': () => new Promise<Response>(() => {}) as never,
    })
    await expect
      .element(screen.getByRole('status', { name: 'Loading videos' }))
      .toBeInTheDocument()
  })

  it('calls only the ViralTrack API with an approved sort and a bounded creator size', async () => {
    const { screen, calls } = await renderApp('/', api(json(page(ITEMS))))
    await expect
      .element(screen.getByText('Tiny AI Lab').first())
      .toBeInTheDocument()
    expect(calls.every((c) => c.startsWith('/api/v1/'))).toBe(true)
    const discover = calls.find((c) => c.startsWith('/api/v1/discover'))!
    const q = new URL(discover, 'http://x').searchParams
    expect(q.get('sort')).toBe('views')
    expect(q.has('query')).toBe(false)
    expect(q.get('creator_size')).toBe('any')
    expect(q.get('platform')).toBe('youtube')
  })

  it('offers only the sorts the API reports as available', async () => {
    const { screen } = await renderApp('/', api(json(page(ITEMS))))
    const sort = screen.getByRole('radiogroup', { name: 'Sort by' })
    await expect.element(sort).toBeInTheDocument()
    const options = sort
      .getByRole('radio')
      .elements()
      .map((e) => e.textContent)
    expect(options).toEqual(['Most views', 'Newest'])
  })

  it('shows unavailable platforms as unavailable', async () => {
    const { screen } = await renderApp('/', api(json(page(ITEMS))))
    const group = screen.getByRole('group', { name: 'Platform' })
    await expect.element(group).toHaveTextContent(/Instagrams*Unavailable/)
    await expect.element(group).toHaveTextContent(/TikToks*Unavailable/)
    await expect.element(group).toHaveTextContent(/No approved data source/)
  })

  it('never shows a derived value, score or restricted label, in cards or details', async () => {
    const { screen } = await renderApp('/', api(json(page(ITEMS))))
    await expect
      .element(screen.getByText('Tiny AI Lab').first())
      .toBeInTheDocument()
    await userEvent.click(
      screen.getByRole('button', { name: /Local LLM on a laptop/ })
    )
    await expect.element(screen.getByRole('dialog')).toBeInTheDocument()
    const text = document.body.textContent ?? ''
    for (const pattern of FORBIDDEN_TEXT) expect(text).not.toMatch(pattern)
    expect(text).not.toContain('5.655')
    expect(text).not.toContain('1,234.5')
  })

  it('shows hidden likes as hidden in the details, never as 0', async () => {
    const { screen } = await renderApp('/', api(json(page(ITEMS))))
    await userEvent.click(
      screen.getByRole('button', { name: /History of the forgotten/ })
    )
    const dialog = screen.getByRole('dialog')
    await expect
      .element(dialog.getByText('Hidden or not reported').first())
      .toBeInTheDocument()
    expect(dialog.element().textContent).not.toMatch(/Likes\s*0/)
    const link = dialog.getByRole('link', { name: /Open on YouTube/ })
    await expect.element(link).toHaveAttribute('rel', 'noopener noreferrer')
    // keyboard: focus is inside the dialog and Escape closes it
    await expect
      .poll(() => dialog.element().contains(document.activeElement))
      .toBe(true)
    await userEvent.keyboard('{Escape}')
    await expect
      .poll(
        () =>
          document
            .querySelector('[role="dialog"]')
            ?.getAttribute('data-state') ?? 'gone',
        { timeout: 5000 }
      )
      .not.toBe('open')
  })

  it('shows an empty state that says nothing was hidden', async () => {
    const { screen } = await renderApp('/', api(json(page([]))))
    await expect
      .element(screen.getByText('No videos match these filters'))
      .toBeInTheDocument()
  })

  it('shows a data-source error and retries only when asked', async () => {
    const { screen, calls } = await renderApp(
      '/',
      api(
        json(
          {
            error: { code: 'provider_unavailable', message: 'x', details: [] },
          },
          503
        )
      )
    )
    await expect
      .element(screen.getByText('The data source is unavailable'))
      .toBeInTheDocument()
    const discoverCalls = () =>
      calls.filter((c) => c.startsWith('/api/v1/discover')).length
    await new Promise((r) => setTimeout(r, 300))
    expect(discoverCalls()).toBe(1)
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await expect.poll(discoverCalls).toBe(2)
  })

  it('explains how to start the API when it is not running', async () => {
    const { screen } = await renderApp('/', {
      '/api/v1/capabilities': new TypeError('Failed to fetch'),
      '/api/v1/health/ready': new TypeError('Failed to fetch'),
      '/api/v1/discover': new TypeError('Failed to fetch'),
    })
    await expect
      .element(screen.getByText('The ViralTrack API is not running'))
      .toBeInTheDocument()
  })

  it('topic search: no sort is sent, the order is shown as relevance and explained', async () => {
    const topicNote =
      'Topic search ranks the collected videos by how closely they match the search text, as the data source computes it. It does not exclude unrelated videos, and relevance is not a measure of popularity or performance.'
    const { screen, calls } = await renderApp(
      '/?q=llm',
      api(json(page(ITEMS, { sort: 'relevance', notes: [topicNote] })))
    )
    await expect
      .element(screen.getByRole('combobox', { name: 'Creator size' }))
      .toBeDisabled()
    // one order only: the sort choice is replaced by a fixed label
    await expect
      .element(screen.getByRole('radiogroup', { name: 'Sort by' }))
      .not.toBeInTheDocument()
    await expect
      .element(screen.getByText('Relevance to the topic'))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText(/minimum views do not apply/))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText(/relevance is not a measure of popularity/))
      .toBeInTheDocument()
    const discover = calls.find((c) => c.startsWith('/api/v1/discover'))!
    const q = new URL(discover, 'http://x').searchParams
    expect(q.get('query')).toBe('llm')
    expect(q.has('sort')).toBe(false)
    expect(q.has('creator_size')).toBe(false)
    const text = document.body.textContent ?? ''
    for (const word of [/\bviral\b/i, /breakout/i, /trending/i])
      expect(text).not.toMatch(word)
  })

  it('topic search never offers relevance as a browse sort', async () => {
    const { screen } = await renderApp('/', api(json(page(ITEMS))))
    const sort = screen.getByRole('radiogroup', { name: 'Sort by' })
    await expect.element(sort).toBeInTheDocument()
    expect(sort.element().textContent).not.toMatch(/relevance/i)
  })

  it('ignores a restricted sort put in the URL', async () => {
    const { calls, screen } = await renderApp(
      '/?sort=engagement_rate',
      api(json(page(ITEMS)))
    )
    await expect
      .element(screen.getByText('Tiny AI Lab').first())
      .toBeInTheDocument()
    const discover = calls.find((c) => c.startsWith('/api/v1/discover'))!
    expect(new URL(discover, 'http://x').searchParams.get('sort')).toBe('views')
  })

  it('moves to the next page within the API window', async () => {
    const { screen, calls } = await renderApp(
      '/',
      api(json(page(ITEMS, { has_more: true, total: 60 })))
    )
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await expect.poll(() => calls.some((c) => c.includes('page=2'))).toBe(true)
  })

  it('has no serious accessibility violations (light and dark)', async () => {
    const { screen } = await renderApp('/', api(json(page(ITEMS))))
    await expect
      .element(screen.getByText('Tiny AI Lab').first())
      .toBeInTheDocument()
    expect(await seriousViolations(document.body)).toEqual([])
    document.documentElement.classList.add('dark')
    expect(await seriousViolations(document.body)).toEqual([])
  })
})

describe('Data sources page', () => {
  it('lists platforms, sorts and the local-build notice from the API', async () => {
    const { screen } = await renderApp('/sources', api(json(page(ITEMS))))
    await expect
      .element(screen.getByText('Local development build'))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText(/connected/).first())
      .toBeInTheDocument()
    await expect
      .element(
        screen.getByText(/the foundation orders hidden like counts as zero/)
      )
      .toBeInTheDocument()
    expect(await seriousViolations(document.body)).toEqual([])
  })
})
