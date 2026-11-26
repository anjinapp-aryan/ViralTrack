import { Compass, Database, Users } from 'lucide-react'
import { SECTIONS } from '@/features/ai/sections'
import { type SidebarData } from '../types'

/** Only pages that work are listed. Nothing here is a placeholder for a future feature. */
export const sidebarData: SidebarData = {
  navGroups: [
    {
      title: 'AI Content Intelligence',
      items: SECTIONS.map((s) => ({ title: s.title, url: s.to, icon: s.icon })),
    },
    {
      title: 'Explore',
      items: [
        { title: 'Discover', url: '/', icon: Compass },
        { title: 'Creators', url: '/creators', icon: Users },
      ],
    },
    {
      title: 'Reference',
      items: [{ title: 'Data sources', url: '/sources', icon: Database }],
    },
  ],
}
