import { Play } from 'lucide-react'
import { cn } from '@/lib/utils'

// Brand palette (cyan, teal, violet). The tint is chosen from the video id only so cards differ;
// it carries no meaning about the video.
const TINTS = [
  'from-cyan-500/30 via-sky-500/10 to-teal-500/25',
  'from-teal-500/30 via-emerald-500/10 to-violet-500/20',
  'from-violet-500/30 via-indigo-500/10 to-cyan-500/20',
]

function tintFor(seed: string): string {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  return TINTS[h % TINTS.length]
}

/** A 16:9 placeholder. No image is requested from the platform; the category label is real metadata. */
export function ThumbnailPlaceholder({
  seed,
  category,
  className,
}: {
  seed: string
  category?: string | null
  className?: string
}) {
  return (
    <div
      className={cn(
        'relative aspect-video w-full overflow-hidden bg-muted bg-gradient-to-br',
        tintFor(seed),
        className
      )}
    >
      {/* fine dot texture, pure CSS */}
      <div
        aria-hidden
        className='absolute inset-0 [background-image:radial-gradient(currentColor_1px,transparent_1px)] [background-size:14px_14px] text-foreground/15 opacity-40'
      />
      {category && (
        <span className='absolute start-2 top-2 max-w-[70%] truncate rounded-md bg-background/80 px-1.5 py-0.5 text-[11px] font-medium text-foreground/80 backdrop-blur-sm'>
          {category}
        </span>
      )}
      <div className='absolute inset-0 grid place-items-center'>
        <span className='grid size-10 place-items-center rounded-full bg-background/75 text-foreground/70 shadow-sm ring-1 ring-border backdrop-blur-sm transition-transform duration-200 group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:scale-100'>
          <Play aria-hidden className='ms-0.5 size-4' />
        </span>
      </div>
      <span className='sr-only'>Thumbnail not shown</span>
    </div>
  )
}
