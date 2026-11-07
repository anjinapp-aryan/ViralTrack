import { ExternalLink } from 'lucide-react'
import type { Video } from '@/lib/api/client'
import {
  absoluteDate,
  absoluteDateTime,
  duration,
  isUpToThreeMinutes,
} from '@/lib/format'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { MetricValue } from './metric-value'
import { ThumbnailPlaceholder } from './thumbnail-placeholder'

type Props = {
  video: Video | null
  onClose: () => void
}

const ORIGIN_LABEL: Record<Video['origin'], string> = {
  real_provider_data: 'Real platform data',
  demo: 'DEMO data (synthetic)',
  test: 'TEST data (synthetic)',
}

/** Every approved field of one video, with provenance. Derived values are not shown in phase 1. */
export function QuickView({ video, onClose }: Props) {
  return (
    <Sheet open={video !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        className='w-full gap-0 overflow-y-auto sm:max-w-md'
        // focus the panel itself, not the first info icon (which would pop its tooltip open)
        onOpenAutoFocus={(e) => {
          e.preventDefault()
          ;(e.currentTarget as HTMLElement).focus()
        }}
      >
        {video && (
          <>
            <SheetHeader className='gap-3 pb-2'>
              <ThumbnailPlaceholder
                seed={video.id}
                className='mt-6 rounded-lg border'
              />
              <SheetTitle className='text-base leading-snug'>
                {video.title ?? 'Untitled video'}
              </SheetTitle>
              <SheetDescription>
                {video.creator.name ?? 'Unknown creator'}
                {video.creator.handle ? ` · ${video.creator.handle}` : ''}
              </SheetDescription>
              <div className='flex flex-wrap gap-1.5'>
                <Badge variant='outline'>{ORIGIN_LABEL[video.origin]}</Badge>
                {video.category && (
                  <Badge variant='secondary'>{video.category}</Badge>
                )}
                {isUpToThreeMinutes(video.duration_seconds) && (
                  <Badge variant='secondary'>≤ 3 min</Badge>
                )}
              </div>
            </SheetHeader>

            <div className='grid grid-cols-2 gap-2 px-4'>
              <MetricValue
                label='Views'
                metric={video.metrics.views}
                missing='Not reported'
              />
              <MetricValue
                label='Likes'
                metric={video.metrics.likes}
                missing='Hidden or not reported'
              />
              <MetricValue
                label='Comments'
                metric={video.metrics.comments}
                missing='Not reported'
              />
              <MetricValue
                label='Creator followers'
                metric={video.creator.followers}
                missing='Hidden or not reported'
              />
            </div>

            <dl className='mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 px-4 text-sm'>
              <dt className='text-muted-foreground'>Published</dt>
              <dd>{absoluteDate(video.published_at) ?? 'Not reported'}</dd>
              <dt className='text-muted-foreground'>Length</dt>
              <dd className='tabular-nums'>
                {duration(video.duration_seconds) ?? 'Not reported'}
              </dd>
              <dt className='text-muted-foreground'>Language</dt>
              <dd>{video.language ?? 'Not reported'}</dd>
              <dt className='text-muted-foreground'>Retrieved</dt>
              <dd>{absoluteDateTime(video.retrieved_at) ?? 'Not reported'}</dd>
            </dl>

            <p className='mt-4 px-4 text-xs text-muted-foreground'>
              Values are raw platform counts as stored by the local foundation.
              The time each value was read from the platform is not reported by
              the source, so freshness is shown as the retrieval time.
            </p>

            <div className='mt-auto p-4'>
              <Button asChild variant='outline' className='w-full'>
                <a href={video.url} target='_blank' rel='noopener noreferrer'>
                  Open on{' '}
                  {video.platform === 'youtube' ? 'YouTube' : video.platform}
                  <ExternalLink aria-hidden />
                </a>
              </Button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
