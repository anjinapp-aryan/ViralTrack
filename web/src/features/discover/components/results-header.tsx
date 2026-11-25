import { ArrowDownWideNarrow, Clock, FlaskConical, Info } from 'lucide-react'
import type { PageMeta, Video } from '@/lib/api/client'
import {
  absoluteDate,
  absoluteDateTime,
  fullNumber,
  relativeTime,
} from '@/lib/format'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { collectionSpan } from '../collection-span'

const ORDER_LABELS: Record<string, string> = {
  views: 'Most views',
  published_at: 'Newest',
  relevance: 'Relevance to the topic',
}

/** How many results, in which order, how fresh, and whether the data is synthetic. Notes are verbatim. */
export function ResultsHeader({
  meta,
  items,
  noun = 'videos',
}: {
  meta: PageMeta
  items: Video[]
  /** what is counted: videos on Discover, creators on the Creators page */
  noun?: string
}) {
  const start = (meta.page - 1) * meta.page_size + 1
  const end = start + meta.returned - 1
  const collected = collectionSpan(items)
  return (
    <div className='flex flex-col gap-3'>
      <div className='flex flex-wrap items-end justify-between gap-x-6 gap-y-2'>
        <div className='flex flex-wrap items-baseline gap-x-3 gap-y-1'>
          <p className='text-lg font-semibold tracking-tight'>
            {meta.total != null ? (
              <>
                <span className='tabular-nums'>{fullNumber(meta.total)}</span>{' '}
                {noun}
              </>
            ) : (
              <span className='capitalize'>{noun}</span>
            )}
          </p>
          {meta.returned > 0 && (
            <p className='text-sm text-muted-foreground'>
              Showing{' '}
              <span className='text-foreground tabular-nums'>
                {start}–{end}
              </span>
              {meta.total == null && ' of an unknown total'}
            </p>
          )}
        </div>
        <div className='flex flex-wrap items-center gap-2 text-xs text-muted-foreground'>
          {meta.sort && (
            <>
              <span className='inline-flex items-center gap-1'>
                <ArrowDownWideNarrow aria-hidden className='size-3.5' />
                {ORDER_LABELS[meta.sort] ?? meta.sort}
              </span>
              <span aria-hidden>·</span>
            </>
          )}
          <span>YouTube via the local foundation</span>
          {collected && (
            <>
              <span aria-hidden>·</span>
              <span
                data-testid='collected-at'
                title='When these videos were first collected from YouTube into the local dataset. View counts are as of that collection unless they were refreshed later.'
              >
                Collected{' '}
                {collected.oldestDay === collected.newestDay
                  ? absoluteDateTime(collected.newest)
                  : `${absoluteDate(collected.oldest)} – ${absoluteDate(collected.newest)}`}{' '}
                ({relativeTime(collected.oldest)})
              </span>
              {collected.stale ? (
                <Badge
                  variant='outline'
                  className='border-amber-500/60 text-amber-700 dark:text-amber-300'
                >
                  <Clock aria-hidden />
                  Stale: collected over 24 h ago
                </Badge>
              ) : (
                <Badge
                  variant='outline'
                  className='border-emerald-500/60 text-emerald-700 dark:text-emerald-300'
                >
                  <Clock aria-hidden />
                  Collected in the last 24 h
                </Badge>
              )}
            </>
          )}
          {meta.demo && (
            <Badge
              variant='outline'
              className='border-violet-500/50 text-violet-700 dark:text-violet-300'
            >
              <FlaskConical aria-hidden />
              {meta.data_origin === 'test' ? 'TEST data' : 'DEMO data'}
            </Badge>
          )}
        </div>
      </div>
      {meta.notes.length > 0 && (
        <Alert className='border-dashed py-2.5'>
          <Info aria-hidden />
          <AlertDescription className='text-xs'>
            <ul className='flex flex-col gap-1'>
              {meta.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}
