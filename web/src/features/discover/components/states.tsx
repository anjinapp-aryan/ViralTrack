import { CloudOff, RefreshCw, SearchX, TriangleAlert } from 'lucide-react'
import { ApiError } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { RESULTS_GRID } from './grid'

export function ResultsSkeleton({ count = 12 }: { count?: number }) {
  return (
    <div role='status' aria-label='Loading videos' className={RESULTS_GRID}>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className='overflow-hidden rounded-xl border bg-card'>
          <Skeleton className='aspect-video w-full rounded-none' />
          <div className='flex flex-col gap-2 p-3.5'>
            <Skeleton className='h-4 w-11/12' />
            <Skeleton className='h-4 w-2/3' />
            <Skeleton className='h-3 w-1/3' />
            <Skeleton className='mt-2 h-4 w-1/2' />
          </div>
        </div>
      ))}
    </div>
  )
}

function Panel({
  icon,
  title,
  children,
  action,
}: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <div className='flex flex-col items-center rounded-xl border border-dashed px-6 py-14 text-center'>
      <div className='grid size-11 place-items-center rounded-full bg-muted text-muted-foreground'>
        {icon}
      </div>
      <h2 className='mt-4 text-base font-semibold'>{title}</h2>
      <div className='mt-1 max-w-md text-sm text-muted-foreground'>
        {children}
      </div>
      {action && <div className='mt-5'>{action}</div>}
    </div>
  )
}

export function EmptyResults({ onReset }: { onReset: () => void }) {
  return (
    <Panel
      icon={<SearchX aria-hidden className='size-5' />}
      title='No videos match these filters'
      action={
        <Button variant='outline' onClick={onReset}>
          Reset filters
        </Button>
      }
    >
      Nothing was hidden: this is what the collected data contains. Try a longer
      period, a larger creator size or a different search.
    </Panel>
  )
}

const MESSAGES: Record<string, { title: string; body: string }> = {
  api_unreachable: {
    title: 'The ViralTrack API is not running',
    body: 'Start it with `python -m viraltrack.api` (port 8000), then retry. See web/README.md.',
  },
  provider_unavailable: {
    title: 'The data source is unavailable',
    body: 'The API is running but cannot reach the local foundation. Start the foundation, then retry.',
  },
  provider_timeout: {
    title: 'The data source did not answer in time',
    body: 'The local foundation is slow or busy. Retry in a moment.',
  },
  provider_error: {
    title: 'The data source returned something unusable',
    body: 'The answer was rejected by the API. Details are in the API log.',
  },
  page_out_of_range: {
    title: 'That page is beyond the result window',
    body: 'Results are limited to the first 1,000 videos. Narrow the filters instead.',
  },
  platform_unavailable: {
    title: 'This platform is not available',
    body: 'There is no approved data source for it yet.',
  },
}

/** Retry is always a click: nothing is repeated automatically. */
export function ErrorResults({
  error,
  onRetry,
  retrying,
}: {
  error: unknown
  onRetry: () => void
  retrying: boolean
}) {
  const code = error instanceof ApiError ? error.code : 'unknown'
  const known = MESSAGES[code]
  const unreachable = code === 'api_unreachable'
  return (
    <Panel
      icon={
        unreachable ? (
          <CloudOff aria-hidden className='size-5' />
        ) : (
          <TriangleAlert aria-hidden className='size-5' />
        )
      }
      title={known?.title ?? 'Something went wrong'}
      action={
        <Button variant='outline' onClick={onRetry} disabled={retrying}>
          <RefreshCw aria-hidden className={retrying ? 'animate-spin' : ''} />
          Retry
        </Button>
      }
    >
      <p>
        {known?.body ??
          (error instanceof Error ? error.message : 'The request failed.')}
      </p>
      {error instanceof ApiError && error.status > 0 && (
        <p className='mt-2 font-mono text-xs'>
          {error.status} · {error.code}
        </p>
      )}
    </Panel>
  )
}
