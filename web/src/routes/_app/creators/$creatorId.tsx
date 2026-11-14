import { createFileRoute } from '@tanstack/react-router'
import { CreatorDetail } from '@/features/creators/detail'
import { creatorVideosSearchSchema } from '@/features/creators/search-params'

export const Route = createFileRoute('/_app/creators/$creatorId')({
  validateSearch: creatorVideosSearchSchema,
  component: CreatorDetail,
})
