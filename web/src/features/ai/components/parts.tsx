import { Link } from '@tanstack/react-router'
import {
  ArrowRight,
  Ban,
  Clock,
  Database,
  FlaskConical,
  Info,
} from 'lucide-react'
import type { CorpusMeta, Count } from '@/lib/api/client'
import {
  absoluteDate,
  absoluteDateTime,
  fullNumber,
  relativeTime,
} from '@/lib/format'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { isStale } from '../labels'
import type { AiSearch } from '../search-params'

/** Where the numbers come from: origin, collection dates, how much was examined, what was left out. */
export function CorpusStrip({
  meta,
  showNotes = true,
}: {
  meta: CorpusMeta
  showNotes?: boolean
}) {
  const from = meta.collected_from
  const to = meta.collected_to
  const stale = isStale(from)
  return (
    <div className='flex flex-col gap-2'>
      <div
        className='flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground'
        data-testid='corpus-strip'
      >
        {meta.demo ? (
          <Badge
            variant='outline'
            className='border-violet-500/50 text-violet-700 dark:text-violet-300'
          >
            <FlaskConical aria-hidden />
            {meta.data_origin === 'test' ? 'TEST data' : 'DEMO data'}
          </Badge>
        ) : (
          <Badge variant='outline'>
            <Database aria-hidden />
            Real collected data
          </Badge>
        )}
        {from && to ? (
          <>
            <span data-testid='collected-span'>
              Collected{' '}
              {absoluteDate(from) === absoluteDate(to)
                ? absoluteDateTime(to)
                : `${absoluteDate(from)} – ${absoluteDate(to)}`}{' '}
              ({relativeTime(from)})
            </span>
            <Badge
              variant='outline'
              className={
                stale
                  ? 'border-amber-500/60 text-amber-700 dark:text-amber-300'
                  : 'border-emerald-500/60 text-emerald-700 dark:text-emerald-300'
              }
            >
              <Clock aria-hidden />
              {stale
                ? 'Stale: collected over 24 h ago'
                : 'Collected in the last 24 h'}
            </Badge>
          </>
        ) : (
          <span>Collection time not reported</span>
        )}
        <span aria-hidden>·</span>
        <span>Classifier {meta.classifier_version}</span>
        {meta.candidate_limit_reached && (
          <>
            <span aria-hidden>·</span>
            <span>
              Only the first {fullNumber(meta.candidate_limit)} videos were
              examined
            </span>
          </>
        )}
      </div>
      {showNotes && meta.notes.length > 0 && (
        <details className='group rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground'>
          <summary className='flex cursor-pointer items-center gap-1.5 hover:text-foreground'>
            <Info aria-hidden className='size-3.5' />
            How to read these numbers ({meta.notes.length} notes)
          </summary>
          <ul className='mt-2 flex list-disc flex-col gap-1 ps-5'>
            {meta.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

/**
 * A headline count. `value` null = unavailable (the reason is written out), which is never shown as 0.
 * With `to`, the tile opens the matching list.
 */
export function StatTile({
  label,
  value,
  hint,
  unavailable,
  to,
  search,
  emphasis,
}: {
  label: string
  value: number | null
  hint?: string
  unavailable?: string
  to?: string
  search?: Partial<AiSearch>
  emphasis?: boolean
}) {
  const body = (
    <>
      <span className='text-xs leading-4 text-muted-foreground'>{label}</span>
      {value === null ? (
        <span className='flex items-center gap-1.5 text-sm font-medium text-muted-foreground'>
          <Ban aria-hidden className='size-4' />
          Unavailable
        </span>
      ) : (
        <span
          className={cn(
            'font-semibold tracking-tight tabular-nums',
            emphasis ? 'text-3xl' : 'text-2xl'
          )}
        >
          {fullNumber(value)}
        </span>
      )}
      {(unavailable ?? hint) && (
        <span className='text-xs leading-4 text-muted-foreground'>
          {value === null ? unavailable : hint}
        </span>
      )}
      {to && (
        <span className='mt-auto inline-flex items-center gap-1 pt-1 text-xs font-medium text-primary'>
          Inspect
          <ArrowRight aria-hidden className='size-3.5' />
        </span>
      )}
    </>
  )
  const cls =
    'flex min-h-28 flex-col gap-1 rounded-xl border bg-card p-4 text-start shadow-xs'
  return to ? (
    <Link
      to={to}
      search={search as never}
      className={cn(
        cls,
        'transition-colors outline-none hover:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring'
      )}
    >
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  )
}

/**
 * Horizontal bars for one measure (items in the collected corpus). One hue, length = count, every value
 * written next to its bar, so the list also works as a table.
 */
export function BarList({
  title,
  description,
  counts,
  name,
  empty = 'No items in this window.',
  max = 10,
}: {
  title: string
  description?: string
  counts: Count[]
  name: (key: string) => string
  empty?: string
  max?: number
}) {
  const shown = counts.slice(0, max)
  const rest = counts.slice(max).reduce((a, c) => a + c.count, 0)
  const top = Math.max(1, ...shown.map((c) => c.count))
  return (
    <section className='flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs'>
      <div>
        <h3 className='text-sm font-semibold'>{title}</h3>
        {description && (
          <p className='text-xs text-muted-foreground'>{description}</p>
        )}
      </div>
      {shown.length === 0 ? (
        <p className='text-sm text-muted-foreground'>{empty}</p>
      ) : (
        <ul className='flex flex-col gap-1.5'>
          {shown.map((c) => (
            <li
              key={c.key}
              className='grid grid-cols-[minmax(5rem,9rem)_1fr_auto] items-center gap-3 text-sm'
              title={`${name(c.key)}: ${c.count} items`}
            >
              <span className='truncate'>{name(c.key)}</span>
              <span className='h-2 rounded-full bg-muted'>
                <span
                  className='block h-full rounded-full bg-primary'
                  style={{ width: `${(c.count / top) * 100}%` }}
                />
              </span>
              <span className='text-end text-muted-foreground tabular-nums'>
                {fullNumber(c.count)}
              </span>
            </li>
          ))}
          {rest > 0 && (
            <li className='text-xs text-muted-foreground'>
              and {fullNumber(rest)} more items in other groups
            </li>
          )}
        </ul>
      )}
    </section>
  )
}

export function PanelSkeleton({ label }: { label: string }) {
  return (
    <div
      role='status'
      aria-label={`Loading ${label}`}
      className='grid gap-3 sm:grid-cols-2 xl:grid-cols-4'
    >
      {Array.from({ length: 8 }, (_, i) => (
        <Skeleton key={i} className='h-28 rounded-xl' />
      ))}
    </div>
  )
}

/** A neutral message for a real zero or an empty result. Says why, and what to do. */
export function EmptyNote({
  title,
  children,
  actions,
}: {
  title: string
  children: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <div className='flex flex-col gap-2 rounded-xl border border-dashed p-6'>
      <h3 className='text-sm font-semibold'>{title}</h3>
      <div className='max-w-3xl text-sm text-muted-foreground'>{children}</div>
      {actions && <div className='mt-1 flex flex-wrap gap-2'>{actions}</div>}
    </div>
  )
}
