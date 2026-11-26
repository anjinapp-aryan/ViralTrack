import { createFileRoute } from '@tanstack/react-router'
import { BriefsPage } from '@/features/ai/pages/briefs'

export const Route = createFileRoute('/_app/ai/briefs')({
  component: BriefsPage,
})
