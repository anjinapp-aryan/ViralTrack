import { useState } from 'react'
import { ChevronDown, RotateCcw, SlidersHorizontal, X } from 'lucide-react'
import type { Count } from '@/lib/api/client'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
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
import { Segmented } from '@/features/discover/components/segmented'
import { PERIODS } from '@/features/discover/search-params'
import {
  CATEGORY_LABEL,
  FORMAT_LABEL,
  STATUS_HINT,
  STATUS_LABEL,
  VERIFIED_SHORTS_UNAVAILABLE,
  countryName,
  languageName,
} from '../labels'
import {
  CATEGORIES,
  DEFAULT_PERIOD,
  DEFAULT_STATUSES,
  FORMAT_CHOICES,
  STATUSES,
  activeFilters,
  type AiSearch,
  type Category,
} from '../search-params'

type Props = {
  search: AiSearch
  countries: Count[] | undefined
  languages: Count[] | undefined
  onChange: (
    patch: Partial<AiSearch> | ((prev: AiSearch) => Partial<AiSearch>)
  ) => void
  onReset: () => void
  /** Discover pages: offer the approved sorts. */
  showSort?: boolean
  /** Focused pages: only these categories can be chosen. */
  scope?: readonly Category[]
  /** The Country Explorer chooses countries itself. */
  hideCountry?: boolean
}

function some<T>(list: T[]): T[] | undefined {
  return list.length ? list : undefined
}

function toggle<T>(list: readonly T[] | undefined, value: T): T[] {
  const set = new Set(list ?? [])
  if (set.has(value)) set.delete(value)
  else set.add(value)
  return [...set]
}

function Group({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      role='group'
      aria-label={label}
      className={cn('flex max-w-full min-w-0 flex-col gap-1.5', className)}
    >
      <span className='text-[11px] font-medium tracking-wide text-muted-foreground uppercase'>
        {label}
      </span>
      <div className='flex max-w-full flex-wrap items-center gap-2 overflow-x-auto'>
        {children}
      </div>
    </div>
  )
}

