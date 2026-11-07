import { useReadiness } from '@/lib/api/queries'
import { cn } from '@/lib/utils'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

/** Readiness of the local ViralTrack API and its data source (GET /api/v1/health/ready, free). */
export function ApiStatus() {
  const { data, isPending, isError } = useReadiness()
  const ready = data?.status === 'ready'
  const label = isPending
    ? 'Checking API'
    : isError
      ? 'API offline'
      : ready
        ? 'API ready'
        : 'Data source unavailable'
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          className='inline-flex h-8 items-center gap-2 rounded-full border px-3 text-xs text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring'
        >
          <span
            aria-hidden
            className={cn(
              'size-2 rounded-full',
              isPending
                ? 'bg-muted-foreground/40'
                : ready
                  ? 'bg-teal-500'
                  : 'bg-amber-500'
            )}
          />
          <span className='max-sm:sr-only'>{label}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent className='max-w-64 text-xs'>
        {isError
          ? 'The local ViralTrack API (127.0.0.1:8000) is not answering.'
          : data?.checks
            ? Object.entries(data.checks)
                .map(([name, c]) => `${name}: ${c.status.replace('_', ' ')}`)
                .join(' · ')
            : label}
      </TooltipContent>
    </Tooltip>
  )
}
