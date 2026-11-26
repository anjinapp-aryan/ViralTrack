import { Link } from '@tanstack/react-router'
import { ArrowRight } from 'lucide-react'
import type { AiSummary } from '@/lib/api/client'
import { useAiSummary } from '@/lib/api/queries'
import { fullNumber } from '@/lib/format'
import { Button } from '@/components/ui/button'
import { AiFilters } from '../components/ai-filters'
import { AiVideoCard } from '../components/ai-video-card'
import { Loaded } from '../components/loaded'
import { BarList, CorpusStrip, EmptyNote, StatTile } from '../components/parts'
import {
  CONFIDENCE_LABEL,
  STATUS_HINT,
  STATUS_LABEL,
  VERIFIED_SHORTS_UNAVAILABLE,
  countOf,
  countryName,
  label,
  languageName,
} from '../labels'
import {
  DEFAULT_STATUSES,
  STATUSES,
  optionParams,
  summaryParams,
  type AiSearch,
} from '../search-params'
import { useAiSearch } from '../use-ai-search'

const PRIMARY = [
  {
    key: 'AI_MUSIC_VIDEO',
    title: 'AI music videos',
    to: '/ai/music',
  },
  {
    key: 'AI_MUSIC_AUDIO',
    title: 'AI music / audio',
    to: '/ai/music',
  },
  {
    key: 'AI_VIDEO_WITH_MUSIC',
    title: 'AI videos with soundtrack',
    to: '/ai/video',
  },
  {
    key: 'AI_NORMAL_VIDEO',
    title: 'AI stories and explainers',
    to: '/ai/video',
  },
] as const

function Funnel({ s, search }: { s: AiSummary; search: AiSearch }) {
  const examined = s.meta.candidates_examined
  const excluded = s.meta.excluded_gaming
  const classified = examined - excluded
  const keep = { period: search.period }
  return (
    <section aria-labelledby='funnel-title' className='flex flex-col gap-3'>
      <div>
        <h2 id='funnel-title' className='text-base font-semibold'>
          Classification funnel
        </h2>
        <p className='text-sm text-muted-foreground'>
          Every collected video of the date range, before the other filters.
          Select a group to inspect its videos and the evidence behind each
          status.
        </p>
      </div>
      <ol className='grid gap-3 sm:grid-cols-3'>
        <li>
          <StatTile
            label='1. Collected videos examined'
            value={examined}
            hint={
              s.meta.candidate_limit_reached
                ? `the first ${fullNumber(s.meta.candidate_limit)} by views`
                : 'all of the date range'
            }
            emphasis
          />
        </li>
        <li>
          <StatTile
            label='2. Gaming excluded'
            value={excluded}
            hint='left out of AI Content Intelligence'
            emphasis
          />
        </li>
        <li>
          <StatTile
            label='3. Classified'
            value={classified}
            hint={
              s.meta.signals_missing > 0
                ? `${fullNumber(s.meta.signals_missing)} without stored tags or disclosure`
                : 'every one with its stored tags and disclosure'
            }
            emphasis
          />
        </li>
      </ol>
      <ul
        aria-label='Classified videos by AI status'
        className='grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5'
      >
        {STATUSES.map((st) => (
          <li key={st}>
            <StatTile
              label={STATUS_LABEL[st]}
              value={countOf(s.by_status, st)}
              hint={STATUS_HINT[st]}
              to='/ai/discover'
              search={{ ...keep, status: [st] }}
            />
          </li>
        ))}
      </ul>
    </section>
  )
}

