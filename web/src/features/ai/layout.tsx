import { Link, Outlet, useLocation } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { AppHeader } from '@/components/layout/app-header'
import { Main } from '@/components/layout/main'
import { SECTIONS } from './sections'

/** The AI workspace frame: heading, the section navigation (keeps the shared filters) and the page. */
export function AiLayout() {
  const { pathname } = useLocation()
  const path = pathname.replace(/\/$/, '') || '/'
  const current = SECTIONS.find((s) => s.to === path) ?? SECTIONS[0]
  return (
    <>
      <AppHeader />
      <Main
        fluid
        className='mx-auto flex w-full max-w-[1680px] flex-col gap-5 px-4 py-6 lg:px-6'
      >
        <header className='flex flex-col gap-3'>
          <div>
            <p className='text-xs font-medium tracking-wide text-primary uppercase'>
              AI Content Intelligence
            </p>
            <h1 className='text-2xl font-bold tracking-tight lg:text-[1.7rem]'>
              {current.title}
            </h1>
            <p className='mt-1 max-w-3xl text-sm text-muted-foreground'>
              {current.description} Counts describe the collected corpus only.
              Use them to find themes for original work, never to copy.
            </p>
          </div>
          <nav aria-label='AI workspace' className='-mx-1 overflow-x-auto'>
            <ul className='flex w-max gap-1 px-1 pb-1'>
              {SECTIONS.map((s) => {
                const active = s.to === current.to
                return (
                  <li key={s.to}>
                    <Link
                      to={s.to}
                      search={true as never}
                      aria-current={active ? 'page' : undefined}
                      className={cn(
                        'inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-sm whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring',
                        active
                          ? 'bg-primary/15 font-medium text-foreground'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                      )}
                    >
                      <s.icon aria-hidden className='size-4' />
                      {s.title}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </nav>
        </header>
        <Outlet />
      </Main>
    </>
  )
}
