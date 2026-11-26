import { createFileRoute } from '@tanstack/react-router'
import { DiscoverPage } from '@/features/ai/pages/discover'

export const Route = createFileRoute('/_app/ai/discover')({
  component: DiscoverPage,
})
