import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import type { AiOpportunity } from '@/lib/api/client'
import { useAiOpportunities, useAiSummary } from '@/lib/api/queries'
import { Button } from '@/components/ui/button'
import { briefText } from '../brief-text'
import { AiFilters } from '../components/ai-filters'
import { Loaded } from '../components/loaded'
import { Brief, NoOpportunities } from '../components/opportunity-list'
import { CorpusStrip } from '../components/parts'
import { opportunitiesParams, optionParams } from '../search-params'
import { useAiSearch } from '../use-ai-search'

function CopyBrief({ o }: { o: AiOpportunity }) {
  const [done, setDone] = useState(false)
  return (
    <Button
      variant='outline'
      size='sm'
      onClick={async () => {
        await navigator.clipboard?.writeText(briefText(o))
        setDone(true)
      }}
    >
      {done ? <Check aria-hidden /> : <Copy aria-hidden />}
      {done ? 'Copied' : 'Copy brief as text'}
    </Button>
  )
}

export function BriefsPage() {
  const { search, update, reset } = useAiSearch()
  const basis = search.basis ?? 'creator'
  const options = useAiSummary(optionParams(search))
  const opps = useAiOpportunities(opportunitiesParams(search))
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
      <Loaded q={opps} label='Creative briefs'>
        {(d) => (
          <>
            <CorpusStrip meta={d.meta} showNotes={false} />
            {d.data.length === 0 ? (
              <NoOpportunities min={d.min_items} />
            ) : (
              <ol className='flex flex-col gap-4'>
                {d.data.map((op) => (
                  <li
                    key={op.key}
                    className='flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs'
                  >
                    <div className='flex flex-wrap items-center justify-between gap-2'>
                      <h2 className='text-base font-semibold'>
                        {op.brief.opportunity_title}
                      </h2>
                      <CopyBrief o={op} />
                    </div>
                    <p className='text-xs text-muted-foreground'>
                      Based on {op.item_count} collected videos. {op.summary}
                    </p>
                    <Brief o={op} open />
                  </li>
                ))}
              </ol>
            )}
          </>
        )}
      </Loaded>
    </>
  )
}
