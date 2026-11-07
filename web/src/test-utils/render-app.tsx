import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  RouterProvider,
  createMemoryHistory,
  createRouter,
} from '@tanstack/react-router'
import { routeTree } from '@/routeTree.gen'
import { vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { DirectionProvider } from '@/context/direction-provider'
import { FontProvider } from '@/context/font-provider'
import { ThemeProvider } from '@/context/theme-provider'

export type Reply = Response | (() => Response | Promise<Response>) | Error

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/**
 * Renders the real app (router, providers, routes) at `path`, with `fetch` replaced by a handler keyed by
 * API path. Returns the list of requested URLs so tests can assert what was (and was not) called.
 */
export async function renderApp(path: string, routes: Record<string, Reply>) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(
        input instanceof Request ? input.url : String(input),
        window.location.origin
      )
      calls.push(url.pathname + url.search)
      const reply = routes[url.pathname]
      if (reply === undefined)
        return json({ error: { code: 'not_found' } }, 404)
      if (reply instanceof Error) throw reply
      return typeof reply === 'function' ? reply() : reply.clone()
    })
  )
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  })
  const router = createRouter({
    routeTree,
    context: { queryClient },
    history: createMemoryHistory({ initialEntries: [path] }),
  })
  const screen = await render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <FontProvider>
          <DirectionProvider>
            <RouterProvider router={router} />
          </DirectionProvider>
        </FontProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
  return { screen, calls, router }
}
