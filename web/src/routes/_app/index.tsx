import { createFileRoute } from '@tanstack/react-router'
import { Discover } from '@/features/discover'
import { discoverSearchSchema } from '@/features/discover/search-params'

export const Route = createFileRoute('/_app/')({
  validateSearch: discoverSearchSchema,
  component: Discover,
})
