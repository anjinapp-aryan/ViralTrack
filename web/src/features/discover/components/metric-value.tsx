import { Info } from 'lucide-react'
import type { MetricValue as Metric } from '@/lib/api/client'
import { absoluteDateTime, fullNumber } from '@/lib/format'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

type Props = {
  label: string
  metric: Metric | null
  /** what a null means for this field, e.g. "Hidden by the creator" */
  missing: string
}

/** One value with its kind and provenance. `null` is shown as text; it is never rendered as 0. */
export function MetricValue({ label, metric, missing }: Props) {
  return (
    <div className='rounded-lg border bg-muted/30 p-3'>
      <div className='flex items-center justify-between gap-2'>
        <span className='text-xs text-muted-foreground'>{label}</span>
        {metric && (
          <Badge
            variant='outline'
            className='h-5 px-1.5 text-[10px] tracking-wide uppercase'
          >
            {metric.kind}
          </Badge>
        )}
      </div>
      {metric ? (
        <div className='mt-1 flex items-center gap-1.5'>
          <span className='text-lg font-semibold tabular-nums'>
            {fullNumber(metric.value)}
          </span>
          <Tooltip>
            <TooltipTrigger
              aria-label={`Where the ${label.toLowerCase()} value comes from`}
              className='rounded text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none'
            >
              <Info className='size-3.5' />
            </TooltipTrigger>
            <TooltipContent className='max-w-64 text-xs'>
              <p>Source: {metric.source}</p>
              <p>
                Read from the platform:{' '}
                {absoluteDateTime(metric.collected_at) ?? 'time not reported'}
              </p>
              <p>
                First stored:{' '}
                {absoluteDateTime(metric.foundation_first_seen_at) ??
                  'not reported'}
              </p>
              {metric.note && <p className='mt-1'>{metric.note}</p>}
            </TooltipContent>
          </Tooltip>
        </div>
      ) : (
        <p className='mt-1 text-sm text-muted-foreground italic'>{missing}</p>
      )}
    </div>
  )
}