function Chips({
  label,
  values,
  selected,
  names,
  hints,
  onToggle,
}: {
  label: string
  values: readonly string[]
  selected: readonly string[]
  names: Record<string, string>
  hints?: Record<string, string>
  onToggle: (value: string) => void
}) {
  return (
    <div role='group' aria-label={label} className='flex flex-wrap gap-1.5'>
      {values.map((v) => {
        const on = selected.includes(v)
        return (
          <button
            key={v}
            type='button'
            aria-pressed={on}
            title={hints?.[v]}
            onClick={() => onToggle(v)}
            className={cn(
              'h-8 rounded-full border px-3 text-[13px] transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring',
              on
                ? 'border-primary bg-primary/15 font-medium text-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
          >
            {names[v] ?? v}
          </button>
        )
      })}
    </div>
  )
}

/** A multi-select over the values present in the collected corpus, with their counts. */
function Picker({
  label,
  options,
  selected,
  name,
  onToggle,
  onClear,
}: {
  label: string
  options: Count[]
  selected: string[]
  name: (code: string) => string
  onToggle: (value: string) => void
  onClear: () => void
}) {
  const [query, setQuery] = useState('')
  const shown = options.filter((o) =>
    `${name(o.key)} ${o.key}`.toLowerCase().includes(query.toLowerCase())
  )
  const summary =
    selected.length === 0
      ? `${label}: all`
      : selected.length === 1
        ? `${label}: ${name(selected[0])}`
        : `${label}: ${selected.length} selected`
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant='outline'
          className={cn(
            'h-9 gap-1.5 font-normal',
            selected.length > 0 && 'border-primary bg-primary/10'
          )}
        >
          {summary}
          <ChevronDown aria-hidden className='size-4 opacity-60' />
        </Button>
      </PopoverTrigger>
      <PopoverContent align='start' className='w-72 p-2'>
        <fieldset>
          <legend className='px-1 pb-1.5 text-xs text-muted-foreground'>
            {label} in the collected corpus (items)
          </legend>
          {options.length > 6 && (
            <input
              type='search'
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Search ${label.toLowerCase()}`}
              aria-label={`Search ${label.toLowerCase()}`}
              className='mb-1.5 h-8 w-full rounded-md border bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring'
            />
          )}
          {shown.length === 0 ? (
            <p className='px-1 py-2 text-sm text-muted-foreground'>
              {options.length === 0 ? 'No values in this window.' : 'No match.'}
            </p>
          ) : (
            <ul className='max-h-72 overflow-auto'>
              {shown.map((o) => (
                <li key={o.key}>
                  <label className='flex cursor-pointer items-center gap-2 rounded-md px-1.5 py-1 text-sm hover:bg-muted'>
                    <input
                      type='checkbox'
                      className='size-4 accent-primary'
                      checked={selected.includes(o.key)}
                      onChange={() => onToggle(o.key)}
                    />
                    <span className='flex-1 truncate'>{name(o.key)}</span>
                    <span className='text-muted-foreground tabular-nums'>
                      {o.count}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          {selected.length > 0 && (
            <Button
              variant='ghost'
              size='sm'
              className='mt-1 w-full'
              onClick={onClear}
            >
              Worldwide / all
            </Button>
          )}
        </fieldset>
      </PopoverContent>
    </Popover>
  )
}

type Active = { key: string; label: string; clear: Partial<AiSearch> }

function activeList(search: AiSearch): Active[] {
  const out: Active[] = []
  if (search.period && search.period !== DEFAULT_PERIOD)
    out.push({
      key: 'period',
      label: PERIODS.find((p) => p.value === search.period)?.label ?? '',
      clear: { period: undefined },
    })
  for (const c of search.country ?? [])
    out.push({
      key: `country-${c}`,
      label: `${search.basis === 'discovery' ? 'Market' : 'Creator country'}: ${countryName(c)}`,
      clear: {
        country: (search.country ?? []).filter((x) => x !== c),
      },
    })
  for (const l of search.language ?? [])
    out.push({
      key: `language-${l}`,
      label: `Language: ${languageName(l)}`,
      clear: { language: (search.language ?? []).filter((x) => x !== l) },
    })
  if (search.format)
    out.push({
      key: 'format',
      label: FORMAT_LABEL[search.format],
      clear: { format: undefined },
    })
  if (search.status?.length)
    out.push({
      key: 'status',
      label: `Status: ${search.status.map((s) => STATUS_LABEL[s]).join(', ')}`,
      clear: { status: undefined },
    })
  for (const c of search.category ?? [])
    out.push({
      key: `category-${c}`,
      label: CATEGORY_LABEL[c],
      clear: {
        category: (search.category ?? []).filter((x) => x !== c),
      },
    })
  return out
}

export function AiFilters({
  search,
  countries,
  languages,
  onChange,
  onReset,
  showSort,
  scope,
  hideCountry,
}: Props) {
  const statuses = search.status ?? [...DEFAULT_STATUSES]
  const basis = search.basis ?? 'creator'
  const active = activeList(search)
  const count = activeFilters(search)
  const contentCount =
    (search.status?.length ? 1 : 0) + (search.category?.length ? 1 : 0)
  const [open, setOpen] = useState(contentCount > 0)
  const clean = (patch: Partial<AiSearch>) => {
    const next: Partial<AiSearch> = { ...patch }
    for (const k of Object.keys(next) as (keyof AiSearch)[]) {
      const v = next[k]
      if (Array.isArray(v) && v.length === 0) next[k] = undefined as never
    }
    onChange(next)
  }
  return (
    <section
      aria-label='Filters'
      className='flex flex-col gap-3 rounded-xl border bg-card p-3 shadow-xs sm:p-4'
    >
      <div className='flex flex-wrap items-end gap-x-6 gap-y-3'>
        <Group label='Date range'>
          <Select
            value={search.period ?? DEFAULT_PERIOD}
            onValueChange={(v) => onChange({ period: v })}
          >
            <SelectTrigger className='w-40' aria-label='Date range'>
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
        </Group>
        <Group label='Market'>
          <Segmented
            label='Country basis'
            value={basis}
            options={[
              {
                value: 'creator',
                label: 'Creator country',
                title: 'The country the creator declared on the channel',
              },
              {
                value: 'discovery',
                label: 'Discovery market',
                title: 'The market of a ViralTrack regional collection',
              },
            ]}
            onChange={(v) =>
              onChange({ basis: v as AiSearch['basis'], country: undefined })
            }
          />
          {!hideCountry && (
            <Picker
              label='Country'
              options={countries ?? []}
              selected={search.country ?? []}
              name={countryName}
              onToggle={(c) =>
                onChange((prev) => ({ country: some(toggle(prev.country, c)) }))
              }
              onClear={() => onChange({ country: undefined })}
            />
          )}
        </Group>
        <Group label='Language'>
          <Picker
            label='Language'
            options={languages ?? []}
            selected={search.language ?? []}
            name={languageName}
            onToggle={(l) =>
              onChange((prev) => ({ language: some(toggle(prev.language, l)) }))
            }
            onClear={() => onChange({ language: undefined })}
          />
        </Group>
        <Group label='Format'>
          <Segmented
            label='Format'
            value={search.format ?? 'any'}
            options={[
              { value: 'any', label: 'Any' },
              {
                value: 'verified_shorts',
                label: 'Verified Shorts',
                disabled: true,
                title: VERIFIED_SHORTS_UNAVAILABLE,
              },
              ...FORMAT_CHOICES.map((f) => ({
                value: f,
                label:
                  f === 'short_form' ? 'Short-form ≤ 3 min' : FORMAT_LABEL[f],
                title:
                  f === 'short_form' ? VERIFIED_SHORTS_UNAVAILABLE : undefined,
              })),
            ]}
            onChange={(v) =>
              onChange({
                format: v === 'any' ? undefined : (v as AiSearch['format']),
              })
            }
          />
        </Group>
        {showSort && (
          <Group label='Order'>
            <Segmented
              label='Sort'
              value={search.sort ?? 'views'}
              options={[
                { value: 'views', label: 'Most views' },
                { value: 'published_at', label: 'Newest' },
              ]}
              onChange={(v) => onChange({ sort: v as AiSearch['sort'] })}
            />
          </Group>
        )}
      </div>

      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <Button
            variant='ghost'
            size='sm'
            className='-ms-2 gap-1.5 text-muted-foreground'
          >
            <SlidersHorizontal aria-hidden />
            Content: AI status and category
            {contentCount > 0 && (
              <span className='rounded-full bg-primary px-1.5 text-[11px] font-semibold text-primary-foreground'>
                {contentCount}
              </span>
            )}
            <ChevronDown
              aria-hidden
              className={cn('transition-transform', open && 'rotate-180')}
            />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className='flex flex-col gap-3 pt-2'>
          <Group label='AI status'>
            <Chips
              label='AI status'
              values={STATUSES}
              selected={statuses}
              names={STATUS_LABEL}
              hints={STATUS_HINT}
              onToggle={(v) =>
                onChange((prev) => ({
                  status: some(
                    toggle(
                      prev.status ?? [...DEFAULT_STATUSES],
                      v as (typeof STATUSES)[number]
                    )
                  ),
                }))
              }
            />
          </Group>
          <Group label='Content category'>
            <Chips
              label='Content category'
              values={scope ?? CATEGORIES}
              selected={search.category ?? []}
              names={CATEGORY_LABEL}
              onToggle={(v) =>
                onChange((prev) => ({
                  category: some(toggle(prev.category, v as Category)),
                }))
              }
            />
          </Group>
        </CollapsibleContent>
      </Collapsible>

      <div className='flex flex-wrap items-center gap-2 border-t pt-3 text-sm'>
        <span
          className='text-muted-foreground'
          data-testid='active-filter-count'
        >
          {count === 0
            ? 'No filters: Confirmed and Likely AI, last 30 days, worldwide'
            : `${count} active ${count === 1 ? 'filter' : 'filters'}`}
        </span>
        {active.map((a) => (
          <button
            key={a.key}
            type='button'
            onClick={() => clean(a.clear)}
            aria-label={`Remove filter ${a.label}`}
            className='inline-flex h-7 items-center gap-1 rounded-full border bg-muted/50 ps-2.5 pe-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring'
          >
            {a.label}
            <X aria-hidden className='size-3.5' />
          </button>
        ))}
        {count > 0 && (
          <Button
            variant='ghost'
            size='sm'
            className='ms-auto'
            onClick={onReset}
          >
            <RotateCcw aria-hidden />
            Reset filters
          </Button>
        )}
      </div>
    </section>
  )
}
