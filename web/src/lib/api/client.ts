/**
 * The only way the web UI reaches data: the local ViralTrack API (D5), typed from
 * docs/api/openapi-v1.json by openapi-typescript (`pnpm api:types`). No response type is written by hand.
 *
 * Requests are same-origin (`/api/v1/...`): the Vite dev and preview servers proxy `/api` to the API on
 * 127.0.0.1, so CORS stays closed on the API. The foundation is never called from the browser.
 */
import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

type Schemas = components['schemas']
export type Video = Schemas['Video']
export type MetricValue = Schemas['MetricValue']
export type PageMeta = Schemas['PageMeta']
export type VideoPage = Schemas['Page_Video_']
export type Capabilities = Schemas['CapabilitiesOut']
export type PlatformInfo = Schemas['PlatformOut']
export type Readiness = Schemas['HealthOut']
export type DiscoverParams = NonNullable<
  paths['/api/v1/discover']['get']['parameters']['query']
>

// `fetch` is looked up on every request (not captured once), so the page always uses the current one.
export const api = createClient<paths>({
  baseUrl: '',
  fetch: (request) => globalThis.fetch(request),
})

/** A failed API call. `status` 0 means the API could not be reached at all. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response }

/** Returns the data or throws an `ApiError` built from the API's error envelope. Never retries. */
export async function unwrap<T>(request: Promise<Result<T>>): Promise<T> {
  let result: Result<T>
  try {
    result = await request
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError')
      throw cause
    throw new ApiError(
      0,
      'api_unreachable',
      'The ViralTrack API is not reachable.'
    )
  }
  if (result.data !== undefined && result.response.ok) return result.data
  const envelope = result.error as
    { error?: { code?: string; message?: string } } | undefined
  throw new ApiError(
    result.response.status,
    envelope?.error?.code ?? 'http_error',
    envelope?.error?.message ?? `Request failed (${result.response.status})`
  )
}
