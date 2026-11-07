import { ApiStatus } from '@/components/api-status'
import { ConfigDrawer } from '@/components/config-drawer'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { Header } from './header'

/** The header every ViralTrack page uses: command menu, API status, theme and layout settings. */
export function AppHeader() {
  return (
    <Header fixed>
      <Search placeholder='Go to…' />
      <div className='ms-auto flex items-center gap-2 sm:gap-3'>
        <ApiStatus />
        <ThemeSwitch />
        <ConfigDrawer />
      </div>
    </Header>
  )
}
