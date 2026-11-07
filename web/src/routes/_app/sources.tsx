import { createFileRoute } from '@tanstack/react-router'
import { DataSources } from '@/features/sources'

export const Route = createFileRoute('/_app/sources')({
  component: DataSources,
})
