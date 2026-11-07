import { createFileRoute } from '@tanstack/react-router'
import { AppLayout } from '@/components/layout/app-layout'

// No authentication: this is a local development build (see web/README.md). Nothing here pretends to log in.
export const Route = createFileRoute('/_app')({
  component: AppLayout,
})
