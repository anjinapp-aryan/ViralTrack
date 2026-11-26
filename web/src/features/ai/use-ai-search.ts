import {
  getRouteApi,
  useLocation,
  useNavigate,
  useRouter,
} from '@tanstack/react-router'
import type { AiSearch } from './search-params'

const route = getRouteApi('/_app/ai')

/**
 * The AI workspace's URL state, shared by every AI page: the search schema is defined once on the /ai layout
 * route. Updates stay on the current page; a filter change returns to page 1. A function patch reads the
 * router's latest location (including a navigation still in flight), so quick successive toggles never
 * drop a choice.
 */
export function useAiSearch() {
  const search = route.useSearch()
  const navigate = useNavigate()
  const router = useRouter()
  const { pathname } = useLocation()
  const go = (next: AiSearch) =>
    navigate({ to: pathname, search: next } as never)
  const update = (
    patch: Partial<AiSearch> | ((prev: AiSearch) => Partial<AiSearch>)
  ) => {
    const prev = router.latestLocation.search as AiSearch
    const p = typeof patch === 'function' ? patch(prev) : patch
    go({ ...prev, ...p, page: p.page ?? undefined })
  }
  const reset = () => go({})
  return { search, update, reset }
}
