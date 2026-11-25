/** The AI workspace's pages: one list feeds the sidebar, the in-page navigation and the page headings. */
import {
  BrainCircuit,
  Clapperboard,
  FileText,
  Globe2,
  LayoutDashboard,
  Lightbulb,
  Music2,
} from 'lucide-react'
import type { Category } from './search-params'

export type Section = {
  to:
    | '/ai'
    | '/ai/discover'
    | '/ai/countries'
    | '/ai/music'
    | '/ai/video'
    | '/ai/opportunities'
    | '/ai/briefs'
  title: string
  description: string
  icon: React.ElementType
}

export const SECTIONS: Section[] = [
  {
    to: '/ai',
    title: 'Overview',
    description:
      'How the collected corpus was classified, and what AI content it holds.',
    icon: LayoutDashboard,
  },
  {
    to: '/ai/discover',
    title: 'Browse AI Content',
    description:
      'Every classified video, with its evidence, country, language and format.',
    icon: BrainCircuit,
  },
  {
    to: '/ai/countries',
    title: 'Country Explorer',
    description:
      'AI content in the collected corpus by creator country or discovery market.',
    icon: Globe2,
  },
  {
    to: '/ai/music',
    title: 'AI Music Intelligence',
    description: 'AI music videos and AI music or audio tracks.',
    icon: Music2,
  },
  {
    to: '/ai/video',
    title: 'AI Video Intelligence',
    description: 'AI videos with a soundtrack, and AI stories and explainers.',
    icon: Clapperboard,
  },
  {
    to: '/ai/opportunities',
    title: 'Content Opportunities',
    description:
      'Groups of similar AI videos, with the evidence behind each group.',
    icon: Lightbulb,
  },
  {
    to: '/ai/briefs',
    title: 'Creative Briefs',
    description:
      'Original creative briefs written from the opportunities, ready to edit.',
    icon: FileText,
  },
]

export const MUSIC_SCOPE: readonly Category[] = [
  'AI_MUSIC_VIDEO',
  'AI_MUSIC_AUDIO',
]
export const VIDEO_SCOPE: readonly Category[] = [
  'AI_VIDEO_WITH_MUSIC',
  'AI_NORMAL_VIDEO',
]
