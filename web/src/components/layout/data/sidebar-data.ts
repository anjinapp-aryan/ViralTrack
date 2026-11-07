import { Compass, Database } from 'lucide-react'
import { type SidebarData } from '../types'

/** Only pages that work are listed. Nothing here is a placeholder for a future feature. */
export const sidebarData: SidebarData = {
  navGroups: [
    {
      title: 'Explore',
      items: [{ title: 'Discover', url: '/', icon: Compass }],
    },
    {
      title: 'Reference',
      items: [{ title: 'Data sources', url: '/sources', icon: Database }],
    },
  ],
}
