import { ExternalLink, Lightbulb } from 'lucide-react'
import type { AiOpportunities, AiOpportunity } from '@/lib/api/client'
import { absoluteDate, compactNumber } from '@/lib/format'
import { Badge } from '@/components/ui/badge'
import {
  CATEGORY_LABEL,
  FORMAT_LABEL,
  STATUS_LABEL,
  countryName,
  label,
  languageName,
} from '../labels'

function Field({
  name,
  children,
  className,
}: {
  name: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={`flex flex-col gap-0.5 ${className ?? ''}`}>
      <dt className='text-xs font-medium text-muted-foreground'>{name}</dt>
      <dd className='text-sm'>{children}</dd>
    </div>
  )
}

export function Brief({ o, open }: { o: AiOpportunity; open?: boolean }) {
  const b = o.brief
  return (
    <details className='rounded-lg border bg-muted/30 p-3' open={open}>
      <summary className='cursor-pointer text-sm font-medium'>
        Original creative brief
      </summary>
      <dl className='mt-3 grid gap-3 md:grid-cols-2'>
        <Field name='Opportunity'>{b.opportunity_title}</Field>
        <Field name='Country / language'>
          {b.country ? countryName(b.country) : 'Unknown'} ·{' '}
          {languageName(b.language_code)}
        </Field>
        <Field name='Category / format'>
          {label(CATEGORY_LABEL, b.category)} ·{' '}
          {label(FORMAT_LABEL, b.format_type)}
        </Field>
        <Field name='Suggested length'>{b.suggested_duration}</Field>
        <Field name='Audience hypothesis'>{b.audience_hypothesis}</Field>
        <Field name='Theme'>{b.theme}</Field>
        <Field name='Original creative angle'>
          {b.original_creative_angle}
        </Field>
        <Field name='Hook'>{b.hook_concept}</Field>
        <Field name='Story outline'>
          <ol className='list-decimal ps-4'>
            {b.story_outline.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
        </Field>
        {b.music_direction && (
          <Field name='Music direction'>{b.music_direction}</Field>
        )}
        <Field name='Visual direction'>{b.visual_direction}</Field>
        <Field name='Platforms'>{b.platform_recommendations.join(', ')}</Field>
        <Field
          name='Rights and originality checklist'
          className='md:col-span-2'
        >
          <ul className='flex flex-col gap-1'>
            {b.rights_checklist.map((r) => (
              <li key={r} className='flex gap-2'>
                <input
                  type='checkbox'
                  className='mt-0.5 size-4 accent-primary'
                  aria-label={r}
                />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </Field>
      </dl>
      <p className='mt-3 text-xs text-muted-foreground'>{b.note}</p>
    </details>
  )
}

export function NoOpportunities({ min }: { min: number }) {
  return (
    <p className='rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground'>
      No group of at least {min} matching AI videos shares a category, format,
      language and country in this date range. Nothing is invented to fill the
      page: collect more AI content or widen the filters.
    </p>
  )
}

export function Opportunities({ data }: { data: AiOpportunities }) {
  if (data.data.length === 0) return <NoOpportunities min={data.min_items} />
  return (
    <ol className='flex flex-col gap-4'>
      {data.data.map((o) => (
        <li
          key={o.key}
          className='flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs'
        >
          <div className='flex flex-wrap items-center gap-2'>
            <Lightbulb aria-hidden className='size-4 text-primary' />
            <Badge variant='secondary'>
              {label(CATEGORY_LABEL, o.category)}
            </Badge>
            <Badge variant='outline'>
              {label(FORMAT_LABEL, o.format_type)}
            </Badge>
            <Badge variant='outline'>{languageName(o.language_code)}</Badge>
            <Badge variant='outline'>
              {o.country ? countryName(o.country) : 'Country unknown'}
              {o.country_basis === 'creator' ? ' (creator)' : ' (market)'}
            </Badge>
            <span className='text-xs text-muted-foreground'>
              {o.item_count} supporting videos
            </span>
          </div>
          <p className='text-sm'>{o.summary}</p>
          {o.themes.length > 0 && (
            <div className='flex flex-wrap items-center gap-1.5 text-xs'>
              <span className='text-muted-foreground'>Recurring terms:</span>
              {o.themes.map((t) => (
                <span key={t.term} className='rounded-full border px-2 py-0.5'>
                  {t.term}{' '}
                  <span className='text-muted-foreground'>×{t.items}</span>
                </span>
              ))}
            </div>
          )}
          <details>
            <summary className='cursor-pointer text-sm text-muted-foreground hover:text-foreground'>
              Supporting evidence ({o.evidence.length})
            </summary>
            <ul className='mt-2 flex flex-col gap-1.5 text-sm'>
              {o.evidence.map((e) => (
                <li
                  key={e.id}
                  className='flex flex-wrap items-baseline gap-x-2'
                >
                  <a
                    href={e.url}
                    target='_blank'
                    rel='noopener noreferrer'
                    className='inline-flex items-center gap-1 text-primary hover:underline'
                  >
                    {e.title ?? e.id}
                    <ExternalLink aria-hidden className='size-3' />
                  </a>
                  <span className='text-xs text-muted-foreground'>
                    {e.creator_name ?? 'Unknown creator'} ·{' '}
                    {compactNumber(e.views?.value) ?? 'views not reported'}{' '}
                    views · {absoluteDate(e.published_at) ?? 'date unknown'} ·{' '}
                    {label(STATUS_LABEL, e.status)}
                  </span>
                </li>
              ))}
            </ul>
          </details>
          <Brief o={o} />
        </li>
      ))}
    </ol>
  )
}
