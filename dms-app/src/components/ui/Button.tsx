import { forwardRef } from 'react'
import clsx from 'clsx'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline'
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
  primary:   { backgroundColor: '#1e293b', color: '#fff' },
  secondary: { backgroundColor: '#f8fafc', color: '#374151', border: '1px solid #e2e8f0' },
  danger:    { backgroundColor: '#dc2626', color: '#fff' },
  ghost:     { backgroundColor: 'transparent', color: '#475569' },
  outline:   { backgroundColor: 'transparent', color: '#4f46e5', border: '1.5px solid #4f46e5' },
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
