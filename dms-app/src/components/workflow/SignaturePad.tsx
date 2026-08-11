import { useRef, useState, useCallback, useEffect } from 'react'
import Button from '@/components/ui/Button'

interface SignaturePadProps {
  width?: number
  height?: number
  onCapture: (blob: Blob) => void
  onCancel?: () => void
}

const padStyle: React.CSSProperties = {
  border: '2px dashed #cbd5e1',
  borderRadius: '8px',
  backgroundColor: '#fff',
  cursor: 'crosshair',
  touchAction: 'none',
}

const labelStyle: React.CSSProperties = {
  position: 'absolute',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  color: '#94a3b8',
  fontSize: '0.85rem',
  pointerEvents: 'none',
  userSelect: 'none',
}

const actionsStyle: React.CSSProperties = {
  display: 'flex',
  gap: '8px',
  marginTop: '8px',
}

export default function SignaturePad({
  width = 400,
  height = 150,
  onCapture,
  onCancel,
}: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [hasDrawn, setHasDrawn] = useState(false)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, height)
    ctx.strokeStyle = '#1e293b'
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
  }, [width, height])

  const getPos = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current!
    const rect = canvas.getBoundingClientRect()
    if ('touches' in e) {
      return {
        x: e.touches[0].clientX - rect.left,
        y: e.touches[0].clientY - rect.top,
      }
    }
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }, [])

  const startDraw = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      const ctx = canvasRef.current?.getContext('2d')
      if (!ctx) return
      const pos = getPos(e)
      ctx.beginPath()
      ctx.moveTo(pos.x, pos.y)
      setIsDrawing(true)
      setHasDrawn(true)
    },
    [getPos]
  )

  const draw = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      if (!isDrawing) return
      const ctx = canvasRef.current?.getContext('2d')
      if (!ctx) return
      const pos = getPos(e)
      ctx.lineTo(pos.x, pos.y)
      ctx.stroke()
    },
    [isDrawing, getPos]
  )

  const endDraw = useCallback(() => {
    setIsDrawing(false)
  }, [])

  const clear = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, height)
    setHasDrawn(false)
  }, [width, height])

  const save = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.toBlob((blob) => {
      if (blob) onCapture(blob)
    }, 'image/png')
  }, [onCapture])

  return (
    <div>
      <div style={{ position: 'relative', display: 'inline-block' }}>
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          style={padStyle}
          onMouseDown={startDraw}
          onMouseMove={draw}
          onMouseUp={endDraw}
          onMouseLeave={endDraw}
          onTouchStart={startDraw}
          onTouchMove={draw}
          onTouchEnd={endDraw}
        />
        {!hasDrawn && <div style={labelStyle}>Sign here</div>}
      </div>
      <div style={actionsStyle}>
        <Button variant="secondary" size="sm" onClick={clear}>
          Clear
        </Button>
        <Button variant="primary" size="sm" onClick={save} disabled={!hasDrawn}>
          Accept Signature
        </Button>
        {onCancel && (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </div>
  )
}
