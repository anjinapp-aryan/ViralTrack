import { createFileRoute } from '@tanstack/react-router'
import { OpportunitiesPage } from '@/features/ai/pages/opportunities'

export const Route = createFileRoute('/_app/ai/opportunities')({
  component: OpportunitiesPage,
})
