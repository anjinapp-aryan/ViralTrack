import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useAiContent, useAiSummary } from '@/lib/api/queries'
import { fullNumber } from '@/lib/format'
import { Button } from '@/components/ui/button'
import { RESULTS_GRID } from '@/features/discover/components/grid'
import { Segmented } from '@/features/discover/components/segmented'
import { AiFilters } from '../components/ai-filters'
import { AiVideoCard } from '../components/ai-video-card'
import { Loaded } from '../components/loaded'
import { CorpusStrip, EmptyNote } from '../components/parts'
import { CATEGORY_LABEL, countOf } from '../labels'
import {
  contentParams,
  optionParams,
  summaryParams,
  type Category,
} from '../search-params'
import { MUSIC_SCOPE, VIDEO_SCOPE } from '../sections'
import { useAiSearch } from '../use-ai-search'

/** The video list shared by AI Discover and the focused music and video pages (`scope`). */
function VideoList({ scope }: { scope?: readonly Category[] }) {
  const { search, update, reset } = useAiSearch()
  const basis = search.basis ?? 'creator'
  const options = useAiSummary(optionParams(search))
  const scoped = useAiSummary(
    summaryParams({ ...search, category: undefined }, scope),
    Boolean(scope)
  )
  const content = useAiContent(contentParams(search, scope))
  const o = options.data
  const chosen = (search.category ?? []).filter(
    (c) => !scope || scope.includes(c)
  )
  return (
    <>
      {scope && (
        <div className='max-w-full overflow-x-auto'>
          <Segmented
            label='Category'
            value={chosen.length === 1 ? chosen[0] : 'all'}
            options={[
              {
                value: 'all',
                label: `All (${scoped.data ? fullNumber(scoped.data.matching) : '…'})`,
              },
              ...scope.map((c) => ({
                value: c,
                label: `${CATEGORY_LABEL[c]} (${scoped.data ? fullNumber(countOf(scoped.data.by_category, c)) : '…'})`,
              })),
            ]}
            onChange={(v) =>
              update({ category: v === 'all' ? undefined : [v as Category] })
            }
          />
        </div>
      )}
      <AiFilters
        search={search}
        countries={
          basis === 'creator' ? o?.by_creator_country : o?.by_discovery_country
        }
        languages={o?.by_language}
        onChange={update}
        onReset={reset}
        showSort
        scope={scope}
      />
      <Loaded q={content} label='AI videos'>
        {(d) => (
          <>
            <CorpusStrip meta={d.meta} showNotes={false} />
            <p className='text-lg font-semibold'>
              {fullNumber(d.meta.total)} matching videos{' '}
              <span className='text-sm font-normal text-muted-foreground'>
                {d.meta.returned > 0 &&
                  `showing ${(d.meta.page - 1) * d.meta.page_size + 1}–${(d.meta.page - 1) * d.meta.page_size + d.meta.returned}`}
              </span>
            </p>
            {d.data.length === 0 ? (
              <EmptyNote
                title='No collected video matches these filters'
                actions={
                  <Button variant='outline' size='sm' onClick={reset}>
                    Reset filters
                  </Button>
                }
              >
                Nothing was hidden: this is a real zero for the classified
                corpus. Try a longer date range, add Possibly AI or Unclassified
                under Content, or choose another country or language.
              </EmptyNote>
            ) : (
              <div className={RESULTS_GRID}>
                {d.data.map((v) => (
                  <AiVideoCard key={v.video.id} item={v} />
                ))}
              </div>
            )}
            {(d.meta.page > 1 || d.meta.has_more) && (
              <nav
                aria-label='Pages'
                className='flex items-center justify-center gap-2'
              >
                <Button
                  variant='outline'
                  disabled={d.meta.page <= 1}
                  onClick={() => update({ page: d.meta.page - 1 })}
                >
                  <ChevronLeft aria-hidden />
                  Previous
                </Button>
                <span className='text-sm text-muted-foreground'>
                  Page {d.meta.page}
                </span>
                <Button
                  variant='outline'
                  disabled={!d.meta.has_more}
                  onClick={() => update({ page: d.meta.page + 1 })}
                >
                  Next
                  <ChevronRight aria-hidden />
                </Button>
              </nav>
            )}
          </>
        )}
      </Loaded>
    </>
  )
}

export function DiscoverPage() {
  return <VideoList />
}

export function MusicPage() {
  return <VideoList scope={MUSIC_SCOPE} />
}

export function VideoPage() {
  return <VideoList scope={VIDEO_SCOPE} />
}
