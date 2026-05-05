import clsx from 'clsx'

interface Props {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizes = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-10 h-10' }

export default function Spinner({ size = 'md', className }: Props) {
  return (
    <div
      role="status"
      className={clsx(
        'animate-spin rounded-full border-2 border-slate-200 border-t-primary-600',
        sizes[size],
        className
      )}
    />
  )
}
