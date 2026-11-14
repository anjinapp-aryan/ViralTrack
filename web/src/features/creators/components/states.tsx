import { Link } from '@tanstack/react-router'
import { ArrowLeft, UserX, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export const CREATORS_GRID =
  'grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(min(100%,15rem),1fr))]'

export function CreatorsSkeleton({ count = 12 }: { count?: number }) {
  return (
    <div role='status' aria-label='Loading creators' className={CREATORS_GRID}>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className='rounded-xl border bg-card p-4'>
          <div className='flex items-center gap-3'>
            <Skeleton className='size-11 rounded-full' />
            <div className='flex-1 space-y-2'>
              <Skeleton className='h-4 w-2/3' />
              <Skeleton className='h-3 w-1/3' />
            </div>
          </div>
          <Skeleton className='mt-5 h-4 w-3/4' />
        </div>
      ))}
    </div>
  )
}

function Panel({
  icon,
  title,
  children,
  action,
}: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <div className='flex flex-col items-center rounded-xl border border-dashed px-6 py-14 text-center'>
      <div className='grid size-11 place-items-center rounded-full bg-muted text-muted-foreground'>
        {icon}
      </div>
      <h2 className='mt-4 text-base font-semibold'>{title}</h2>
      <div className='mt-1 max-w-md text-sm text-muted-foreground'>
        {children}
      </div>
      {action && <div className='mt-5'>{action}</div>}
    </div>
  )
}

export function EmptyCreators({ onReset }: { onReset: () => void }) {
  return (
    <Panel
      icon={<Users aria-hidden className='size-5' />}
      title='No creators match these filters'
      action={
        <Button variant='outline' onClick={onReset}>
          Reset filters
        </Button>
      }
    >
      Creators are listed from the videos in the collected corpus, so a creator
      appears only when one of their videos matches. Try a longer period or a
      larger creator size.
    </Panel>
  )
}

export function EmptyCreatorVideos({ period }: { period: string }) {
  return (
    <Panel
      icon={<Users aria-hidden className='size-5' />}
      title='No videos collected for this creator'
    >
      {period === 'all'
        ? 'The local data source has no videos for this creator yet.'
        : 'No collected video of this creator falls in this period. Try a longer one.'}
    </Panel>
  )
}

export function CreatorNotCollected() {
  return (
    <Panel
      icon={<UserX aria-hidden className='size-5' />}
      title='This creator is not in the collected data'
      action={
        <Button asChild variant='outline'>
          <Link to='/creators'>
            <ArrowLeft aria-hidden />
            Back to creators
          </Link>
        </Button>
      }
    >
      The local data source has no record of this creator. Nothing was looked up
      on the platform.
    </Panel>
  )
}
