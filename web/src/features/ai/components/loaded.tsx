import { cn } from '@/lib/utils'
import { ErrorResults } from '@/features/discover/components/states'
import { PanelSkeleton } from './parts'

type Query<T> = {
  data?: T
  isPending: boolean
  isError: boolean
  isFetching: boolean
  error: unknown
  refetch: () => unknown
  isPlaceholderData?: boolean
}

/** One query's states: a loading skeleton, an error with an explicit Retry (never automatic), then content. */
export function Loaded<T>({
  q,
  label,
  children,
}: {
  q: Query<T>
  label: string
  children: (data: T) => React.ReactNode
}) {
  if (q.isPending) return <PanelSkeleton label={label} />
  if (q.isError && !q.data)
    return (
      <ErrorResults
        error={q.error}
        onRetry={() => q.refetch()}
        retrying={q.isFetching}
      />
    )
  if (!q.data) return null
  return (
    <section
      aria-label={label}
      aria-busy={q.isFetching}
      className={cn(
        'flex flex-col gap-5 transition-opacity',
        q.isPlaceholderData && 'opacity-60'
      )}
    >
      {children(q.data)}
    </section>
  )
}
