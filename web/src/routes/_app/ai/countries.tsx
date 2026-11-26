import { createFileRoute } from '@tanstack/react-router'
import { CountriesPage } from '@/features/ai/pages/countries'

export const Route = createFileRoute('/_app/ai/countries')({
  component: CountriesPage,
})
