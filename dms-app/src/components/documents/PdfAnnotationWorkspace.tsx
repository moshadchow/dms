import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent,
} from 'react'
import { toast } from 'react-hot-toast'
import { GlobalWorkerOptions, getDocument } from 'pdfjs-dist'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { documentsApi } from '@/api/documents.api'
import { getErrorMessage } from '@/api/client'
import { usePermissions } from '@/hooks/usePermissions'
import { createClientId } from '@/utils/ids'
import type {
  Document,
  DocumentAnnotation,
  DocumentVariant,
  DocumentWorkspaceResponse,
  PdfStrokePoint,
} from '@/types/document.types'

GlobalWorkerOptions.workerSrc = `${pdfWorkerSrc}?v=pdfjs4`

type ToolMode = 'pen' | 'eraser'

interface PageMetric {
  pageNumber: number
  width: number
  height: number
}

interface PdfStrokeDraft {
  localId: string
  pageNumber: number
  color: string
  thickness: number
  points: PdfStrokePoint[]
}

interface Props {
  document: Document
  variant: DocumentVariant | null
  annotations: DocumentAnnotation[]
  onClose: () => void
  onWorkspaceSaved: (workspace: DocumentWorkspaceResponse) => void
}

const DEFAULT_COLORS = ['#0f172a', '#ef4444', '#2563eb', '#16a34a', '#d97706']
const MIN_ZOOM = 0.75
const MAX_ZOOM = 2

