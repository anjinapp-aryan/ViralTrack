/**
 * TanStack Query hooks over the ViralTrack API. Every request is a free, read-only GET; even so nothing is
 * retried automatically (the QueryClient default is `retry: false`): a failure shows a Retry button.
 */
import { keepPreviousData, queryOptions, useQuery } from '@tanstack/react-query'
import {
  api,
  unwrap,
  type AiContentParams,
  type AiCountriesParams,
  type AiOpportunitiesParams,
  type AiSummaryParams,
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

// ---- AI Content Intelligence: read-only GETs, classified by the API at request time ----

export function useAiSummary(params: AiSummaryParams, enabled = true) {
  return useQuery({
    enabled,
    queryKey: ['ai-summary', params],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET('/api/v1/ai/summary', { params: { query: params }, signal })
      ),
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  })
}

export function useAiContent(params: AiContentParams, enabled = true) {
  return useQuery({
    enabled,
    queryKey: ['ai-content', params],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET('/api/v1/ai/content', { params: { query: params }, signal })
      ),
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  })
}

export function useAiCountries(params: AiCountriesParams, enabled = true) {
  return useQuery({
    enabled,
    queryKey: ['ai-countries', params],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET('/api/v1/ai/countries', { params: { query: params }, signal })
      ),
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  })
}

export function useAiOpportunities(
  params: AiOpportunitiesParams,
  enabled = true
) {
  return useQuery({
    enabled,
    queryKey: ['ai-opportunities', params],
    queryFn: ({ signal }) =>
      unwrap(
        api.GET('/api/v1/ai/opportunities', {
          params: { query: params },
          signal,
        })
      ),
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  })
}
