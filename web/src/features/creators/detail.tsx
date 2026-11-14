import { useState } from 'react'
import { Link, getRouteApi } from '@tanstack/react-router'
import { ArrowLeft, ExternalLink, FlaskConical } from 'lucide-react'
import { ApiError, type Video } from '@/lib/api/client'
import { useCreator, useCreatorVideos } from '@/lib/api/queries'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { AppHeader } from '@/components/layout/app-header'
import { Main } from '@/components/layout/main'
import { RESULTS_GRID } from '@/features/discover/components/grid'
import { MetricValue } from '@/features/discover/components/metric-value'
import { Pager } from '@/features/discover/components/pager'
import { QuickView } from '@/features/discover/components/quick-view'
import { ResultsHeader } from '@/features/discover/components/results-header'
import {
  ErrorResults,
  ResultsSkeleton,
} from '@/features/discover/components/states'
import { VideoCard } from '@/features/discover/components/video-card'
import { PERIODS } from '@/features/discover/search-params'
import { Avatar } from './components/creator-card'
import { CreatorNotCollected, EmptyCreatorVideos } from './components/states'
import {
  CREATOR_VIDEOS_WINDOW,
  toCreatorVideosParams,
  type CreatorVideosSearch,
} from './search-params'

const route = getRouteApi('/_app/creators/$creatorId')

const ORIGIN_LABEL = { demo: 'DEMO data', test: 'TEST data' } as const

export function CreatorDetail() {
  const { creatorId } = route.useParams()
  const search = route.useSearch()
  const navigate = route.useNavigate()
  const creator = useCreator(creatorId)
  const params = toCreatorVideosParams(search)
  const notCollected =
    creator.error instanceof ApiError && creator.error.status === 404
  // the video list is requested only once the creator is known to exist
  const videos = useCreatorVideos(creatorId, params, Boolean(creator.data))
  const [open, setOpen] = useState<Video | null>(null)

  const update = (patch: Partial<CreatorVideosSearch>) =>
    navigate({
      search: (prev) => ({ ...prev, ...patch, page: patch.page ?? undefined }),
    })
  const profile = creator.data?.data
  const data = videos.data

  return (
    <>
      <AppHeader />
      <Main
        fluid
        className='mx-auto flex w-full max-w-[1680px] flex-col gap-6 px-4 py-6 lg:px-6'
      >
        <Button
          asChild
          variant='ghost'
          size='sm'
          className='-ms-2 w-fit text-muted-foreground'
        >
          <Link to='/creators'>
            <ArrowLeft aria-hidden />
            Creators
          </Link>
        </Button>

        {creator.isPending ? (
          <div className='flex items-center gap-4'>
            <Skeleton className='size-14 rounded-full' />
            <div className='space-y-2'>
              <Skeleton className='h-6 w-56' />
              <Skeleton className='h-4 w-32' />
            </div>
          </div>
        ) : notCollected ? (
          <CreatorNotCollected />
        ) : creator.isError || !profile ? (
          <ErrorResults
            error={creator.error}
            onRetry={() => creator.refetch()}
            retrying={creator.isFetching}
          />
        ) : (
          <>
            <header className='flex flex-wrap items-center gap-x-5 gap-y-3'>
              <Avatar creator={profile.creator} className='size-14 text-base' />
              <div className='min-w-0 flex-1'>
                <h1 className='truncate text-2xl font-bold tracking-tight lg:text-[1.7rem]'>
                  {profile.creator.name ?? 'Unknown creator'}
                </h1>
                <p className='text-sm text-muted-foreground'>
                  {profile.creator.handle ?? 'No handle reported'}
                </p>
              </div>
              <div className='flex flex-wrap items-center gap-2'>
                {profile.demo && (
                  <Badge
                    variant='outline'
                    className='border-violet-500/50 text-violet-700 dark:text-violet-300'
                  >
                    <FlaskConical aria-hidden />
                    {ORIGIN_LABEL[
                      profile.origin as keyof typeof ORIGIN_LABEL
                    ] ?? 'DEMO data'}
                  </Badge>
                )}
                {profile.creator.url && (
                  <Button asChild variant='outline' size='sm'>
                    <a
                      href={profile.creator.url}
                      target='_blank'
                      rel='noopener noreferrer'
                    >
                      Open on YouTube
                      <ExternalLink aria-hidden />
                    </a>
                  </Button>
                )}
              </div>
            </header>

            <section aria-label='Profile' className='flex flex-col gap-2'>
              <h2 className='sr-only'>Profile</h2>
              <div className='grid max-w-xl grid-cols-2 gap-2'>
                <MetricValue
                  label='Followers'
                  metric={profile.creator.followers}
                  missing='Hidden or not reported'
                />
                <MetricValue
                  label='Uploads on the platform'
                  metric={profile.creator.content_count}
                  missing='Not reported'
                />
              </div>
              <p className='text-xs text-muted-foreground'>
                The platform's own counts. A hidden or unreported value is shown
                as such, never as zero.
              </p>
            </section>

            <section aria-label='Videos' className='flex flex-col gap-4'>
              <h2 className='sr-only'>Videos</h2>
              <div className='flex flex-wrap items-center gap-2 rounded-xl border bg-card/60 p-2 shadow-xs'>
                <Select
                  value={search.period ?? 'all'}
                  onValueChange={(v) => update({ period: v })}
                >
                  <SelectTrigger
                    aria-label='Period'
                    className='h-9 w-[160px] bg-background'
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
              </div>

              {videos.isPending ? (
                <ResultsSkeleton count={8} />
              ) : videos.isError && !data ? (
                <ErrorResults
                  error={videos.error}
                  onRetry={() => videos.refetch()}
                  retrying={videos.isFetching}
                />
              ) : data ? (
                <div
                  aria-busy={videos.isFetching}
                  className='flex flex-col gap-4'
                >
                  <ResultsHeader
                    meta={data.meta}
                    items={data.data}
                    noun='videos'
                  />
                  {videos.isError && (
                    <ErrorResults
                      error={videos.error}
                      onRetry={() => videos.refetch()}
                      retrying={videos.isFetching}
                    />
                  )}
                  {data.data.length === 0 ? (
                    <EmptyCreatorVideos period={search.period ?? 'all'} />
                  ) : (
                    <div
                      className={cn(
                        RESULTS_GRID,
                        'transition-opacity',
                        videos.isPlaceholderData && 'opacity-60'
                      )}
                    >
                      {data.data.map((v) => (
                        <VideoCard key={v.id} video={v} onOpen={setOpen} />
                      ))}
                    </div>
                  )}
                  <Pager
                    meta={data.meta}
                    busy={videos.isFetching}
                    window={CREATOR_VIDEOS_WINDOW}
                    onPage={(page) => {
                      update({ page })
                      window.scrollTo({ top: 0 })
                    }}
                  />
                </div>
              ) : null}
            </section>
          </>
        )}
      </Main>
      <QuickView video={open} onClose={() => setOpen(null)} />
    </>
  )
}
