import { useState } from 'react'
import { Globe2, Search } from 'lucide-react'
import type { Count, CountryRow } from '@/lib/api/client'
import { useAiCountries, useAiSummary } from '@/lib/api/queries'
import { fullNumber } from '@/lib/format'
import { cn } from '@/lib/utils'
import { AiFilters } from '../components/ai-filters'
import { Loaded } from '../components/loaded'
import { BarList, CorpusStrip, EmptyNote, StatTile } from '../components/parts'
import {
  CATEGORY_LABEL,
  FORMAT_LABEL,
  countOf,
  countryName,
  label,
  languageName,
} from '../labels'
import { countriesParams, optionParams, summaryParams } from '../search-params'
import { useAiSearch } from '../use-ai-search'

const COMPARE_MAX = 4

function addDays(rows: CountryRow[]): Count[] {
  const days = new Map<string, number>()
  for (const r of rows)
    for (const d of r.by_published_day)
      days.set(d.key, (days.get(d.key) ?? 0) + d.count)
  return [...days].map(([key, count]) => ({ key, count }))
}

function byDay(counts: Count[]): Count[] {
  return [...counts].sort((a, b) => b.key.localeCompare(a.key))
}

function Detail({
  title,
  items,
  category,
  format,
  language,
  days,
  daysNote,
}: {
  title: string
  items: number
  category: Count[]
  format: Count[]
  language: Count[]
  days: Count[] | null
  daysNote?: string
}) {
  return (
    <section aria-label={title} className='flex flex-col gap-3'>
      <h2 className='text-base font-semibold'>{title}</h2>
      <div className='grid grid-cols-3 gap-3'>
        <StatTile label='Matching videos' value={items} />
        <StatTile
          label='Short-form by duration'
          value={countOf(format, 'short_form')}
        />
        <StatTile label='Long-form' value={countOf(format, 'long_form')} />
      </div>
      <BarList
        title='AI category'
        counts={category}
        name={(k) => label(CATEGORY_LABEL, k)}
      />
      <BarList title='Language' counts={language} name={languageName} />
      <BarList
        title='Format'
        counts={format}
        name={(k) => label(FORMAT_LABEL, k)}
      />
      {days ? (
        <BarList
          title='Recent discoveries by publication day'
          description='Matching collected videos per day they were published (newest first)'
          counts={byDay(days)}
          name={(k) => k}
          max={14}
        />
      ) : (
        <EmptyNote title='Recent discoveries by publication day'>
          {daysNote}
        </EmptyNote>
      )}
    </section>
  )
}

export function CountriesPage() {
  const { search, update, reset } = useAiSearch()
  const basis = search.basis ?? 'creator'
  const [query, setQuery] = useState('')
  const options = useAiSummary(optionParams(search))
  const countries = useAiCountries(countriesParams(search))
  const worldwide = useAiSummary(
    summaryParams({ ...search, country: undefined })
  )
  const selected = search.country ?? []
  const pick = (code: string) => {
    const next = selected.includes(code)
      ? selected.filter((c) => c !== code)
      : [...selected, code].slice(-COMPARE_MAX)
    update({ country: next.length ? next : undefined })
  }
  return (
    <>
      <AiFilters
        search={search}
        countries={undefined}
        languages={options.data?.by_language}
        onChange={update}
        onReset={reset}
        hideCountry
      />
      <Loaded q={countries} label='Countries'>
        {(d) => {
          const rows = d.data
          const shown = rows.filter((r) =>
            `${countryName(r.country)} ${r.country}`
              .toLowerCase()
              .includes(query.trim().toLowerCase())
          )
          const picked = rows.filter((r) => selected.includes(r.country))
          const w = worldwide.data
          return (
            <>
              <CorpusStrip meta={d.meta} />
              <div className='grid gap-5 lg:grid-cols-[18rem_1fr]'>
                <aside aria-label='Countries' className='flex flex-col gap-2'>
                  <label className='relative'>
                    <span className='sr-only'>Search countries</span>
                    <Search
                      aria-hidden
                      className='absolute start-2.5 top-2.5 size-4 text-muted-foreground'
                    />
                    <input
                      type='search'
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder='Search countries'
                      className='h-9 w-full rounded-md border bg-background ps-8 pe-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring'
                    />
                  </label>
                  <p className='text-xs text-muted-foreground'>
                    {basis === 'creator'
                      ? 'By the country creators declared on their channel.'
                      : "By the market of ViralTrack's regional collections."}{' '}
                    Select up to {COMPARE_MAX} to compare.
                  </p>
                  <ul className='flex max-h-[28rem] flex-col gap-0.5 overflow-auto rounded-xl border bg-card p-1.5'>
                    <li>
                      <button
                        type='button'
                        aria-pressed={selected.length === 0}
                        onClick={() => update({ country: undefined })}
                        className={cn(
                          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-start text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring',
                          selected.length === 0
                            ? 'bg-primary/15 font-medium'
                            : 'hover:bg-muted'
                        )}
                      >
                        <Globe2 aria-hidden className='size-4' />
                        <span className='flex-1'>Worldwide</span>
                        <span className='text-muted-foreground tabular-nums'>
                          {w ? fullNumber(w.matching) : '…'}
                        </span>
                      </button>
                    </li>
                    {shown.map((r) => (
                      <li key={r.country}>
                        <button
                          type='button'
                          aria-pressed={selected.includes(r.country)}
                          onClick={() => pick(r.country)}
                          className={cn(
                            'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-start text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring',
                            selected.includes(r.country)
                              ? 'bg-primary/15 font-medium'
                              : 'hover:bg-muted'
                          )}
                        >
                          <span className='flex-1 truncate'>
                            {countryName(r.country)}
                          </span>
                          <span className='text-muted-foreground tabular-nums'>
                            {fullNumber(r.items)}
                          </span>
                        </button>
                      </li>
                    ))}
                    {shown.length === 0 && (
                      <li className='px-2 py-1.5 text-sm text-muted-foreground'>
                        {rows.length === 0
                          ? 'No country has matching videos in this date range.'
                          : 'No country matches the search.'}
                      </li>
                    )}
                  </ul>
                </aside>
                <div className='flex min-w-0 flex-col gap-4'>
                  {picked.length === 0 ? (
                    w ? (
                      <Detail
                        title='Worldwide (the whole collected corpus)'
                        items={w.matching}
                        category={w.by_category}
                        format={w.by_format}
                        language={w.by_language}
                        days={basis === 'creator' ? addDays(rows) : null}
                        daysNote='Shown per market only: one video can be found in several markets.'
                      />
                    ) : null
                  ) : (
                    <div
                      className={cn(
                        'grid gap-5',
                        picked.length > 1 && 'xl:grid-cols-2'
                      )}
                    >
                      {picked.map((r) => (
                        <Detail
                          key={r.country}
                          title={
                            r.country === 'unknown'
                              ? 'Unknown country'
                              : countryName(r.country)
                          }
                          items={r.items}
                          category={r.by_category}
                          format={r.by_format}
                          language={r.by_language}
                          days={r.by_published_day}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          )
        }}
      </Loaded>
    </>
  )
}