export default function PdfAnnotationWorkspace({
  document,
  variant,
  annotations,
  onClose,
  onWorkspaceSaved,
}: Props) {
  const { canDownload } = usePermissions()
  const viewerRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<Array<HTMLDivElement | null>>([])
  const pdfCanvasRefs = useRef<Array<HTMLCanvasElement | null>>([])
  const overlayCanvasRefs = useRef<Array<HTMLCanvasElement | null>>([])
  const pdfDocRef = useRef<PDFDocumentProxy | null>(null)
  const strokesRef = useRef<PdfStrokeDraft[]>([])
  const activeStrokeRef = useRef<PdfStrokeDraft | null>(null)
  const eraserSnapshotRef = useRef<PdfStrokeDraft[] | null>(null)
  const eraserChangedRef = useRef(false)

  const [pageMetrics, setPageMetrics] = useState<PageMetric[]>([])
  const [pdfReady, setPdfReady] = useState(false)
  const [loadingPdf, setLoadingPdf] = useState(true)
  const [saving, setSaving] = useState(false)
  const [tool, setTool] = useState<ToolMode>('pen')
  const [zoom, setZoom] = useState(1)
  const [color, setColor] = useState(DEFAULT_COLORS[0])
  const [thickness, setThickness] = useState(4)
  const [currentPage, setCurrentPage] = useState(1)
  const [strokes, setStrokes] = useState<PdfStrokeDraft[]>([])
  const [undoStack, setUndoStack] = useState<PdfStrokeDraft[][]>([])
  const [redoStack, setRedoStack] = useState<PdfStrokeDraft[][]>([])
  const [activeStroke, setActiveStroke] = useState<PdfStrokeDraft | null>(null)

  useEffect(() => {
    // Local editor state is intentionally reset when a saved workspace reloads.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStrokes(
      annotations
        .filter((annotation) => annotation.annotation_type === 'stroke')
        .map((annotation) => ({
          localId: `saved-${annotation.id}`,
          pageNumber: annotation.page_number ?? 1,
          color: annotation.color,
          thickness: annotation.thickness ?? 4,
          points: Array.isArray(annotation.anchor_data?.points)
            ? annotation.anchor_data.points as PdfStrokePoint[]
            : [],
        }))
        .filter((annotation) => annotation.points.length >= 2)
    )
    setUndoStack([])
    setRedoStack([])
    setActiveStroke(null)
    activeStrokeRef.current = null
    eraserSnapshotRef.current = null
    eraserChangedRef.current = false
  }, [annotations])

  useEffect(() => {
    strokesRef.current = strokes
  }, [strokes])

  useEffect(() => {
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadingPdf(true)
    setPdfReady(false)
    setPageMetrics([])
    pdfDocRef.current = null

    const token = localStorage.getItem('access_token')
    const task = getDocument({
      url: documentsApi.getViewEndpoint(document.id),
      httpHeaders: token ? { Authorization: `Bearer ${token}` } : undefined,
      withCredentials: false,
    })

    task.promise
      .then(async (pdf) => {
        if (cancelled) return
        pdfDocRef.current = pdf
        if (!cancelled) {
          setPdfReady(true)
          setCurrentPage(1)
        }
      })
      .catch(() => {
        if (!cancelled) {
          toast.error('Failed to load PDF preview')
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingPdf(false)
      })

    return () => {
      cancelled = true
      task.destroy()
    }
  }, [document.id])

  useEffect(() => {
    if (!pdfDocRef.current || !pdfReady) return
    let cancelled = false

    const measurePages = async () => {
      const nextMetrics: PageMetric[] = []
      for (let pageNumber = 1; pageNumber <= pdfDocRef.current.numPages; pageNumber += 1) {
        const page = await pdfDocRef.current.getPage(pageNumber)
        const viewport = page.getViewport({ scale: zoom })
        nextMetrics.push({
          pageNumber,
          width: viewport.width,
          height: viewport.height,
        })
      }
      if (!cancelled) setPageMetrics(nextMetrics)
    }

    void measurePages()
    return () => {
      cancelled = true
    }
  }, [pdfReady, zoom])

  useEffect(() => {
    if (!pdfDocRef.current || pageMetrics.length === 0) return
    let cancelled = false

    const renderPages = async () => {
      for (const metric of pageMetrics) {
        const canvas = pdfCanvasRefs.current[metric.pageNumber - 1]
        if (!canvas) continue
        const page = await pdfDocRef.current.getPage(metric.pageNumber)
        const viewport = page.getViewport({ scale: zoom })
        canvas.width = viewport.width
        canvas.height = viewport.height
        const context = canvas.getContext('2d')
        if (!context || cancelled) continue
        await page.render({ canvasContext: context, viewport }).promise
      }
    }

    void renderPages()
    return () => {
      cancelled = true
    }
  }, [pageMetrics, zoom])

  useEffect(() => {
    for (const metric of pageMetrics) {
      const canvas = overlayCanvasRefs.current[metric.pageNumber - 1]
      if (!canvas) continue
      canvas.width = metric.width
      canvas.height = metric.height
      const context = canvas.getContext('2d')
      if (!context) continue
      context.clearRect(0, 0, canvas.width, canvas.height)
      drawStrokeSet(context, metric, strokes.filter((stroke) => stroke.pageNumber === metric.pageNumber))
      if (activeStroke && activeStroke.pageNumber === metric.pageNumber) {
        drawStrokeSet(context, metric, [activeStroke])
      }
    }
  }, [activeStroke, pageMetrics, strokes])

  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return

    const handleScroll = () => {
      const viewerRect = viewer.getBoundingClientRect()
      let nearestPage = currentPage
      let nearestDistance = Number.POSITIVE_INFINITY
      pageRefs.current.forEach((pageRef, index) => {
        if (!pageRef) return
        const rect = pageRef.getBoundingClientRect()
        const distance = Math.abs(rect.top - viewerRect.top - 24)
        if (distance < nearestDistance) {
          nearestDistance = distance
          nearestPage = index + 1
        }
      })
      setCurrentPage(nearestPage)
    }

    viewer.addEventListener('scroll', handleScroll, { passive: true })
    return () => viewer.removeEventListener('scroll', handleScroll)
  }, [currentPage, pageMetrics.length])

  const cloneStrokes = (value: PdfStrokeDraft[]) => (
    value.map((stroke) => ({
      ...stroke,
      points: stroke.points.map((point) => ({ ...point })),
    }))
  )

  const commitStrokes = (next: PdfStrokeDraft[]) => {
    setUndoStack((previous) => [...previous, cloneStrokes(strokes)])
    setRedoStack([])
    setStrokes(next)
  }

  const getPointerPoint = (event: PointerEvent<HTMLCanvasElement>): PdfStrokePoint | null => {
    const canvas = event.currentTarget
    const rect = canvas.getBoundingClientRect()
    const x = (event.clientX - rect.left) / rect.width
    const y = (event.clientY - rect.top) / rect.height
    if (x < 0 || y < 0 || x > 1 || y > 1) return null
    return { x, y }
  }

  const eraseAtPoint = (pageNumber: number, point: PdfStrokePoint) => {
    const page = pageMetrics.find((item) => item.pageNumber === pageNumber)
    if (!page) return
    const radius = Math.max(thickness * 1.8 / page.width, 0.01)
    const filtered = strokesRef.current.filter((stroke) => {
      if (stroke.pageNumber !== pageNumber) return true
      return !stroke.points.some((candidate) => {
        const dx = candidate.x - point.x
        const dy = candidate.y - point.y
        return Math.sqrt(dx * dx + dy * dy) <= radius
      })
    })
    if (filtered.length !== strokesRef.current.length) {
      eraserChangedRef.current = true
      strokesRef.current = filtered
      setStrokes(filtered)
    }
  }

  const handlePointerDown = (pageNumber: number) => (event: PointerEvent<HTMLCanvasElement>) => {
    const point = getPointerPoint(event)
    if (!point) return

    event.currentTarget.setPointerCapture(event.pointerId)

    if (tool === 'eraser') {
      eraserSnapshotRef.current = cloneStrokes(strokesRef.current)
      eraserChangedRef.current = false
      eraseAtPoint(pageNumber, point)
      return
    }

    const stroke: PdfStrokeDraft = {
      localId: createClientId(),
      pageNumber,
      color,
      thickness,
      points: [point],
    }
    activeStrokeRef.current = stroke
    setActiveStroke(stroke)
  }

  const handlePointerMove = (pageNumber: number) => (event: PointerEvent<HTMLCanvasElement>) => {
    const point = getPointerPoint(event)
    if (!point) return

    if (tool === 'eraser' && eraserSnapshotRef.current) {
      eraseAtPoint(pageNumber, point)
      return
    }

    const stroke = activeStrokeRef.current
    if (!stroke || stroke.pageNumber !== pageNumber) return
    const nextStroke = {
      ...stroke,
      points: [...stroke.points, point],
    }
    activeStrokeRef.current = nextStroke
    setActiveStroke(nextStroke)
  }

  const handlePointerUp = (pageNumber: number) => (event: PointerEvent<HTMLCanvasElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }

    if (tool === 'eraser') {
      if (eraserChangedRef.current && eraserSnapshotRef.current) {
        setUndoStack((previous) => [...previous, eraserSnapshotRef.current as PdfStrokeDraft[]])
        setRedoStack([])
      } else if (eraserSnapshotRef.current) {
        setStrokes(eraserSnapshotRef.current)
      }
      eraserSnapshotRef.current = null
      eraserChangedRef.current = false
      return
    }

    const stroke = activeStrokeRef.current
    if (!stroke || stroke.pageNumber !== pageNumber) return
    activeStrokeRef.current = null
    setActiveStroke(null)
    if (stroke.points.length < 2) return
    commitStrokes([...strokes, stroke])
  }

  const handleUndo = () => {
    const previous = undoStack[undoStack.length - 1]
    if (!previous) return
    setUndoStack((stack) => stack.slice(0, -1))
    setRedoStack((stack) => [...stack, cloneStrokes(strokes)])
    setStrokes(cloneStrokes(previous))
  }

  const handleRedo = () => {
    const next = redoStack[redoStack.length - 1]
    if (!next) return
    setRedoStack((stack) => stack.slice(0, -1))
    setUndoStack((stack) => [...stack, cloneStrokes(strokes)])
    setStrokes(cloneStrokes(next))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const response = await documentsApi.saveVariant(document.id, {
        annotations: strokes.map((stroke) => {
          const metric = pageMetrics.find((item) => item.pageNumber === stroke.pageNumber)
          return {
            page_number: stroke.pageNumber,
            annotation_type: 'stroke',
            drawing_tool: 'pen',
            thickness: stroke.thickness,
            anchor_data: {
              points: stroke.points,
              thickness_ratio: metric ? stroke.thickness / metric.width : 0,
            },
            note_text: null,
            color: stroke.color,
          }
        }),
      })
      onWorkspaceSaved(response)
      toast.success('Annotated PDF saved')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const handleDownload = async () => {
    try {
      if (variant) {
        await documentsApi.downloadVariant(variant.id, variant.source_file_name)
      } else {
        await documentsApi.download(document.id, document.file_name)
      }
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  const scrollToPage = (pageNumber: number) => {
    pageRefs.current[pageNumber - 1]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setCurrentPage(pageNumber)
  }

  return (
    <div style={styles.backdropWrap}>
      <div style={styles.backdrop} onClick={onClose} />
      <div style={styles.modal}>
        <div style={styles.header}>
          <div style={{ minWidth: 0 }}>
            <div style={styles.titleRow}>
              <h2 style={styles.title}>{document.title}</h2>
              {variant && <span style={styles.privateBadge}>Private copy</span>}
            </div>
            <p style={styles.subtitle}>{document.file_name}</p>
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
            <button onClick={() => setTool('pen')} style={tool === 'pen' ? styles.activeToggle : styles.toggle}>Pen</button>
            <button onClick={() => setTool('eraser')} style={tool === 'eraser' ? styles.activeToggle : styles.toggle}>Eraser</button>
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
          <div style={styles.toolbarGroup}>
            <button onClick={() => setZoom((value) => Math.max(MIN_ZOOM, Number((value - 0.1).toFixed(2))))} style={styles.toggle}>-</button>
            <span style={styles.toolbarValue}>{Math.round(zoom * 100)}%</span>
            <button onClick={() => setZoom((value) => Math.min(MAX_ZOOM, Number((value + 0.1).toFixed(2))))} style={styles.toggle}>+</button>
          </div>
          <button onClick={handleSave} disabled={saving} style={styles.primaryButton}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>

        <div style={styles.body}>
          <div style={styles.pageRail}>
            <button
              onClick={() => scrollToPage(Math.max(1, currentPage - 1))}
              style={styles.pageButton}
              disabled={currentPage === 1}
            >
              Prev
            </button>
            <span style={styles.pageLabel}>Page {currentPage} / {pageMetrics.length || 1}</span>
            <button
              onClick={() => scrollToPage(Math.min(pageMetrics.length, currentPage + 1))}
              style={styles.pageButton}
              disabled={currentPage === pageMetrics.length || pageMetrics.length === 0}
            >
              Next
            </button>
          </div>

          <div ref={viewerRef} style={styles.viewerColumn}>
            {loadingPdf ? (
              <div style={styles.centerState}>
                <p style={styles.mutedText}>Loading PDF...</p>
              </div>
            ) : (
              pageMetrics.map((metric, index) => (
                <div
                  key={metric.pageNumber}
                  ref={(node) => {
                    pageRefs.current[index] = node
                  }}
                  style={styles.pageCard}
                >
                  <div style={styles.pageHeader}>Page {metric.pageNumber}</div>
                  <div style={{ ...styles.pageSurface, width: metric.width, height: metric.height }}>
                    <canvas
                      ref={(node) => {
                        pdfCanvasRefs.current[index] = node
                      }}
                      style={styles.pageCanvas}
                    />
                    <canvas
                      ref={(node) => {
                        overlayCanvasRefs.current[index] = node
                      }}
                      style={styles.overlayCanvas}
                      onPointerDown={handlePointerDown(metric.pageNumber)}
                      onPointerMove={handlePointerMove(metric.pageNumber)}
                      onPointerUp={handlePointerUp(metric.pageNumber)}
                      onPointerLeave={handlePointerUp(metric.pageNumber)}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function drawStrokeSet(
  context: CanvasRenderingContext2D,
  metric: PageMetric,
  strokes: PdfStrokeDraft[],
) {
  strokes.forEach((stroke) => {
    if (stroke.points.length < 2) return
    context.save()
    context.lineCap = 'round'
    context.lineJoin = 'round'
    context.strokeStyle = stroke.color
    context.lineWidth = stroke.thickness
    context.beginPath()
    context.moveTo(stroke.points[0].x * metric.width, stroke.points[0].y * metric.height)
    stroke.points.slice(1).forEach((point) => {
      context.lineTo(point.x * metric.width, point.y * metric.height)
    })
    context.stroke()
    context.restore()
  })
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
    width: 'min(1400px, calc(100vw - 2rem))',
    height: 'min(920px, calc(100vh - 2rem))',
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
  },
  title: {
    margin: 0,
    fontSize: '1rem',
    fontWeight: 700,
    color: '#0f172a',
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
  },
  headerActions: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
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
    alignItems: 'center',
    gap: '0.75rem',
    flexWrap: 'wrap',
    padding: '0.75rem 1rem',
    borderBottom: '1px solid #e2e8f0',
    backgroundColor: '#f8fafc',
    flexShrink: 0,
  },
  toolbarGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
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
  primaryButton: {
    border: 'none',
    backgroundColor: '#0f172a',
    color: '#fff',
    borderRadius: '8px',
    padding: '0.65rem 1rem',
    fontSize: '0.84rem',
    fontWeight: 700,
    cursor: 'pointer',
    marginLeft: 'auto',
  },
  label: {
    fontSize: '0.74rem',
    color: '#475569',
    fontWeight: 600,
  },
  toolbarValue: {
    minWidth: '52px',
    fontSize: '0.75rem',
    color: '#475569',
    textAlign: 'center',
  },
  colorSwatch: {
    width: '20px',
    height: '20px',
    borderRadius: '999px',
    border: '1px solid rgba(15,23,42,0.15)',
    cursor: 'pointer',
  },
  colorInput: {
    width: '32px',
    height: '28px',
    border: 'none',
    backgroundColor: 'transparent',
    padding: 0,
  },
  body: {
    display: 'grid',
    gridTemplateColumns: '180px minmax(0, 1fr)',
    minHeight: 0,
    flex: 1,
  },
  pageRail: {
    borderRight: '1px solid #e2e8f0',
    backgroundColor: '#fff',
    padding: '1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  pageButton: {
    border: '1px solid #cbd5e1',
    backgroundColor: '#fff',
    color: '#0f172a',
    borderRadius: '8px',
    padding: '0.65rem 0.75rem',
    fontSize: '0.82rem',
    fontWeight: 600,
    cursor: 'pointer',
  },
  pageLabel: {
    fontSize: '0.82rem',
    color: '#475569',
    fontWeight: 600,
  },
  viewerColumn: {
    minWidth: 0,
    backgroundColor: '#e2e8f0',
    overflow: 'auto',
    padding: '1rem',
  },
  pageCard: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    marginBottom: '1.5rem',
  },
  pageHeader: {
    alignSelf: 'flex-start',
    marginBottom: '0.5rem',
    fontSize: '0.78rem',
    fontWeight: 700,
    color: '#475569',
  },
  pageSurface: {
    position: 'relative',
    backgroundColor: '#fff',
    boxShadow: '0 12px 30px rgba(15,23,42,0.12)',
  },
  pageCanvas: {
    position: 'absolute',
    inset: 0,
  },
  overlayCanvas: {
    position: 'absolute',
    inset: 0,
    touchAction: 'none',
    cursor: 'crosshair',
  },
  centerState: {
    minHeight: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  mutedText: {
    margin: 0,
    color: '#64748b',
    fontSize: '0.85rem',
  },
}
