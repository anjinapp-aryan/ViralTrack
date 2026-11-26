import { createFileRoute } from '@tanstack/react-router'
import { VideoPage } from '@/features/ai/pages/discover'

export const Route = createFileRoute('/_app/ai/video')({
  component: VideoPage,
})
