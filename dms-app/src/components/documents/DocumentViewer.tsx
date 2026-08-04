import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { toast } from 'react-hot-toast'
import { documentsApi } from '@/api/documents.api'
import { getErrorMessage } from '@/api/client'
import { formatDateTime, formatFileSize } from '@/utils/formatters'
import { createClientId } from '@/utils/ids'
import { usePermissions } from '@/hooks/usePermissions'
import PdfAnnotationWorkspace from '@/components/documents/PdfAnnotationWorkspace'
import type {
  Document,
  DocumentWorkspaceResponse,
  PdfStrokePoint,
} from '@/types/document.types'

interface Props {
  doc: Document | null
  onClose: () => void
}

type ToolMode = 'pen' | 'eraser'

interface StrokeDraft {
  localId: string
  color: string
  thickness: number
  points: PdfStrokePoint[]
}

const DEFAULT_COLORS = ['#0f172a', '#ef4444', '#2563eb', '#16a34a', '#d97706']

function cloneStrokes(value: StrokeDraft[]): StrokeDraft[] {
  return value.map((stroke) => ({
    ...stroke,
    points: stroke.points.map((point) => ({ ...point })),
  }))
}

function getPointerPoint(
  event: React.PointerEvent<HTMLCanvasElement>,
): PdfStrokePoint | null {
  const canvas = event.currentTarget
  const rect = canvas.getBoundingClientRect()
  if (rect.width === 0 || rect.height === 0) return null
  const x = (event.clientX - rect.left) / rect.width
  const y = (event.clientY - rect.top) / rect.height
  if (x < 0 || y < 0 || x > 1 || y > 1) return null
  return { x, y }
}

function drawStrokeSet(
  ctx: CanvasRenderingContext2D,
  strokes: StrokeDraft[],
) {
  const w = ctx.canvas.width
  const h = ctx.canvas.height
  ctx.clearRect(0, 0, w, h)
  for (const stroke of strokes) {
    if (stroke.points.length < 2) continue
    ctx.save()
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.strokeStyle = stroke.color
    ctx.lineWidth = stroke.thickness
    ctx.beginPath()
    ctx.moveTo(stroke.points[0].x * w, stroke.points[0].y * h)
    for (let i = 1; i < stroke.points.length; i++) {
      ctx.lineTo(stroke.points[i].x * w, stroke.points[i].y * h)
    }
    ctx.stroke()
    ctx.restore()
  }
}

function drawActiveStroke(
  ctx: CanvasRenderingContext2D,
  stroke: StrokeDraft,
) {
  if (stroke.points.length < 2) return
  const w = ctx.canvas.width
  const h = ctx.canvas.height
  ctx.save()
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = stroke.color
  ctx.lineWidth = stroke.thickness
  ctx.beginPath()
  ctx.moveTo(stroke.points[0].x * w, stroke.points[0].y * h)
  for (let i = 1; i < stroke.points.length; i++) {
    ctx.lineTo(stroke.points[i].x * w, stroke.points[i].y * h)
  }
  ctx.stroke()
  ctx.restore()
}

