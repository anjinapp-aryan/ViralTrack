import { CheckCircle2, CircleSlash, FlaskConical } from 'lucide-react'
import { useCapabilities } from '@/lib/api/queries'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { AppHeader } from '@/components/layout/app-header'
import { Main } from '@/components/layout/main'
import { ErrorResults } from '@/features/discover/components/states'
import { SORT_LABELS } from '@/features/discover/search-params'

const PLATFORM_NAMES: Record<string, string> = {
  youtube: 'YouTube',
  instagram: 'Instagram',
  tiktok: 'TikTok',
}
// Phase 1 displays raw values only; derived values exist in the API but are not shown in this UI.
const SHOWN_IN_UI = new Set(['views', 'likes', 'comments', 'followers'])

/** What this deployment can and cannot do, read from GET /api/v1/capabilities. */
export function DataSources() {
  const { data, isPending, isError, error, refetch, isFetching } =
    useCapabilities()
  return (
    <>
      <AppHeader />
      <Main
        fluid
        className='mx-auto flex w-full max-w-[1680px] flex-col gap-5 px-4 py-6 lg:px-6'
      >
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>Data sources</h1>
          <p className='text-sm text-muted-foreground'>
            Where the numbers come from, which platforms are connected and what
            this build does not do.
          </p>
        </div>

        {isPending ? (
          <div className='grid gap-4 md:grid-cols-2'>
            <Skeleton className='h-48' />
            <Skeleton className='h-48' />
          </div>
        ) : isError ? (
          <ErrorResults
            error={error}
            onRetry={() => refetch()}
            retrying={isFetching}
          />
        ) : (
          <div className='grid gap-4 md:grid-cols-2 2xl:grid-cols-4'>
            <Card>
              <CardHeader>
                <CardTitle>Platforms</CardTitle>
                <CardDescription>
                  Only platforms with an approved data source are connected.
                </CardDescription>
              </CardHeader>
              <CardContent className='grid gap-3'>
                {data.platforms.map((p) => (
                  <div key={p.platform} className='flex gap-3'>
                    {p.available ? (
                      <CheckCircle2
                        aria-hidden
                        className='mt-0.5 size-4 shrink-0 text-teal-600 dark:text-teal-400'
                      />
                    ) : (
                      <CircleSlash
                        aria-hidden
                        className='mt-0.5 size-4 shrink-0 text-muted-foreground'
                      />
                    )}
                    <div className='text-sm'>
                      <p className='font-medium'>
                        {PLATFORM_NAMES[p.platform] ?? p.platform}{' '}
                        <span className='font-normal text-muted-foreground'>
                          {p.available ? '· connected' : '· unavailable'}
                        </span>
                      </p>
                      {p.reason && (
                        <p className='text-muted-foreground'>{p.reason}</p>
                      )}
                      {p.data_origin &&
                        p.data_origin !== 'real_provider_data' && (
                          <Badge variant='outline' className='mt-1'>
                            Serving {p.data_origin.toUpperCase()} data
                          </Badge>
                        )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Ordering</CardTitle>
                <CardDescription>
                  Results are ordered only by values the platform reports.
                </CardDescription>
              </CardHeader>
              <CardContent className='grid gap-2 text-sm'>
                {data.sorts.map((s) => (
                  <div key={s.name} className='flex gap-3'>
                    {s.available ? (
                      <CheckCircle2
                        aria-hidden
                        className='mt-0.5 size-4 shrink-0 text-teal-600 dark:text-teal-400'
                      />
                    ) : (
                      <CircleSlash
                        aria-hidden
                        className='mt-0.5 size-4 shrink-0 text-muted-foreground'
                      />
                    )}
                    <p>
                      <span className='font-medium'>
                        {SORT_LABELS[s.name] ?? s.name.replace(/_/g, ' ')}
                      </span>
                      {!s.available && (
                        <span className='text-muted-foreground'>
                          {' '}
                          · not available: {s.reason}
                        </span>
                      )}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Values shown</CardTitle>
                <CardDescription>
                  Raw counts as the platform reports them. A hidden or missing
                  value is shown as such, never as zero.
                </CardDescription>
              </CardHeader>
              <CardContent className='grid gap-2 text-sm'>
                {data.metrics
                  .filter((m) => SHOWN_IN_UI.has(m.name))
                  .map((m) => (
                    <p key={m.name}>
                      <span className='font-medium capitalize'>{m.name}</span>{' '}
                      <span className='text-muted-foreground'>
                        · {m.kind} · {m.description}
                      </span>
                    </p>
                  ))}
                <p className='text-muted-foreground'>
                  Calculated values and scores are not shown in this version.
                </p>
              </CardContent>
            </Card>

            <Card id='local-build'>
              <CardHeader>
                <CardTitle className='flex items-center gap-2'>
                  <FlaskConical
                    aria-hidden
                    className='size-4 text-violet-600 dark:text-violet-300'
                  />
                  Local development build
                </CardTitle>
                <CardDescription>
                  What this build is and is not.
                </CardDescription>
              </CardHeader>
              <CardContent className='grid gap-2 text-sm text-muted-foreground'>
                <p>
                  Runs on this computer only, against the local ViralTrack API
                  on 127.0.0.1. There are no accounts and no sign-in; it must
                  not be exposed on a network.
                </p>
                <p>
                  It reads data that was already collected. It never collects
                  new data and never spends platform quota.
                </p>
                <p>
                  Thumbnails are not loaded until the use of platform images is
                  reviewed.
                </p>
              </CardContent>
            </Card>
          </div>
        )}
      </Main>
    </>
  )
}
