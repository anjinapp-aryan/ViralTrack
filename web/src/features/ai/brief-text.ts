import type { AiOpportunity } from '@/lib/api/client'
import {
  CATEGORY_LABEL,
  FORMAT_LABEL,
  countryName,
  label,
  languageName,
} from './labels'

/** The brief as plain text, for copying into a document (stays on the device; nothing is sent). */
export function briefText(o: AiOpportunity): string {
  const b = o.brief
  return [
    b.opportunity_title,
    `Country: ${b.country ? countryName(b.country) : 'Unknown'} (${b.country_basis}) · Language: ${languageName(b.language_code)}`,
    `Category: ${label(CATEGORY_LABEL, b.category)} · Format: ${label(FORMAT_LABEL, b.format_type)}`,
    `Suggested length: ${b.suggested_duration}`,
    `Audience hypothesis: ${b.audience_hypothesis}`,
    `Theme: ${b.theme}`,
    `Original creative angle: ${b.original_creative_angle}`,
    `Hook: ${b.hook_concept}`,
    'Story outline:',
    ...b.story_outline.map((x, i) => `  ${i + 1}. ${x}`),
    ...(b.music_direction ? [`Music direction: ${b.music_direction}`] : []),
    `Visual direction: ${b.visual_direction}`,
    `Platforms: ${b.platform_recommendations.join(', ')}`,
    'Rights and originality checklist:',
    ...b.rights_checklist.map((x) => `  [ ] ${x}`),
    '',
    b.note,
  ].join('\n')
}