export default function DocumentViewer({ doc, onClose }: Props) {
  const { canDownload } = usePermissions()
  const viewerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const strokesRef = useRef<StrokeDraft[]>([])
  const activeStrokeRef = useRef<StrokeDraft | null>(null)
  const eraserSnapshotRef = useRef<StrokeDraft[] | null>(null)
  const eraserChangedRef = useRef(false)

  const [workspace, setWorkspace] = useState<DocumentWorkspaceResponse | null>(null)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [tool, setTool] = useState<ToolMode>('pen')
  const [color, setColor] = useState(DEFAULT_COLORS[1])
  const [thickness, setThickness] = useState(4)
  const [strokes, setStrokes] = useState<StrokeDraft[]>([])
  const [undoStack, setUndoStack] = useState<StrokeDraft[][]>([])
  const [redoStack, setRedoStack] = useState<StrokeDraft[][]>([])
  const [activeStroke, setActiveStroke] = useState<StrokeDraft | null>(null)

  const currentDocument = workspace?.document ?? doc
  const currentVariant = workspace?.variant ?? null

  useEffect(() => {
    strokesRef.current = strokes
  }, [strokes])

  useEffect(() => {
    if (!doc) {
      setWorkspace(null)
      setBlobUrl(null)
      setTool('pen')
      setStrokes([])
      setUndoStack([])
      setRedoStack([])
      setActiveStroke(null)
      strokesRef.current = []
      activeStrokeRef.current = null
      eraserSnapshotRef.current = null
      eraserChangedRef.current = false
      return
    }

    let alive = true
    setLoading(true)
    setWorkspace(null)
    setBlobUrl(null)
    setTool('pen')
    setStrokes([])
    setUndoStack([])
    setRedoStack([])
    setActiveStroke(null)
    strokesRef.current = []
    activeStrokeRef.current = null
    eraserSnapshotRef.current = null
    eraserChangedRef.current = false

    documentsApi.getWorkspace(doc.id)
      .then((data) => {
        if (!alive) return
        setWorkspace(data)
        const loaded: StrokeDraft[] = []
        for (const annotation of data.annotations) {
          if (annotation.annotation_type === 'stroke' && annotation.drawing_tool === 'pen') {
            const points = annotation.anchor_data?.points
            if (Array.isArray(points) && points.length >= 2) {
              loaded.push({
                localId: `saved-${annotation.id}`,
                color: annotation.color,
                thickness: annotation.thickness ?? 4,
                points: points as PdfStrokePoint[],
              })
            }
          }
        }
        setStrokes(loaded)
        setUndoStack([])
        setRedoStack([])
      })
      .catch((err) => {
        if (!alive) return
        toast.error(getErrorMessage(err))
        onClose()
      })
      .finally(() => {
        if (alive) setLoading(false)
      })

    return () => {
      alive = false
    }
  }, [doc, onClose])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    drawStrokeSet(ctx, strokes)
    if (activeStroke) {
      drawActiveStroke(ctx, activeStroke)
    }
  }, [strokes, activeStroke])

  useEffect(() => {
    if (!currentDocument || currentDocument.file_type === 'pdf') return
    const token = localStorage.getItem('access_token')
    const url = currentVariant
      ? documentsApi.getVariantViewUrl(currentVariant.id)
      : documentsApi.getViewUrl(currentDocument.id)

    let alive = true
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load preview')
        return response.blob()
      })
      .then((blob) => {
        if (!alive) return
        setBlobUrl(URL.createObjectURL(blob))
      })
      .catch(() => {
        if (!alive) return
        toast.error('Failed to load preview')
      })

    return () => {
      alive = false
      setBlobUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous)
        return null
      })
    }
  }, [currentDocument, currentVariant])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const parent = canvas.parentElement
    if (!parent) return
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        if (width > 0 && height > 0) {
          canvas.width = width
          canvas.height = height
        }
      }
    })
    ro.observe(parent)
    return () => ro.disconnect()
  }, [])

  const commitStrokes = (next: StrokeDraft[]) => {
    setUndoStack((previous) => [...previous, cloneStrokes(strokesRef.current)])
    setRedoStack([])
    setStrokes(next)
  }

  const handleUndo = () => {
    const previous = undoStack[undoStack.length - 1]
    if (!previous) return
    setUndoStack((stack) => stack.slice(0, -1))
    setRedoStack((stack) => [...stack, cloneStrokes(strokesRef.current)])
    setStrokes(previous)
  }

  const handleRedo = () => {
    const next = redoStack[redoStack.length - 1]
    if (!next) return
    setRedoStack((stack) => stack.slice(0, -1))
    setUndoStack((stack) => [...stack, cloneStrokes(strokesRef.current)])
    setStrokes(next)
  }

  const eraseAtPoint = (point: PdfStrokePoint) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const radius = Math.max(thickness * 1.8 / canvas.width, 0.01)
    const filtered = strokesRef.current.filter((stroke) =>
      !stroke.points.some((candidate) => {
        const dx = candidate.x - point.x
        const dy = candidate.y - point.y
        return Math.sqrt(dx * dx + dy * dy) <= radius
      }),
    )
    if (filtered.length !== strokesRef.current.length) {
      eraserChangedRef.current = true
      setStrokes(filtered)
    }
  }

  const handlePointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const point = getPointerPoint(event)
    if (!point) return

    event.currentTarget.setPointerCapture(event.pointerId)

    if (tool === 'eraser') {
      eraserSnapshotRef.current = cloneStrokes(strokesRef.current)
      eraserChangedRef.current = false
      eraseAtPoint(point)
      return
    }

    const stroke: StrokeDraft = {
      localId: createClientId(),
      color,
      thickness,
      points: [point],
    }
    activeStrokeRef.current = stroke
    setActiveStroke(stroke)
  }

  const handlePointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const point = getPointerPoint(event)
    if (!point) return

    if (tool === 'eraser' && eraserSnapshotRef.current) {
      eraseAtPoint(point)
      return
    }

    if (tool !== 'pen') return
    const stroke = activeStrokeRef.current
    if (!stroke) return

    const nextStroke: StrokeDraft = {
      ...stroke,
      points: [...stroke.points, point],
    }
    activeStrokeRef.current = nextStroke
    setActiveStroke(nextStroke)
  }

  const handlePointerUp = () => {
    if (tool === 'eraser') {
      if (eraserChangedRef.current && eraserSnapshotRef.current) {
        setUndoStack((previous) => [...previous, eraserSnapshotRef.current as StrokeDraft[]])
        setRedoStack([])
      } else if (eraserSnapshotRef.current) {
        setStrokes(eraserSnapshotRef.current)
      }
      eraserSnapshotRef.current = null
      eraserChangedRef.current = false
      return
    }

    if (tool !== 'pen') return
    const stroke = activeStrokeRef.current
    if (!stroke) return
    activeStrokeRef.current = null
    setActiveStroke(null)
    if (stroke.points.length < 2) return
    commitStrokes([...strokesRef.current, stroke])
  }

  const handleSave = async () => {
    if (!workspace || !currentDocument) return

    const canvas = canvasRef.current
    const canvasWidth = canvas?.width ?? 1

    const strokePayload = strokes
      .filter((stroke) => stroke.points.length >= 2)
      .map((stroke) => ({
        page_number: null,
        annotation_type: 'stroke' as const,
        drawing_tool: 'pen' as const,
        thickness: stroke.thickness,
        anchor_data: {
          points: stroke.points,
          thickness_ratio: stroke.thickness / canvasWidth,
        },
        note_text: null,
        color: stroke.color,
      }))

    if (strokePayload.length === 0) {
      toast.error('Draw at least one stroke before saving')
      return
    }

    setSaving(true)
    try {
      const response = await documentsApi.saveVariant(currentDocument.id, { annotations: strokePayload })
      setWorkspace(response)
      const loaded: StrokeDraft[] = []
      for (const annotation of response.annotations) {
        if (annotation.annotation_type === 'stroke' && annotation.drawing_tool === 'pen') {
          const points = annotation.anchor_data?.points
          if (Array.isArray(points) && points.length >= 2) {
            loaded.push({
              localId: `saved-${annotation.id}`,
              color: annotation.color,
              thickness: annotation.thickness ?? 4,
              points: points as PdfStrokePoint[],
            })
          }
        }
      }
      setStrokes(loaded)
      setUndoStack([])
      setRedoStack([])
      toast.success('Private copy saved')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const handleDownload = async () => {
    if (!currentDocument) return
    try {
      if (currentVariant) {
        await documentsApi.downloadVariant(currentVariant.id, currentVariant.source_file_name)
      } else {
        await documentsApi.download(currentDocument.id, currentDocument.file_name)
      }
    } catch (err) {
      toast.error(getErrorMessage(err))
    }
  }

  if (!doc) return null
  if (!loading && workspace?.document.file_type === 'pdf') {
    return (
      <PdfAnnotationWorkspace
        document={workspace.document}
        variant={workspace.variant}
        annotations={workspace.annotations}
        onClose={onClose}
        onWorkspaceSaved={setWorkspace}
      />
    )
  }

  return (
    <div style={styles.backdropWrap}>
      <div style={styles.backdrop} onClick={onClose} />
      <div style={styles.modal}>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <div style={styles.header}>
          <div style={{ overflow: 'hidden', minWidth: 0 }}>
            <div style={styles.titleRow}>
              <h2 style={styles.title}>{workspace?.document.title ?? doc.title}</h2>
              {workspace?.has_private_variant && (
                <span style={styles.privateBadge}>Private copy</span>
              )}
            </div>
            <p style={styles.subtitle}>
              {workspace?.document.file_name ?? doc.file_name} · {formatFileSize(workspace?.document.file_size ?? doc.file_size)} · {formatDateTime(workspace?.document.created_at ?? doc.created_at)}
            </p>
          </div>
          <div style={styles.headerActions}>
            {canDownload && (
              <button onClick={handleDownload} style={styles.secondaryButton}>
                Download
              </button>
            )}
            <button onClick={onClose} style={styles.iconButton} aria-label="Close viewer">
              ×
            </button>
          </div>
        </div>

        <div style={styles.toolbar}>
          <div style={styles.toolbarGroup}>
            <button
              onClick={() => setTool('pen')}
              style={tool === 'pen' ? styles.activeToggle : styles.toggle}
            >
              Pen
            </button>
            <button
              onClick={() => setTool('eraser')}
              style={tool === 'eraser' ? styles.activeToggle : styles.toggle}
            >
              Eraser
            </button>
          </div>
          <div style={styles.toolbarGroup}>
            {DEFAULT_COLORS.map((swatch) => (
              <button
                key={swatch}
                onClick={() => setColor(swatch)}
                style={{
                  ...styles.colorSwatch,
                  backgroundColor: swatch,
                  outline: color === swatch ? '2px solid #0f172a' : 'none',
                }}
                aria-label="Set pen color"
              />
            ))}
            <input
              type="color"
              value={color}
              onChange={(event) => setColor(event.target.value)}
              style={styles.colorInput}
              aria-label="Custom pen color"
            />
          </div>
          <div style={styles.toolbarGroup}>
            <label style={styles.label}>Size</label>
            <input
              type="range"
              min={2}
              max={18}
              step={1}
              value={thickness}
              onChange={(event) => setThickness(Number(event.target.value))}
            />
            <span style={styles.toolbarValue}>{thickness}px</span>
          </div>
          <div style={styles.toolbarGroup}>
            <button onClick={handleUndo} disabled={undoStack.length === 0} style={styles.toggle}>Undo</button>
            <button onClick={handleRedo} disabled={redoStack.length === 0} style={styles.toggle}>Redo</button>
          </div>
          <button
            onClick={handleSave}
            disabled={saving || strokes.length === 0}
            style={styles.primaryButton}
          >
            {saving ? 'Saving...' : 'Save private copy'}
          </button>
        </div>

        <div style={styles.body}>
          {loading ? (
            <div style={styles.centerState}>
              <div style={styles.spinner} />
              <p style={styles.mutedText}>Loading workspace...</p>
            </div>
          ) : workspace?.preview_html ? (
              <div ref={viewerRef} style={styles.previewShell}>
                <div
                  style={styles.docxPreview}
                  dangerouslySetInnerHTML={{ __html: workspace.preview_html }}
                />
                <canvas
                  ref={canvasRef}
                  style={{
                    position: 'absolute',
                    inset: '1rem',
                    width: 'calc(100% - 2rem)',
                    height: 'calc(100% - 2rem)',
                    pointerEvents: tool === 'pen' || tool === 'eraser' ? 'auto' : 'none',
                    cursor: tool === 'pen' ? 'crosshair' : tool === 'eraser' ? 'cell' : 'default',
                    zIndex: 2,
                    touchAction: 'none',
                  }}
                  onPointerDown={handlePointerDown}
                  onPointerMove={handlePointerMove}
                  onPointerUp={handlePointerUp}
                />
              </div>
          ) : workspace?.preview_error ? (
            <div style={styles.centerState}>
              <p style={styles.mutedText}>{workspace.preview_error}</p>
            </div>
          ) : blobUrl ? (
            <div ref={viewerRef} style={styles.previewShell}>
              <iframe
                src={blobUrl}
                title={workspace?.document.title ?? doc.title}
                style={styles.pdfFrame}
              />
              <canvas
                ref={canvasRef}
                style={{
                  position: 'absolute',
                  inset: '1rem',
                  width: 'calc(100% - 2rem)',
                  height: 'calc(100% - 2rem)',
                  pointerEvents: tool === 'pen' || tool === 'eraser' ? 'auto' : 'none',
                  cursor: tool === 'pen' ? 'crosshair' : tool === 'eraser' ? 'cell' : 'default',
                  zIndex: 2,
                  touchAction: 'none',
                }}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
              />
            </div>
          ) : (
            <div style={styles.centerState}>
              <p style={styles.mutedText}>Unable to load preview</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const styles: Record<string, CSSProperties> = {
  backdropWrap: {
    position: 'fixed',
    inset: 0,
    zIndex: 60,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '1rem',
  },
  backdrop: {
    position: 'absolute',
    inset: 0,
    backgroundColor: 'rgba(15,23,42,0.78)',
  },
  modal: {
    position: 'relative',
    width: 'min(1280px, calc(100vw - 2rem))',
    height: 'min(900px, calc(100vh - 2rem))',
    backgroundColor: '#fff',
    borderRadius: '12px',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '0 24px 80px rgba(0,0,0,0.35)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: '1rem',
    alignItems: 'center',
    padding: '0.9rem 1.1rem',
    borderBottom: '1px solid #e2e8f0',
    flexShrink: 0,
  },
  titleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    minWidth: 0,
  },
  title: {
    margin: 0,
    fontSize: '1rem',
    fontWeight: 700,
    color: '#0f172a',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  subtitle: {
    margin: '0.15rem 0 0',
    fontSize: '0.75rem',
    color: '#64748b',
  },
  privateBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '0.2rem 0.5rem',
    borderRadius: '999px',
    backgroundColor: '#eef2ff',
    color: '#4338ca',
    fontSize: '0.68rem',
    fontWeight: 700,
    whiteSpace: 'nowrap',
  },
  headerActions: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    flexShrink: 0,
  },
  secondaryButton: {
    border: '1px solid #cbd5e1',
    backgroundColor: '#fff',
    color: '#0f172a',
    borderRadius: '8px',
    padding: '0.55rem 0.85rem',
    fontSize: '0.84rem',
    fontWeight: 600,
    cursor: 'pointer',
  },
  iconButton: {
    width: '34px',
    height: '34px',
    borderRadius: '8px',
    border: '1px solid #e2e8f0',
    backgroundColor: '#fff',
    color: '#0f172a',
    fontSize: '1.15rem',
    cursor: 'pointer',
    lineHeight: 1,
  },
  toolbar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '0.7rem 1.1rem',
    borderBottom: '1px solid #e2e8f0',
    backgroundColor: '#f8fafc',
    gap: '0.75rem',
    flexWrap: 'wrap',
  },
  toolbarGroup: {
    display: 'flex',
    gap: '0.4rem',
    alignItems: 'center',
  },
  toggle: {
    border: '1px solid #cbd5e1',
    backgroundColor: '#fff',
    color: '#334155',
    borderRadius: '999px',
    padding: '0.45rem 0.85rem',
    fontSize: '0.82rem',
    fontWeight: 600,
    cursor: 'pointer',
  },
  activeToggle: {
    border: '1px solid #0f172a',
    backgroundColor: '#0f172a',
    color: '#fff',
    borderRadius: '999px',
    padding: '0.45rem 0.85rem',
    fontSize: '0.82rem',
    fontWeight: 600,
    cursor: 'pointer',
  },
  colorSwatch: {
    width: '22px',
    height: '22px',
    borderRadius: '999px',
    border: '1px solid rgba(15,23,42,0.15)',
    cursor: 'pointer',
    padding: 0,
  },
  colorInput: {
    width: '28px',
    height: '28px',
    border: 'none',
    padding: 0,
    cursor: 'pointer',
  },
  label: {
    fontSize: '0.78rem',
    color: '#64748b',
    fontWeight: 600,
  },
  toolbarValue: {
    fontSize: '0.78rem',
    color: '#334155',
    fontWeight: 600,
    minWidth: '2.5rem',
    textAlign: 'center',
  },
  primaryButton: {
    border: 'none',
    backgroundColor: '#0f172a',
    color: '#fff',
    borderRadius: '8px',
    padding: '0.65rem 1rem',
    fontSize: '0.84rem',
    fontWeight: 700,
    cursor: 'pointer',
  },
  body: {
    flex: 1,
    minHeight: 0,
    overflow: 'auto',
    backgroundColor: '#f8fafc',
    position: 'relative',
  },
  previewShell: {
    position: 'relative',
    minHeight: '100%',
    padding: '1rem',
  },
  pdfFrame: {
    width: '100%',
    height: '100%',
    minHeight: 'calc(100vh - 220px)',
    border: 'none',
    borderRadius: '10px',
    backgroundColor: '#fff',
  },
  docxPreview: {
    position: 'relative',
    backgroundColor: '#fff',
    borderRadius: '10px',
    border: '1px solid #e2e8f0',
    padding: '1.5rem',
    minHeight: 'calc(100vh - 220px)',
    color: '#0f172a',
    lineHeight: 1.65,
  },
  centerState: {
    minHeight: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'column',
    gap: '0.75rem',
    padding: '1.5rem',
  },
  spinner: {
    width: '26px',
    height: '26px',
    borderRadius: '999px',
    border: '3px solid #e2e8f0',
    borderTopColor: '#0f172a',
    animation: 'spin 0.7s linear infinite',
  },
  mutedText: {
    margin: 0,
    color: '#64748b',
    fontSize: '0.85rem',
  },
}
