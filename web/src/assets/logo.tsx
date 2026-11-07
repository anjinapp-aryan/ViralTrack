import { type SVGProps } from 'react'
import { cn } from '@/lib/utils'

/** ViralTrack mark: a rising trace through three observed points. */
export function Logo({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox='0 0 24 24'
      xmlns='http://www.w3.org/2000/svg'
      height='24'
      width='24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2.2'
      strokeLinecap='round'
      strokeLinejoin='round'
      className={cn('size-6', className)}
      aria-hidden='true'
      {...props}
    >
      <path d='M3 17l5.5-5.5 4 4L21 7' />
      <circle cx='8.5' cy='11.5' r='1.2' fill='currentColor' stroke='none' />
      <circle cx='12.5' cy='15.5' r='1.2' fill='currentColor' stroke='none' />
      <path d='M15.5 7H21v5.5' />
    </svg>
  )
}
