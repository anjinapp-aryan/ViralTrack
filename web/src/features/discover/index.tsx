import { useState } from 'react'
import { getRouteApi } from '@tanstack/react-router'
import type { Video } from '@/lib/api/client'
import { useCapabilities, useDiscover } from '@/lib/api/queries'
import { cn } from '@/lib/utils'
import { AppHeader } from '@/components/layout/app-header'
import { Main } from '@/components/layout/main'
import { FilterBar } from './components/filter-bar'
import { RESULTS_GRID } from './components/grid'
import { Pager } from './components/pager'
import { PlatformSwitcher } from './components/platform-switcher'
import { QuickView } from './components/quick-view'
import { ResultsHeader } from './components/results-header'
import {
  EmptyResults,
  ErrorResults,
  ResultsSkeleton,
} from './components/states'
import { VideoCard } from './components/video-card'
import { type DiscoverSearch, toApiParams } from './search-params'

const route = getRouteApi('/_app/')

export function Discover() {
  const search = route.useSearch()
  const navigate = route.useNavigate()
  const capabilities = useCapabilities()
  const results = useDiscover(toApiParams(search))
  const [open, setOpen] = useState<Video | null>(null)

  const update = (patch: Partial<DiscoverSearch>) =>
    navigate({
      search: (prev) => ({ ...prev, ...patch, page: patch.page ?? undefined }),
    })
  const reset = () => navigate({ search: {} })

  const data = results.data
  return (
    <>
      <AppHeader />
      <Main
        fluid
        className='mx-auto flex w-full max-w-[1680px] flex-col gap-5 px-4 py-6 lg:px-6'
      >
        <div className='flex flex-wrap items-end justify-between gap-3'>
          <div>
            <h1 className='text-2xl font-bold tracking-tight lg:text-[1.7rem]'>
              Discover
            </h1>
            <p className='mt-1 text-sm text-muted-foreground'>
              Videos in the collected corpus, ordered by what the platform
              reports. No predictions and no hidden scores.
            </p>
          </div>
          <PlatformSwitcher platforms={capabilities.data?.platforms} />
        </div>

        <FilterBar
          key={search.q ?? ''}
          search={search}
          capabilities={capabilities.data}
          onChange={update}
          onReset={reset}
        />

        {results.isPending ? (
          <ResultsSkeleton />
        ) : results.isError && !data ? (
          <ErrorResults
            error={results.error}
            onRetry={() => results.refetch()}
            retrying={results.isFetching}
          />
        ) : data ? (
          <section
            aria-label='Results'
            aria-busy={results.isFetching}
            className='flex flex-col gap-4'
          >
            <h2 className='sr-only'>Results</h2>
            <ResultsHeader meta={data.meta} items={data.data} />
            {results.isError && (
              <ErrorResults
                error={results.error}
                onRetry={() => results.refetch()}
                retrying={results.isFetching}
              />
            )}
            {data.data.length === 0 ? (
              <EmptyResults onReset={reset} />
            ) : (
              <div
                className={cn(
                  RESULTS_GRID,
                  'transition-opacity',
                  results.isPlaceholderData && 'opacity-60'
                )}
              >
                {data.data.map((v) => (
                  <VideoCard key={v.id} video={v} onOpen={setOpen} />
                ))}
              </div>
            )}
            <Pager
              meta={data.meta}
              busy={results.isFetching}
              onPage={(page) => {
                update({ page })
                window.scrollTo({ top: 0 })
              }}
            />
          </section>
        ) : null}
      </Main>
      <QuickView video={open} onClose={() => setOpen(null)} />
    </>
  )
}
