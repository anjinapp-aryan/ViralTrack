import { useAiOpportunities, useAiSummary } from '@/lib/api/queries'
import { AiFilters } from '../components/ai-filters'
import { Loaded } from '../components/loaded'
import { Opportunities } from '../components/opportunity-list'
import { CorpusStrip } from '../components/parts'
import { opportunitiesParams, optionParams } from '../search-params'
import { useAiSearch } from '../use-ai-search'

export function OpportunitiesPage() {
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
      <Loaded q={opps} label='Opportunities'>
        {(d) => (
          <>
            <CorpusStrip meta={d.meta} />
            <p className='text-sm text-muted-foreground'>
              Groups of at least {d.min_items} matching AI videos that share a
              category, format, language and{' '}
              {d.basis === 'creator' ? 'creator country' : 'discovery market'},
              ordered by how many collected videos support them. No score and no
              prediction.
            </p>
            <Opportunities data={d} />
          </>
        )}
      </Loaded>
    </>
  )
}
