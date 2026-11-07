import { describe, expect, it } from 'vitest'
import { ApiError, unwrap } from './client'

const response = (status: number) => new Response(null, { status })

describe('unwrap', () => {
  it('returns the data of a successful response', async () => {
    await expect(
      unwrap(Promise.resolve({ data: { ok: 1 }, response: response(200) }))
    ).resolves.toEqual({ ok: 1 })
  })

  it('turns the API error envelope into an ApiError with its code', async () => {
    const err = await unwrap(
      Promise.resolve({
        error: { error: { code: 'provider_unavailable', message: 'down' } },
        response: response(503),
      })
    ).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 503, code: 'provider_unavailable' })
  })

  it('reports an unreachable API as status 0, not as an empty result', async () => {
    const err = await unwrap(
      Promise.reject(new TypeError('Failed to fetch'))
    ).catch((e: unknown) => e)
    expect(err).toMatchObject({ status: 0, code: 'api_unreachable' })
  })

  it('rethrows an abort unchanged', async () => {
    const abort = new DOMException('aborted', 'AbortError')
    await expect(unwrap(Promise.reject(abort))).rejects.toBe(abort)
  })
})
