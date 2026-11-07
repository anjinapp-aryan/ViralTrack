import { useState } from 'react'
import { RotateCcw, Search, SlidersHorizontal } from 'lucide-react'
import type { Capabilities } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  CREATOR_SIZES,
  DEFAULT_PERIOD,
  DURATIONS,
  PERIODS,
  SORT_LABELS,
  activeFilterCount,
  type DiscoverSearch,
} from '../search-params'
import { Segmented } from './segmented'

type Props = {
  search: DiscoverSearch
  capabilities: Capabilities | undefined
  onChange: (patch: Partial<DiscoverSearch>) => void
  onReset: () => void
}

const REGIONS = ['US', 'GB', 'CA', 'AU', 'IN', 'DE', 'FR', 'ES', 'BR', 'JP']
const QUERY_ONLY_HINT = 'Not available with topic search'

/** One toolbar: topic search, filters and sort. Sort options are the API's browse sorts only. */
export function FilterBar({ search, capabilities, onChange, onReset }: Props) {
  const [text, setText] = useState(search.q ?? '')
  const searching = Boolean(search.q)
  const sorts = (capabilities?.sorts ?? [])
    .filter((s) => s.available && s.applies_to === 'browse')
    .map((s) => ({ value: s.name, label: SORT_LABELS[s.name] ?? s.name }))
  const extra = [search.niche, search.region, search.min_views].filter(
    (v) => v != null
  ).length

  return (
    <div className='flex flex-col gap-2'>
      <div className='flex flex-wrap items-center gap-2 rounded-xl border bg-card/60 p-2 shadow-xs'>
        <form
          role='search'
          className='flex min-w-[16rem] flex-[1_1_22rem] gap-2'
          onSubmit={(e) => {
            e.preventDefault()
            onChange({ q: text.trim() || undefined })
          }}
        >
          <div className='relative flex-1'>
            <Search
              aria-hidden
              className='pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground'
            />
            <Input
              type='search'
              value={text}
              maxLength={200}
              onChange={(e) => setText(e.target.value)}
              placeholder='Topic search, e.g. "local LLM"'
              aria-label='Topic search'
              className='h-9 bg-background ps-9'
            />
          </div>
          <Button type='submit' className='h-9'>
            Search
          </Button>
        </form>

        <div className='flex flex-wrap items-center gap-2'>
          <Select
            value={search.period ?? DEFAULT_PERIOD}
            onValueChange={(v) => onChange({ period: v })}
          >
            <SelectTrigger
              aria-label='Period'
              className='h-9 w-[150px] bg-background'
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIODS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={search.creator_size ?? 'any'}
            onValueChange={(v) =>
              onChange({ creator_size: v as DiscoverSearch['creator_size'] })
            }
            disabled={searching}
          >
            <SelectTrigger
              aria-label='Creator size'
              className='h-9 w-[180px] bg-background'
              title={searching ? QUERY_ONLY_HINT : undefined}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CREATOR_SIZES.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Segmented
            label='Video length'
            value={search.duration ?? 'any'}
            options={DURATIONS}
            onChange={(v) =>
              onChange({ duration: v as DiscoverSearch['duration'] })
            }
          />

          <Popover>
            <PopoverTrigger asChild>
              <Button variant='outline' className='h-9 bg-background'>
                <SlidersHorizontal aria-hidden />
                More
                {extra > 0 && (
                  <span className='rounded-full bg-primary px-1.5 text-xs text-primary-foreground'>
                    {extra}
                  </span>
                )}
              </Button>
            </PopoverTrigger>
            <PopoverContent align='start' className='w-72'>
              <MoreFilters
                key={`${search.niche}-${search.region}-${search.min_views}`}
                search={search}
                searching={searching}
                onApply={onChange}
              />
            </PopoverContent>
          </Popover>

          {activeFilterCount(search) > 0 && (
            <Button
              variant='ghost'
              className='h-9'
              onClick={() => {
                setText('')
                onReset()
              }}
            >
              <RotateCcw aria-hidden />
              Reset
            </Button>
          )}
        </div>

        {sorts.length > 0 && (
          <div className='ms-auto flex items-center gap-2'>
            <span className='text-sm text-muted-foreground max-sm:sr-only'>
              Sort
            </span>
            {searching ? (
              <span
                className='inline-flex h-9 items-center rounded-md border bg-background px-3 text-sm'
                title='Topic search has one order: relevance to the text'
              >
                Relevance
              </span>
            ) : (
              <Segmented
                label='Sort by'
                value={search.sort ?? 'views'}
                options={sorts}
                onChange={(v) =>
                  onChange({ sort: v as DiscoverSearch['sort'] })
                }
              />
            )}
          </div>
        )}
      </div>
      {searching && (
        <p className='px-1 text-xs text-muted-foreground'>
          With topic search, creator size, region and minimum views do not
          apply.
        </p>
      )}
    </div>
  )
}

function MoreFilters({
  search,
  searching,
  onApply,
}: {
  search: DiscoverSearch
  searching: boolean
  onApply: (patch: Partial<DiscoverSearch>) => void
}) {
  const [niche, setNiche] = useState(search.niche ?? '')
  const [region, setRegion] = useState(search.region ?? 'any')
  const [minViews, setMinViews] = useState(
    search.min_views != null ? String(search.min_views) : ''
  )
  const parsed = minViews === '' ? undefined : Number(minViews)
  const invalid = parsed != null && (!Number.isInteger(parsed) || parsed < 0)

  return (
    <form
      className='grid gap-3'
      onSubmit={(e) => {
        e.preventDefault()
        if (invalid) return
        onApply({
          niche: niche.trim() || undefined,
          region: region === 'any' ? undefined : region,
          min_views: parsed,
        })
      }}
    >
      <div className='grid gap-1.5'>
        <Label htmlFor='niche'>Niche label</Label>
        <Input
          id='niche'
          value={niche}
          maxLength={100}
          onChange={(e) => setNiche(e.target.value)}
          placeholder='e.g. demo'
        />
      </div>
      <div className='grid gap-1.5'>
        <Label htmlFor='region'>Region</Label>
        <Select value={region} onValueChange={setRegion} disabled={searching}>
          <SelectTrigger id='region' className='w-full'>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value='any'>Any region</SelectItem>
            {REGIONS.map((r) => (
              <SelectItem key={r} value={r}>
                {r}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className='grid gap-1.5'>
        <Label htmlFor='min-views'>Minimum views</Label>
        <Input
          id='min-views'
          inputMode='numeric'
          value={minViews}
          disabled={searching}
          onChange={(e) => setMinViews(e.target.value.replace(/[^0-9]/g, ''))}
          aria-invalid={invalid}
          placeholder='No minimum'
        />
      </div>
      {searching && (
        <p className='text-xs text-muted-foreground'>{QUERY_ONLY_HINT}.</p>
      )}
      <Button type='submit' disabled={invalid}>
        Apply
      </Button>
    </form>
  )
}
