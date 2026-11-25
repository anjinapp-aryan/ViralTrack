import { createFileRoute } from '@tanstack/react-router'
import { OverviewPage } from '@/features/ai/pages/overview'

export const Route = createFileRoute('/_app/ai/')({
  component: OverviewPage,
})