function Breakdown({ s, search }: { s: AiSummary; search: AiSearch }) {
  const statuses = (search.status ?? [...DEFAULT_STATUSES])
    .map((x) => STATUS_LABEL[x])
    .join(', ')
  const fmt = s.by_format
  return (
    <>
      <section aria-labelledby='category-title' className='flex flex-col gap-3'>
        <div>
          <h2 id='category-title' className='text-base font-semibold'>
            AI content categories
          </h2>
          <p className='text-sm text-muted-foreground'>
            Videos matching every filter ({statuses}).
          </p>
        </div>
        <ul className='grid grid-cols-2 gap-3 xl:grid-cols-4'>
          {PRIMARY.map((p) => (
            <li key={p.key}>
              <StatTile
                label={p.title}
                value={countOf(s.by_category, p.key)}
                to={p.to}
                search={{ ...search, category: [p.key], page: undefined }}
              />
            </li>
          ))}
        </ul>
        {countOf(s.by_category, 'UNKNOWN') > 0 && (
          <p className='text-xs text-muted-foreground'>
            {countOf(s.by_category, 'UNKNOWN')} matching AI videos have no
            category: the evidence does not say whether video or audio is the
            product.
          </p>
        )}
      </section>
      <section aria-labelledby='format-title' className='flex flex-col gap-3'>
        <div>
          <h2 id='format-title' className='text-base font-semibold'>
            Format
          </h2>
          <p className='text-sm text-muted-foreground'>
            Videos matching every filter ({statuses}).
          </p>
        </div>
        <ul className='grid grid-cols-2 gap-3 xl:grid-cols-4'>
          <li>
            <StatTile
              label='Platform-verified Shorts'
              value={null}
              unavailable={VERIFIED_SHORTS_UNAVAILABLE}
            />
          </li>
          <li>
            <StatTile
              label='Short-form by duration (≤ 3 min)'
              value={countOf(fmt, 'short_form')}
              hint='length only; not verified as a Short'
            />
          </li>
          <li>
            <StatTile label='Long-form' value={countOf(fmt, 'long_form')} />
          </li>
          <li>
            <StatTile
              label='Live / other'
              value={countOf(fmt, 'live') + countOf(fmt, 'unknown')}
              hint='live or upcoming broadcasts, or no usable length'
            />
          </li>
        </ul>
      </section>
    </>
  )
}

function NoMatches({ s, search }: { s: AiSummary; search: AiSearch }) {
  const possibly = countOf(s.by_status, 'POSSIBLY_AI')
  const unknown = countOf(s.by_status, 'UNKNOWN')
  const keep = { period: search.period }
  return (
    <EmptyNote
      title='No video matches these filters'
      actions={
        <>
          {possibly > 0 && (
            <Button asChild variant='outline' size='sm'>
              <Link
                to='/ai/discover'
                search={{ ...keep, status: ['POSSIBLY_AI'] } as never}
              >
                Inspect {possibly} Possibly AI
                <ArrowRight aria-hidden />
              </Link>
            </Button>
          )}
          {unknown > 0 && (
            <Button asChild variant='outline' size='sm'>
              <Link
                to='/ai/discover'
                search={{ ...keep, status: ['UNKNOWN'] } as never}
              >
                Inspect {unknown} Unclassified
                <ArrowRight aria-hidden />
              </Link>
            </Button>
          )}
        </>
      }
    >
      <p>
        This is a real zero, not missing data: the collected videos of this date
        range were classified, and none of them matches the selected statuses
        and filters. Unclassified means the title, tags and platform disclosure
        give no evidence either way; it does not mean human-made.
      </p>
      <p className='mt-2'>
        A corpus collected with general keywords holds little AI content. More
        AI videos appear only after collections aimed at AI content, which need
        the owner&apos;s approval (live-validation plan).
      </p>
    </EmptyNote>
  )
}

export function OverviewPage() {
  const { search, update, reset } = useAiSearch()
  const basis = search.basis ?? 'creator'
  const options = useAiSummary(optionParams(search))
  const summary = useAiSummary(summaryParams(search))
  const o = options.data
  return (
    <>
      <AiFilters
        search={search}
        countries={
          basis === 'creator' ? o?.by_creator_country : o?.by_discovery_country
        }
        languages={o?.by_language}
        onChange={update}
        onReset={reset}
      />
      <Loaded q={summary} label='Overview'>
        {(s) => (
          <>
            <CorpusStrip meta={s.meta} />
            <Funnel s={s} search={search} />
            {s.matching === 0 && <NoMatches s={s} search={search} />}
            <Breakdown s={s} search={search} />
            <div className='grid gap-3 lg:grid-cols-3'>
              <BarList
                title={
                  basis === 'creator'
                    ? 'Creator country (declared)'
                    : 'Discovery market'
                }
                description='Matching videos; unknown stays unknown'
                counts={
                  basis === 'creator'
                    ? s.by_creator_country
                    : s.by_discovery_country
                }
                name={countryName}
              />
              <BarList
                title='Language'
                description='Matching videos'
                counts={s.by_language}
                name={languageName}
              />
              <BarList
                title='Classification evidence'
                description='How strong the evidence is for the matching videos'
                counts={s.by_confidence}
                name={(k) => label(CONFIDENCE_LABEL, k)}
              />
            </div>
            <section
              aria-labelledby='recent-title'
              className='flex flex-col gap-3'
            >
              <h2 id='recent-title' className='text-base font-semibold'>
                Recent discoveries
              </h2>
              {s.recent.length === 0 ? (
                <p className='text-sm text-muted-foreground'>
                  No matching videos in this date range.
                </p>
              ) : (
                <div className='grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4'>
                  {s.recent.map((v) => (
                    <AiVideoCard key={v.video.id} item={v} />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </Loaded>
    </>
  )
}
