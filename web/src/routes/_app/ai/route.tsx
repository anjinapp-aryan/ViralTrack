import { createFileRoute } from '@tanstack/react-router'
import { AiLayout } from '@/features/ai/layout'
import { aiSearchSchema } from '@/features/ai/search-params'

export const Route = createFileRoute('/_app/ai')({
  validateSearch: aiSearchSchema,
  component: AiLayout,
})
