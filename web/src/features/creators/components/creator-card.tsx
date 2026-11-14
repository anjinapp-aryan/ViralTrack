import { Link } from '@tanstack/react-router'
import { Film, Users } from 'lucide-react'
import type { CreatorRef } from '@/lib/api/client'
import { compactNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

// Brand palette (cyan, teal, violet). The tint comes from the id only so cards differ; it means nothing.
const TINTS = [
  'bg-cyan-500/15 text-cyan-900 dark:text-cyan-300',
  'bg-teal-500/15 text-teal-900 dark:text-teal-300',
  'bg-violet-500/15 text-violet-900 dark:text-violet-300',
]

function tintFor(seed: string): string {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  return TINTS[h % TINTS.length]
}

/** Up to two letters of the name for the avatar. No image is requested from the platform. */
function initials(name: string | null): string {
  const words = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  return (words[0][0] + (words.length > 1 ? words[1][0] : '')).toUpperCase()
}

export function Avatar({
  creator,
  className,
}: {
  creator: CreatorRef
  className?: string
}) {
  return (
    <span
      aria-hidden
      className={cn(
        'grid size-11 shrink-0 place-items-center rounded-full text-sm font-semibold',
        tintFor(creator.id),
        className
      )}
    >
      {initials(creator.name)}
    </span>
  )
}

/** One creator of the discovered videos. Counts are the platform's raw numbers; hidden ones are written out. */
export function CreatorCard({
  creator,
  videosInResult,
}: {
  creator: CreatorRef
  videosInResult: number
}) {
  const followers = compactNumber(creator.followers?.value)
  return (
    <Link
      to='/creators/$creatorId'
      params={{ creatorId: creator.id }}
      className='group flex h-full flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs transition-[transform,box-shadow,border-color] duration-200 outline-none hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md focus-visible:border-primary focus-visible:ring-[3px] focus-visible:ring-ring/40 motion-reduce:transition-none motion-reduce:hover:translate-y-0'
    >
      <div className='flex items-center gap-3'>
        <Avatar creator={creator} />
        <div className='min-w-0'>
          <h3 className='truncate text-[0.95rem] leading-5 font-semibold group-hover:text-primary'>
            {creator.name ?? 'Unknown creator'}
          </h3>
          <p className='truncate text-[13px] text-muted-foreground'>
            {creator.handle ?? 'No handle reported'}
          </p>
        </div>
      </div>
      <div className='mt-auto flex flex-wrap items-baseline gap-x-4 gap-y-1 border-t pt-3 text-[13px] text-muted-foreground'>
        <span className='inline-flex items-baseline gap-1.5'>
          <Users aria-hidden className='size-3.5 self-center' />
          {followers ? (
            <>
              <span className='text-base font-semibold text-foreground tabular-nums'>
                {followers}
              </span>
              followers
            </>
          ) : (
            <span className='italic'>followers hidden or not reported</span>
          )}
        </span>
        <span className='inline-flex items-baseline gap-1.5'>
          <Film aria-hidden className='size-3.5 self-center' />
          <span className='tabular-nums'>{videosInResult}</span>
          {videosInResult === 1 ? 'video' : 'videos'} in these results
        </span>
      </div>
    </Link>
  )
}
