import { useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent } from 'react'
import { toast } from 'react-hot-toast'
import { documentsApi } from '@/api/documents.api'
import { getErrorMessage } from '@/api/client'
import { formatDateTime, formatFileSize } from '@/utils/formatters'
import { usePermissions } from '@/hooks/usePermissions'
import type {
  AnnotationAnchorType,
  Document,
  DocumentWorkspaceResponse,
} from '@/types/document.types'

interface Props {
  doc: Document | null
  onClose: () => void
}

type WorkspaceMode = 'view' | 'point' | 'text'

interface DraftAnnotation {
  localId: string
  id?: number
  variant_id?: number
  page_number: number | null
  anchor_type: AnnotationAnchorType
  anchor_data: Record<string, unknown>
  note_text: string
  color: string
  created_at?: string
  updated_at?: string
  xPct: number
  yPct: number
}

const NOTE_COLORS = ['#f59e0b', '#ef4444', '#3b82f6', '#10b981', '#8b5cf6']

export default function DocumentViewer({ doc, onClose }: Props) {
  const { canDownload } = usePermissions()
  const viewerRef = useRef<HTMLDivElement>(null)
  const previewRef = useRef<HTMLDivElement>(null)
  const [workspace, setWorkspace] = useState<DocumentWorkspaceResponse | null>(null)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [noteMode, setNoteMode] = useState<WorkspaceMode>('view')
  const [drafts, setDrafts] = useState<DraftAnnotation[]>([])
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null)

  const currentDocument = workspace?.document ?? doc
  const currentVariant = workspace?.variant ?? null
  const currentViewUrl = useMemo(() => {
    if (!currentDocument) return null
    if (currentVariant) return documentsApi.getVariantViewUrl(currentVariant.id)
    return documentsApi.getViewUrl(currentDocument.id)
  }, [currentDocument, currentVariant])

  useEffect(() => {
    if (!doc) {
      setWorkspace(null)
      setDrafts([])
      setBlobUrl(null)
      setActiveDraftId(null)
      return
    }

    let alive = true
    setLoading(true)
    setWorkspace(null)
    setDrafts([])
    setBlobUrl(null)
    setActiveDraftId(null)
    setNoteMode('view')

    documentsApi.getWorkspace(doc.id)
      .then((data) => {
        if (!alive) return
        setWorkspace(data)
        setDrafts(
          data.annotations.map((annotation) => ({
            ...annotation,
            localId: `saved-${annotation.id}`,
            xPct: Number(annotation.anchor_data?.x_pct ?? annotation.anchor_data?.x ?? 0),
            yPct: Number(annotation.anchor_data?.y_pct ?? annotation.anchor_data?.y ?? 0),
          }))
        )
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
  }, [doc?.id, onClose])

  useEffect(() => {
    if (!currentViewUrl) return
    if (workspace?.document.file_type !== 'pdf') return

    let alive = true
    const token = localStorage.getItem('access_token')

    fetch(currentViewUrl, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load preview')
        return response.blob()
      })
      .then((blob) => {
        if (!alive) return
        const url = URL.createObjectURL(blob)
        setBlobUrl(url)
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
  }, [currentViewUrl, workspace?.document.file_type])

  const addDraft = (draft: Omit<DraftAnnotation, 'localId'>) => {
    const localId = crypto.randomUUID()
    setDrafts((previous) => [
      ...previous,
      {
        ...draft,
        localId,
      },
    ])
    setActiveDraftId(localId)
  }

  const handleViewerClick = (event: MouseEvent<HTMLDivElement>) => {
    if (!workspace || noteMode !== 'point') return
    if (!viewerRef.current) return

    const rect = viewerRef.current.getBoundingClientRect()
    const xPct = ((event.clientX - rect.left) / rect.width) * 100
    const yPct = ((event.clientY - rect.top) / rect.height) * 100
    if (xPct < 0 || yPct < 0 || xPct > 100 || yPct > 100) return

    addDraft({
      page_number: workspace.document.file_type === 'pdf' ? 1 : null,
      anchor_type: 'point',
      anchor_data: {
        x_pct: xPct,
        y_pct: yPct,
      },
      note_text: '',
      color: NOTE_COLORS[drafts.length % NOTE_COLORS.length],
      xPct,
      yPct,
    })
  }

  const findParagraphIndex = (node: Node | null): number | null => {
    let current: Node | null = node
    while (current) {
      if (current instanceof HTMLElement) {
        const paragraph = current.closest('[data-paragraph-index]')
        if (paragraph) {
          const raw = paragraph.getAttribute('data-paragraph-index')
          const parsed = raw ? Number(raw) : NaN
          return Number.isFinite(parsed) ? parsed : null
        }
      }
      current = current.parentNode
    }
    return null
  }

  const handleDocxMouseUp = () => {
    if (!workspace || workspace.document.file_type !== 'docx' || noteMode !== 'text') return
    if (!previewRef.current) return

    const selection = window.getSelection()
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) return

    const range = selection.getRangeAt(0)
    if (!previewRef.current.contains(range.commonAncestorContainer)) return

    const selectedText = selection.toString().trim()
    if (!selectedText) return

    const rect = range.getBoundingClientRect()
    const previewRect = previewRef.current.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2
    const xPct = ((centerX - previewRect.left) / previewRect.width) * 100
    const yPct = ((centerY - previewRect.top) / previewRect.height) * 100

    addDraft({
      page_number: null,
      anchor_type: 'text_range',
      anchor_data: {
        paragraph_index: findParagraphIndex(range.startContainer),
        selected_text: selectedText,
        start_offset: range.startOffset,
        end_offset: range.endOffset,
        x_pct: xPct,
        y_pct: yPct,
      },
      note_text: '',
      color: NOTE_COLORS[drafts.length % NOTE_COLORS.length],
      xPct,
      yPct,
    })

    selection.removeAllRanges()
  }

  const updateDraft = (localId: string, patch: Partial<DraftAnnotation>) => {
    setDrafts((previous) => previous.map((draft) => (
      draft.localId === localId ? { ...draft, ...patch } : draft
    )))
  }

  const deleteDraft = (localId: string) => {
    setDrafts((previous) => previous.filter((draft) => draft.localId !== localId))
    if (activeDraftId === localId) setActiveDraftId(null)
  }

  const handleSave = async () => {
    if (!workspace || !currentDocument) return

    const payload = drafts.map((draft) => ({
      page_number: draft.page_number,
      anchor_type: draft.anchor_type,
      anchor_data: draft.anchor_data,
      note_text: draft.note_text.trim(),
      color: draft.color,
    }))

    if (payload.length === 0) {
      toast.error('Add at least one note before saving')
      return
    }
    if (payload.some((note) => !note.note_text)) {
      toast.error('Each note needs text before saving')
      return
    }

    setSaving(true)
    try {
      const response = await documentsApi.saveVariant(currentDocument.id, { annotations: payload })
      setWorkspace(response)
      setDrafts(
        response.annotations.map((annotation) => ({
          ...annotation,
          localId: `saved-${annotation.id}`,
          xPct: Number(annotation.anchor_data?.x_pct ?? 0),
          yPct: Number(annotation.anchor_data?.y_pct ?? 0),
        }))
      )
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

  const visibleNotes = drafts
    .map((draft, index) => ({ draft, index }))
    .sort((a, b) => a.index - b.index)

  if (!doc) return null

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
              onClick={() => setNoteMode((previous) => previous === 'point' ? 'view' : 'point')}
              style={noteMode === 'point' ? styles.activeToggle : styles.toggle}
            >
              Point
            </button>
            {workspace?.document.file_type === 'docx' && (
              <button
                onClick={() => setNoteMode((previous) => previous === 'text' ? 'view' : 'text')}
                style={noteMode === 'text' ? styles.activeToggle : styles.toggle}
              >
                Text
              </button>
            )}
          </div>
          <button
            onClick={handleSave}
            disabled={saving || drafts.length === 0 || drafts.some((draft) => !draft.note_text.trim())}
            style={styles.primaryButton}
          >
            {saving ? 'Saving...' : `Save private copy (${drafts.length})`}
          </button>
        </div>

        <div style={styles.body}>
          <div style={styles.viewerColumn}>
            {loading ? (
              <div style={styles.centerState}>
                <div style={styles.spinner} />
                <p style={styles.mutedText}>Loading workspace...</p>
              </div>
            ) : workspace?.document.file_type === 'docx' ? (
              workspace.preview_html ? (
                <div
                  ref={viewerRef}
                  style={styles.previewShell}
                  onClick={handleViewerClick}
                  onMouseUp={handleDocxMouseUp}
                >
                  <div
                    ref={previewRef}
                    style={styles.docxPreview}
                    dangerouslySetInnerHTML={{ __html: workspace.preview_html }}
                  />
                  <AnnotationLayer notes={drafts} activeDraftId={activeDraftId} onSelect={setActiveDraftId} />
                </div>
              ) : (
                <div style={styles.centerState}>
                  <p style={styles.mutedText}>{workspace.preview_error ?? 'Preview unavailable for this Word file.'}</p>
                </div>
              )
            ) : blobUrl ? (
              <div ref={viewerRef} style={styles.previewShell} onClick={handleViewerClick}>
                <iframe
                  src={blobUrl}
                  title={workspace?.document.title ?? doc.title}
                  style={styles.pdfFrame}
                />
                {noteMode === 'point' && (
                  <div
                    style={styles.clickCatcher}
                    onClick={(event) => {
                      event.stopPropagation()
                      handleViewerClick(event)
                    }}
                  />
                )}
                <AnnotationLayer notes={drafts} activeDraftId={activeDraftId} onSelect={setActiveDraftId} />
              </div>
            ) : (
              <div style={styles.centerState}>
                <p style={styles.mutedText}>Unable to load preview</p>
              </div>
            )}
          </div>

          <div style={styles.sidePanel}>
            <div style={styles.sidePanelHeader}>
              <div>
                <p style={styles.sidePanelTitle}>Notes</p>
                <p style={styles.sidePanelSubtitle}>{drafts.length} item{drafts.length === 1 ? '' : 's'}</p>
              </div>
            </div>
            <div style={styles.noteList}>
              {visibleNotes.length === 0 ? (
                <div style={styles.emptyNotes}>
                  <p style={styles.mutedText}>No annotations yet</p>
                </div>
              ) : visibleNotes.map(({ draft }, index) => (
                <div
                  key={draft.localId}
                  style={activeDraftId === draft.localId ? styles.noteCardActive : styles.noteCard}
                  onClick={() => setActiveDraftId(draft.localId)}
                >
                  <div style={styles.noteCardTop}>
                    <span style={{ ...styles.notePill, backgroundColor: draft.color }}>{draft.anchor_type === 'text_range' ? 'Text' : 'Point'}</span>
                    <button onClick={(event) => { event.stopPropagation(); deleteDraft(draft.localId) }} style={styles.noteDelete}>
                      ×
                    </button>
                  </div>
                  <textarea
                    value={draft.note_text}
                    onChange={(event) => updateDraft(draft.localId, { note_text: event.target.value })}
                    placeholder="Write a note"
                    rows={4}
                    style={styles.noteTextarea}
                  />
                  <div style={styles.noteMetaRow}>
                    <span style={styles.noteMeta}>
                      {draft.anchor_type === 'text_range'
                        ? `Text range ${typeof draft.anchor_data?.paragraph_index === 'number' ? `#${draft.anchor_data.paragraph_index}` : ''}`
                        : 'Point note'}
                    </span>
                    <input
                      type="color"
                      value={draft.color}
                      onChange={(event) => updateDraft(draft.localId, { color: event.target.value })}
                      style={styles.colorInput}
                    />
                  </div>
                  <div style={styles.swatchRow}>
                    {NOTE_COLORS.map((color) => (
                      <button
                        key={color}
                        onClick={(event) => { event.stopPropagation(); updateDraft(draft.localId, { color }) }}
                        style={{ ...styles.swatch, backgroundColor: color, outline: draft.color === color ? '2px solid #0f172a' : 'none' }}
                        aria-label="Set note color"
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function AnnotationLayer({
  notes,
  activeDraftId,
  onSelect,
}: {
  notes: DraftAnnotation[]
  activeDraftId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <div style={styles.annotationLayer}>
      {notes.map((note) => (
        <button
          key={note.localId}
          onClick={(event) => {
            event.stopPropagation()
            onSelect(note.localId)
          }}
          style={{
            ...styles.annotationMarker,
            left: `${note.xPct}%`,
            top: `${note.yPct}%`,
            borderColor: activeDraftId === note.localId ? '#0f172a' : note.color,
            backgroundColor: note.color,
          }}
          aria-label="Annotation marker"
        >
          <span style={styles.annotationDot} />
        </button>
      ))}
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
  },
  body: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) 340px',
    minHeight: 0,
    flex: 1,
  },
  viewerColumn: {
    minWidth: 0,
    backgroundColor: '#f8fafc',
    overflow: 'auto',
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
  annotationLayer: {
    position: 'absolute',
    inset: '1rem',
    pointerEvents: 'none',
    zIndex: 2,
  },
  clickCatcher: {
    position: 'absolute',
    inset: '1rem',
    zIndex: 1,
    cursor: 'crosshair',
  },
  annotationMarker: {
    position: 'absolute',
    transform: 'translate(-50%, -50%)',
    width: '24px',
    height: '24px',
    borderRadius: '6px',
    border: '2px solid',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    pointerEvents: 'auto',
    boxShadow: '0 4px 12px rgba(15,23,42,0.18)',
    padding: 0,
  },
  annotationDot: {
    width: '8px',
    height: '8px',
    borderRadius: '999px',
    backgroundColor: '#fff',
  },
  sidePanel: {
    borderLeft: '1px solid #e2e8f0',
    backgroundColor: '#fff',
    display: 'flex',
    flexDirection: 'column',
    minHeight: 0,
  },
  sidePanelHeader: {
    padding: '0.9rem 1rem',
    borderBottom: '1px solid #e2e8f0',
    flexShrink: 0,
  },
  sidePanelTitle: {
    margin: 0,
    fontSize: '0.9rem',
    fontWeight: 700,
    color: '#0f172a',
  },
  sidePanelSubtitle: {
    margin: '0.15rem 0 0',
    fontSize: '0.75rem',
    color: '#64748b',
  },
  noteList: {
    padding: '0.85rem',
    overflow: 'auto',
    minHeight: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  emptyNotes: {
    padding: '1rem',
    textAlign: 'center',
    border: '1px dashed #cbd5e1',
    borderRadius: '10px',
  },
  noteCard: {
    border: '1px solid #e2e8f0',
    borderRadius: '10px',
    padding: '0.75rem',
    backgroundColor: '#fff',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.65rem',
    cursor: 'pointer',
  },
  noteCardActive: {
    border: '1px solid #0f172a',
    borderRadius: '10px',
    padding: '0.75rem',
    backgroundColor: '#f8fafc',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.65rem',
    cursor: 'pointer',
  },
  noteCardTop: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '0.5rem',
  },
  notePill: {
    display: 'inline-flex',
    alignItems: 'center',
    borderRadius: '999px',
    padding: '0.18rem 0.5rem',
    color: '#fff',
    fontSize: '0.68rem',
    fontWeight: 700,
  },
  noteDelete: {
    width: '24px',
    height: '24px',
    border: 'none',
    backgroundColor: 'transparent',
    color: '#64748b',
    fontSize: '1rem',
    cursor: 'pointer',
  },
  noteTextarea: {
    width: '100%',
    border: '1px solid #cbd5e1',
    borderRadius: '8px',
    minHeight: '88px',
    padding: '0.6rem',
    fontFamily: 'inherit',
    fontSize: '0.82rem',
    resize: 'vertical',
    outline: 'none',
  },
  noteMetaRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '0.5rem',
  },
  noteMeta: {
    fontSize: '0.72rem',
    color: '#64748b',
  },
  colorInput: {
    width: '32px',
    height: '28px',
    border: 'none',
    backgroundColor: 'transparent',
    padding: 0,
  },
  swatchRow: {
    display: 'flex',
    gap: '0.35rem',
    flexWrap: 'wrap',
  },
  swatch: {
    width: '18px',
    height: '18px',
    borderRadius: '999px',
    border: '1px solid rgba(15,23,42,0.15)',
    cursor: 'pointer',
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
