import { createFileRoute } from '@tanstack/react-router'
import { Creators } from '@/features/creators'
import { creatorsSearchSchema } from '@/features/creators/search-params'

export const Route = createFileRoute('/_app/creators/')({
  validateSearch: creatorsSearchSchema,
  component: Creators,
})
