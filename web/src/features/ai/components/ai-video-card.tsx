import { Link } from '@tanstack/react-router'
import { ExternalLink, Lightbulb } from 'lucide-react'
import type { AiVideo } from '@/lib/api/client'
import {
  absoluteDate,
  compactNumber,
  duration,
  relativeTime,
} from '@/lib/format'
import { Badge } from '@/components/ui/badge'
import { ThumbnailPlaceholder } from '@/features/discover/components/thumbnail-placeholder'
import {
  CATEGORY_LABEL,
  CONFIDENCE_LABEL,
  FORMAT_LABEL,
  STATUS_LABEL,
  countryName,
  label,
  languageName,
} from '../labels'
import { AI_CATEGORY_SET, opportunitySearch } from '../search-params'

const STATUS_TONE: Record<string, string> = {
  CONFIRMED_AI: 'border-primary bg-primary/15 text-foreground',
  LIKELY_AI: 'border-primary/60 bg-primary/10 text-foreground',
  POSSIBLY_AI: 'border-dashed text-foreground',
  NOT_AI: 'text-muted-foreground',
  UNKNOWN: 'text-muted-foreground',
}

/**
 * One classified video. The thumbnail stays a placeholder (platform images are not loaded until reviewed).
 * Every label says where it comes from; the evidence behind the AI status is summarised and can be expanded.
 */
export function AiVideoCard({ item }: { item: AiVideo }) {
  const { video, classification: c, format, country } = item
  const views = compactNumber(video.metrics.views?.value)
  const length = duration(format.duration_seconds)
  const isAi = AI_CATEGORY_SET.has(c.category)
  const title = video.title ?? 'Untitled video'
  return (
    <article
      aria-label={title}
      className='flex h-full flex-col overflow-hidden rounded-xl border bg-card shadow-xs'
    >
      <div className='relative'>
        <ThumbnailPlaceholder seed={video.id} category={video.category} />
        {length && (
          <span className='absolute end-2 bottom-2 rounded-md bg-black/75 px-1.5 py-0.5 text-[11px] font-semibold text-white tabular-nums'>
            {length}
          </span>
        )}
      </div>
      <div className='flex flex-1 flex-col gap-2.5 p-3.5'>
        <div className='flex flex-wrap items-center gap-1.5'>
          <Badge variant='outline' className={STATUS_TONE[c.status]}>
            {label(STATUS_LABEL, c.status)}
          </Badge>
          <span className='text-[11px] text-muted-foreground'>
            {label(CONFIDENCE_LABEL, c.confidence)}
          </span>
        </div>
        <h3 className='line-clamp-2 text-[0.95rem] leading-5 font-semibold'>
          {title}
        </h3>
        <p className='-mt-1 truncate text-[13px] text-muted-foreground'>
          {video.creator.name ?? 'Unknown creator'}
        </p>
        <div className='flex flex-wrap gap-1.5'>
          <Badge variant='secondary'>{label(CATEGORY_LABEL, c.category)}</Badge>
          <Badge variant='outline' title={format.reason}>
            {label(FORMAT_LABEL, format.format_type)}
          </Badge>
        </div>
        <p className='line-clamp-2 text-xs text-muted-foreground'>
          <span className='font-medium text-foreground'>Evidence: </span>
          {c.evidence.length > 0 ? c.evidence[0] : c.reason}
          {c.evidence.length > 1 && ` (+${c.evidence.length - 1} more)`}
        </p>
        <dl className='grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-xs'>
          <dt className='text-muted-foreground'>Creator country</dt>
          <dd>
            {country.creator_country
              ? `${countryName(country.creator_country)} (declared by the creator)`
              : 'Unknown'}
          </dd>
          <dt className='text-muted-foreground'>Discovered in</dt>
          <dd>
            {country.discovery_countries.length
              ? country.discovery_countries.map(countryName).join(', ')
              : 'No regional collection'}
          </dd>
          <dt className='text-muted-foreground'>Language</dt>
          <dd>{languageName(country.language_code)}</dd>
          <dt className='text-muted-foreground'>Published</dt>
          <dd>
            {absoluteDate(video.published_at) ?? 'Not reported'}
            {video.published_at && ` (${relativeTime(video.published_at)})`}
          </dd>
        </dl>
        <details className='text-xs'>
          <summary className='cursor-pointer text-muted-foreground hover:text-foreground'>
            Why this classification
          </summary>
          <div className='mt-1.5 flex flex-col gap-1'>
            <p>{c.reason}.</p>
            <p className='text-muted-foreground'>
              Category: {c.category_reason}.
            </p>
            <p className='text-muted-foreground'>Format: {format.reason}.</p>
            {c.evidence.length > 0 && (
              <ul className='list-disc ps-4 text-muted-foreground'>
                {c.evidence.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        </details>
        <div className='mt-auto flex flex-wrap items-center gap-x-3 gap-y-2 border-t pt-2.5 text-[13px] text-muted-foreground'>
          <span className='me-auto'>
            {views ? (
              <>
                <span className='text-base font-semibold text-foreground tabular-nums'>
                  {views}
                </span>{' '}
                views
              </>
            ) : (
              <span className='italic'>views not reported</span>
            )}
          </span>
          {isAi && (
            <Link
              to='/ai/opportunities'
              search={opportunitySearch(item) as never}
              className='inline-flex items-center gap-1 rounded-md font-medium text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring'
            >
              <Lightbulb aria-hidden className='size-3.5' />
              Analyze opportunity
            </Link>
          )}
          <a
            href={video.url}
            target='_blank'
            rel='noopener noreferrer'
            className='inline-flex items-center gap-1 rounded-md text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring'
          >
            Open source
            <ExternalLink aria-hidden className='size-3.5' />
            <span className='sr-only'>(opens the platform in a new tab)</span>
          </a>
        </div>
      </div>
    </article>
  )
}
