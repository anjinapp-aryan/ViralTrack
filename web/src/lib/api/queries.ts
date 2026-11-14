/**
 * TanStack Query hooks over the ViralTrack API. Every request is a free, read-only GET; even so nothing is
 * retried automatically (the QueryClient default is `retry: false`): a failure shows a Retry button.
 */
import { keepPreviousData, queryOptions, useQuery } from '@tanstack/react-query'
import {
  api,
  unwrap,
  type CreatorVideosParams,
  type CreatorsParams,
  type DiscoverParams,
  type Readiness,
} from './client'

const capabilitiesQuery = queryOptions({
  queryKey: ['capabilities'],
  queryFn: ({ signal }) => unwrap(api.GET('/api/v1/capabilities', { signal })),
  staleTime: 5 * 60 * 1000,
})

export function useCapabilities() {
  return useQuery(capabilitiesQuery)
}

export function useReadiness() {
  return useQuery({
    queryKey: ['readiness'],
    // 503 (not ready) still carries a readiness body, so read it instead of throwing
    queryFn: async ({ signal }) => {
      const { data, error, response } = await api.GET('/api/v1/health/ready', {
        signal,
      })
      if (data) return data
      if (response.status === 503 && error) return error as Readiness
      throw new Error(`readiness failed (${response.status})`)
    },
    staleTime: 60 * 1000,
  })
}

export function useCreators(params: CreatorsParams) {
  return useQuery({
    queryKey: ['creators', params],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET('/api/v1/creators', { params: { query: params }, signal })
      ),
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  })
}

export function useCreator(creatorId: string) {
  return useQuery({
    queryKey: ['creator', creatorId],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET('/api/v1/creators/{creator_id}', {
          params: { path: { creator_id: creatorId } },
          signal,
        })
      ),
    staleTime: 60 * 1000,
  })
}

export function useCreatorVideos(
  creatorId: string,
  params: CreatorVideosParams,
  enabled = true
) {
  return useQuery({
    enabled,
    queryKey: ['creator-videos', creatorId, params],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET('/api/v1/creators/{creator_id}/videos', {
          params: { path: { creator_id: creatorId }, query: params },
          signal,
        })
      ),
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  })
}

export function useDiscover(params: DiscoverParams) {
  return useQuery({
    queryKey: ['discover', params],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET('/api/v1/discover', { params: { query: params }, signal })
      ),
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  })
}
