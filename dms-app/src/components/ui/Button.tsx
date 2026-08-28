import { forwardRef } from 'react'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline' | 'accent'
type Size    = 'sm' | 'md' | 'lg'

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?:  Variant
  size?:     Size
  loading?:  boolean
  icon?:     React.ReactNode
  iconRight?: React.ReactNode
  fullWidth?: boolean
}

const base: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  gap: '6px', border: 'none', borderRadius: '8px', fontFamily: 'inherit',
  fontWeight: 600, cursor: 'pointer', transition: 'all 150ms', whiteSpace: 'nowrap',
}

const variants: Record<Variant, React.CSSProperties> = {
  primary:   { backgroundColor: 'var(--primary)', color: '#fff' },
  secondary: { backgroundColor: 'var(--surface-2)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)' },
  danger:    { backgroundColor: 'var(--danger)', color: '#fff' },
  ghost:     { backgroundColor: 'transparent', color: 'var(--text-secondary)' },
  outline:   { backgroundColor: 'transparent', color: 'var(--primary)', border: '1.5px solid var(--primary)' },
  accent:    { backgroundColor: 'var(--accent)', color: '#fff' },
}

const sizes: Record<Size, React.CSSProperties> = {
  sm: { padding: '5px 10px', fontSize: '0.78rem' },
  md: { padding: '7px 14px', fontSize: '0.85rem' },
  lg: { padding: '10px 20px', fontSize: '0.95rem' },
}

const Spinner = () => (
  <span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'currentColor', borderRadius: '50%', animation: 'btn-spin 0.7s linear infinite', display: 'inline-block', flexShrink: 0 }} />
)

const Button = forwardRef<HTMLButtonElement, Props>(({
  variant = 'primary', size = 'md', loading, icon, iconRight, fullWidth, children, style, disabled, ...rest
}, ref) => (
  <>
    <button
      ref={ref}
      disabled={disabled || loading}
      aria-busy={loading}
      style={{
        ...base,
        ...variants[variant],
        ...sizes[size],
        width: fullWidth ? '100%' : undefined,
        opacity: (disabled || loading) ? 0.55 : 1,
        cursor: (disabled || loading) ? 'not-allowed' : 'pointer',
        ...style,
      }}
      {...rest}
    >
      {loading ? <Spinner /> : icon}
      {children}
      {!loading && iconRight}
    </button>
    <style>{`@keyframes btn-spin { to { transform: rotate(360deg); } }`}</style>
  </>
))

Button.displayName = 'Button'
export default Button
