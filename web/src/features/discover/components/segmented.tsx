import { cn } from '@/lib/utils'

type Option = {
  value: string
  label: string
  disabled?: boolean
  title?: string
}

type Props = {
  label: string
  value: string
  options: readonly Option[]
  onChange: (value: string) => void
  disabled?: boolean
}

/** A small single-choice button group (radio semantics, arrow keys move between options). */
export function Segmented({
  label,
  value,
  options,
  onChange,
  disabled,
}: Props) {
  return (
    <div
      role='radiogroup'
      aria-label={label}
      className={cn(
        'inline-flex h-9 items-center rounded-md border bg-muted/40 p-0.5',
        disabled && 'opacity-50'
      )}
      onKeyDown={(e) => {
        if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
        const enabled = options.filter((o) => !o.disabled)
        const i = enabled.findIndex((o) => o.value === value)
        const next =
          enabled[
            (i + (e.key === 'ArrowRight' ? 1 : -1) + enabled.length) %
              enabled.length
          ]
        if (next) {
          e.preventDefault()
          onChange(next.value)
          const el = e.currentTarget.querySelector<HTMLButtonElement>(
            `[data-value="${next.value}"]`
          )
          el?.focus()
        }
      }}
    >
      {options.map((o) => {
        const checked = o.value === value
        return (
          <button
            key={o.value}
            type='button'
            role='radio'
            aria-checked={checked}
            data-value={o.value}
            tabIndex={checked ? 0 : -1}
            disabled={disabled || o.disabled}
            title={o.title}
            onClick={() => onChange(o.value)}
            className={cn(
              'h-full rounded-[5px] px-3 text-sm whitespace-nowrap text-muted-foreground transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed',
              checked &&
                'bg-background font-medium text-foreground shadow-sm ring-1 ring-border'
            )}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
