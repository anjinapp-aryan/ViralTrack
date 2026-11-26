import { createFileRoute } from '@tanstack/react-router'
import { MusicPage } from '@/features/ai/pages/discover'

export const Route = createFileRoute('/_app/ai/music')({
  component: MusicPage,
})
