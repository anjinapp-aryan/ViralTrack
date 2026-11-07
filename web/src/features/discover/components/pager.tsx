import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { PageMeta } from '@/lib/api/client'
import { Button } from '@/components/ui/button'

const WINDOW = 1000 // the API's result window

/** Previous / next within the API's limits. `has_more: null` means more may exist beyond the window. */
export function Pager({
  meta,
  onPage,
  busy,
}: {
  meta: PageMeta
  onPage: (page: number) => void
  busy: boolean
}) {
  const atWindowEnd = meta.page * meta.page_size >= WINDOW
  const canNext = meta.has_more === true && !atWindowEnd
  if (meta.page === 1 && !canNext && meta.has_more !== null) return null
  return (
    <nav
      aria-label='Pagination'
      className='flex flex-wrap items-center justify-between gap-3 border-t pt-4'
    >
      <span className='text-sm text-muted-foreground'>
        Page <span className='tabular-nums'>{meta.page}</span>
        {meta.has_more === null &&
          ' · more may exist beyond the first 1,000 results; narrow the filters'}
      </span>
      <div className='flex gap-2'>
        <Button
          variant='outline'
          size='sm'
          disabled={meta.page <= 1 || busy}
          onClick={() => onPage(meta.page - 1)}
        >
          <ChevronLeft aria-hidden />
          Previous
        </Button>
        <Button
          variant='outline'
          size='sm'
          disabled={!canNext || busy}
          onClick={() => onPage(meta.page + 1)}
        >
          Next
          <ChevronRight aria-hidden />
        </Button>
      </div>
    </nav>
  )
}
