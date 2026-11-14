import { getRouteApi } from '@tanstack/react-router'
import { RotateCcw } from 'lucide-react'
import { useCreators } from '@/lib/api/queries'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { AppHeader } from '@/components/layout/app-header'
import { Main } from '@/components/layout/main'
import { Pager } from '@/features/discover/components/pager'
import { ResultsHeader } from '@/features/discover/components/results-header'
import { ErrorResults } from '@/features/discover/components/states'
import {
  CREATOR_SIZES,
  DEFAULT_PERIOD,
  PERIODS,
} from '@/features/discover/search-params'
import { CreatorCard } from './components/creator-card'
import {
  CREATORS_GRID,
  CreatorsSkeleton,
  EmptyCreators,
} from './components/states'
import {
  CREATORS_WINDOW,
  activeCreatorFilters,
  toCreatorsParams,
  type CreatorsSearch,
} from './search-params'

const route = getRouteApi('/_app/creators/')

export function Creators() {
  const search = route.useSearch()
  const navigate = route.useNavigate()
  const results = useCreators(toCreatorsParams(search))
  const update = (patch: Partial<CreatorsSearch>) =>
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
        <div>
          <h1 className='text-2xl font-bold tracking-tight lg:text-[1.7rem]'>
            Creators
          </h1>
          <p className='mt-1 text-sm text-muted-foreground'>
            Creators of the videos in the collected corpus. This is not a
            creator index and not a ranking: the order follows the most viewed
            video of each creator in the selection.
          </p>
        </div>

        <div className='flex flex-wrap items-center gap-2 rounded-xl border bg-card/60 p-2 shadow-xs'>
          <Select
            value={search.period ?? DEFAULT_PERIOD}
            onValueChange={(v) => update({ period: v })}
          >
            <SelectTrigger
              aria-label='Period'
              className='h-9 w-[150px] bg-background'
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIODS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={search.creator_size ?? 'any'}
            onValueChange={(v) =>
              update({ creator_size: v as CreatorsSearch['creator_size'] })
            }
          >
            <SelectTrigger
              aria-label='Creator size'
              className='h-9 w-[180px] bg-background'
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CREATOR_SIZES.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {activeCreatorFilters(search) > 0 && (
            <Button variant='ghost' className='h-9' onClick={reset}>
              <RotateCcw aria-hidden />
              Reset
            </Button>
          )}
        </div>

        {results.isPending ? (
          <CreatorsSkeleton />
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
            <ResultsHeader meta={data.meta} items={[]} noun='creators' />
            {results.isError && (
              <ErrorResults
                error={results.error}
                onRetry={() => results.refetch()}
                retrying={results.isFetching}
              />
            )}
            {data.data.length === 0 ? (
              <EmptyCreators onReset={reset} />
            ) : (
              <div
                className={cn(
                  CREATORS_GRID,
                  'transition-opacity',
                  results.isPlaceholderData && 'opacity-60'
                )}
              >
                {data.data.map((entry) => (
                  <CreatorCard
                    key={entry.creator.id}
                    creator={entry.creator}
                    videosInResult={entry.videos_in_result}
                  />
                ))}
              </div>
            )}
            <Pager
              meta={data.meta}
              busy={results.isFetching}
              window={CREATORS_WINDOW}
              onPage={(page) => {
                update({ page })
                window.scrollTo({ top: 0 })
              }}
            />
          </section>
        ) : null}
      </Main>
    </>
  )
}
