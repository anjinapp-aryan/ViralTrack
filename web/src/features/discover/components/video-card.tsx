import type { Video } from '@/lib/api/client'
import {
  absoluteDate,
  compactNumber,
  duration,
  isUpToThreeMinutes,
  relativeTime,
} from '@/lib/format'
import { ThumbnailPlaceholder } from './thumbnail-placeholder'

type Props = {
  video: Video
  onOpen: (video: Video) => void
}

/** One discovered video. Thumbnails are not loaded (counsel review pending): a neutral placeholder is shown. */
export function VideoCard({ video, onOpen }: Props) {
  const views = compactNumber(video.metrics.views?.value)
  const length = duration(video.duration_seconds)
  const age = relativeTime(video.published_at)
  const title = video.title ?? 'Untitled video'
  const creator = video.creator.name ?? 'Unknown creator'
  return (
    <button
      type='button'
      onClick={() => onOpen(video)}
      aria-haspopup='dialog'
      className='group flex h-full flex-col overflow-hidden rounded-xl border bg-card text-start shadow-xs transition-[transform,box-shadow,border-color] duration-200 outline-none hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md focus-visible:border-primary focus-visible:ring-[3px] focus-visible:ring-ring/40 motion-reduce:transition-none motion-reduce:hover:translate-y-0'
    >
      <div className='relative'>
        <ThumbnailPlaceholder seed={video.id} category={video.category} />
        {length && (
          <span className='absolute end-2 bottom-2 rounded-md bg-black/75 px-1.5 py-0.5 text-[11px] font-semibold text-white tabular-nums'>
            {length}
          </span>
        )}
        {isUpToThreeMinutes(video.duration_seconds) && (
          <span className='absolute start-2 bottom-2 rounded-md bg-white/90 px-1.5 py-0.5 text-[11px] font-semibold text-slate-900'>
            ≤ 3 min
          </span>
        )}
      </div>
      <div className='flex flex-1 flex-col gap-2 p-3.5'>
        <h3 className='line-clamp-2 min-h-[2.5rem] text-[0.95rem] leading-5 font-semibold text-foreground group-hover:text-primary'>
          {title}
        </h3>
        <p className='truncate text-[13px] text-muted-foreground'>{creator}</p>
        <div className='mt-auto flex items-baseline gap-1.5 border-t pt-2.5 text-[13px] text-muted-foreground'>
          {views ? (
            <>
              <span className='text-base font-semibold text-foreground tabular-nums'>
                {views}
              </span>
              <span>views</span>
            </>
          ) : (
            <span className='italic'>views not reported</span>
          )}
          <span aria-hidden className='px-0.5'>
            ·
          </span>
          <span title={absoluteDate(video.published_at) ?? undefined}>
            {age ?? <span className='italic'>date not reported</span>}
          </span>
        </div>
      </div>
    </button>
  )
}
