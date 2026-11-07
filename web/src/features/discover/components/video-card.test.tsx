import { FORBIDDEN_TEXT, video } from '@/test-utils/fixtures'
import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { VideoCard } from './video-card'

describe('VideoCard', () => {
  it('shows title, creator, views, length and age', async () => {
    const screen = await render(<VideoCard video={video()} onOpen={vi.fn()} />)
    await expect
      .element(screen.getByText('Local LLM on a laptop in 10 minutes'))
      .toBeInTheDocument()
    await expect.element(screen.getByText('Tiny AI Lab')).toBeInTheDocument()
    await expect.element(screen.getByText('49K')).toBeInTheDocument()
    await expect.element(screen.getByText('10:03')).toBeInTheDocument()
  })

  it('never loads the platform thumbnail', async () => {
    const screen = await render(<VideoCard video={video()} onOpen={vi.fn()} />)
    expect(screen.container.querySelector('img')).toBeNull()
    expect(screen.container.innerHTML).not.toContain('ytimg')
    await expect
      .element(screen.getByText('Thumbnail not shown'))
      .toBeInTheDocument()
  })

  it('says a value is missing instead of showing 0', async () => {
    const v = video({
      metrics: { views: null, likes: null, comments: null },
      published_at: null,
      duration_seconds: null,
    })
    const screen = await render(<VideoCard video={v} onOpen={vi.fn()} />)
    await expect
      .element(screen.getByText('views not reported'))
      .toBeInTheDocument()
    await expect
      .element(screen.getByText('date not reported'))
      .toBeInTheDocument()
    expect(screen.container.textContent).not.toMatch(/\b0\b/)
  })

  it('shows no derived value, score or restricted label', async () => {
    const screen = await render(<VideoCard video={video()} onOpen={vi.fn()} />)
    const text = screen.container.textContent ?? ''
    for (const pattern of FORBIDDEN_TEXT) expect(text).not.toMatch(pattern)
    expect(text).not.toContain('5.7')
    expect(text).not.toContain('1,234')
  })

  it.each([
    [180, true],
    [181, false],
  ])('marks %i seconds as up to 3 min: %s', async (seconds, marked) => {
    const screen = await render(
      <VideoCard
        video={video({ duration_seconds: seconds })}
        onOpen={vi.fn()}
      />
    )
    expect(screen.container.textContent?.includes('≤ 3 min')).toBe(marked)
  })

  it('opens the details when activated with the keyboard', async () => {
    const onOpen = vi.fn()
    const screen = await render(<VideoCard video={video()} onOpen={onOpen} />)
    const button = screen.getByRole('button')
    ;(button.element() as HTMLButtonElement).focus()
    await expect.element(button).toHaveFocus()
    ;(button.element() as HTMLButtonElement).click()
    expect(onOpen).toHaveBeenCalledOnce()
  })
})
