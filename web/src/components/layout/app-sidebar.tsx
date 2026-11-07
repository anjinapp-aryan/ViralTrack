import { Link } from '@tanstack/react-router'
import { FlaskConical } from 'lucide-react'
import { Logo } from '@/assets/logo'
import { useLayout } from '@/context/layout-provider'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar'
import { sidebarData } from './data/sidebar-data'
import { NavGroup } from './nav-group'

export function AppSidebar() {
  const { collapsible, variant } = useLayout()
  const { setOpenMobile } = useSidebar()
  return (
    <Sidebar collapsible={collapsible} variant={variant}>
      {/* one landmark for the whole sidebar, so its content is reachable by landmark navigation */}
      <nav aria-label='Primary' className='flex min-h-0 flex-1 flex-col'>
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size='lg' asChild>
                <Link to='/' onClick={() => setOpenMobile(false)}>
                  <span className='grid size-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-cyan-500 via-teal-500 to-violet-500 text-white shadow-sm'>
                    <Logo className='size-5' />
                  </span>
                  <span className='grid flex-1 text-start leading-tight'>
                    <span className='truncate font-semibold tracking-tight'>
                      ViralTrack
                    </span>
                    <span className='truncate text-xs text-muted-foreground'>
                      Creator intelligence
                    </span>
                  </span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>
        <SidebarContent>
          {sidebarData.navGroups.map((props) => (
            <NavGroup key={props.title} {...props} />
          ))}
        </SidebarContent>
        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                size='lg'
                asChild
                tooltip='Local development build: no accounts, not for public use'
              >
                <Link to='/sources' hash='local-build'>
                  <span className='grid size-8 shrink-0 place-items-center rounded-lg border border-violet-500/40 text-violet-600 dark:text-violet-300'>
                    <FlaskConical className='size-4' aria-hidden />
                  </span>
                  <span className='grid flex-1 text-start text-xs leading-tight'>
                    <span className='font-medium'>Local development</span>
                    <span className='text-muted-foreground'>
                      No accounts · localhost only
                    </span>
                  </span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </nav>
      <SidebarRail />
    </Sidebar>
  )
}
