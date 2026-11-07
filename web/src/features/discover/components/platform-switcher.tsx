import type { PlatformInfo } from '@/lib/api/client'
import { cn } from '@/lib/utils'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

const NAMES: Record<string, string> = {
  youtube: 'YouTube',
  instagram: 'Instagram',
  tiktok: 'TikTok',
}

/** Platforms as the API reports them. Unavailable ones are shown, disabled, with the API's reason. */
export function PlatformSwitcher({
  platforms,
}: {
  platforms: PlatformInfo[] | undefined
}) {
  if (!platforms) return null
  return (
    <div role='group' aria-label='Platform' className='flex flex-wrap gap-2'>
      {platforms.map((p) => {
        const name = NAMES[p.platform] ?? p.platform
        const chip = (
          <span
            className={cn(
              'inline-flex h-8 items-center gap-2 rounded-full border px-3 text-sm',
              p.available
                ? 'border-primary/40 bg-primary/10 font-medium text-foreground'
                : 'cursor-not-allowed text-muted-foreground opacity-70'
            )}
            aria-current={p.available ? 'true' : undefined}
            aria-disabled={!p.available || undefined}
          >
            <span
              aria-hidden
              className={cn(
                'size-1.5 rounded-full',
                p.available ? 'bg-teal-500' : 'bg-muted-foreground/50'
              )}
            />
            {name}
            {!p.available && <span className='text-xs'>Unavailable</span>}
            {!p.available && p.reason && (
              <span className='sr-only'>: {p.reason}</span>
            )}
          </span>
        )
        if (p.available) return <span key={p.platform}>{chip}</span>
        return (
          <Tooltip key={p.platform}>
            <TooltipTrigger asChild>
              <span
                tabIndex={0}
                className='rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring'
              >
                {chip}
              </span>
            </TooltipTrigger>
            <TooltipContent className='max-w-72 text-xs'>
              {p.reason ?? 'Not available.'}
            </TooltipContent>
          </Tooltip>
        )
      })}
    </div>
  )
}
