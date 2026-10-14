import { useEffect, useCallback, useRef } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import { getExtensions } from './editorExtensions'
import EditorToolbar from './EditorToolbar'
import TableMenu from './TableMenu'

interface MemoRichTextEditorProps {
  value: string
  onChange: (html: string) => void
  placeholder?: string
  editable?: boolean
  maxLength?: number
}

const editorStyles = `
  .tiptap {
    outline: none;
    min-height: 300px;
    padding: 1rem;
    font-size: 0.95rem;
    line-height: 1.7;
    color: var(--text, #1e293b);
  }
  .tiptap p.is-editor-empty:first-child::before {
    color: var(--text-muted, #94a3b8);
    content: attr(data-placeholder);
    float: left;
    height: 0;
    pointer-events: none;
  }
  .tiptap h1 { font-size: 1.75rem; font-weight: 700; margin: 1rem 0 0.5rem; }
  .tiptap h2 { font-size: 1.4rem; font-weight: 600; margin: 0.875rem 0 0.5rem; }
  .tiptap h3 { font-size: 1.15rem; font-weight: 600; margin: 0.75rem 0 0.375rem; }
  .tiptap h4 { font-size: 1rem; font-weight: 600; margin: 0.625rem 0 0.25rem; }
  .tiptap h5 { font-size: 0.9rem; font-weight: 600; margin: 0.5rem 0 0.25rem; }
  .tiptap h6 { font-size: 0.8rem; font-weight: 600; margin: 0.5rem 0 0.25rem; color: #64748b; }
  .tiptap ul { padding-left: 1.5rem; list-style: disc; margin: 0.5rem 0; }
  .tiptap ol { padding-left: 1.5rem; list-style: decimal; margin: 0.5rem 0; }
  .tiptap li { margin: 0.125rem 0; }
  .tiptap blockquote {
    border-left: 3px solid var(--primary, #4f46e5);
    padding-left: 1rem;
    margin: 0.75rem 0;
    color: var(--text-muted, #64748b);
    font-style: italic;
  }
  .tiptap pre.memo-code-block {
    background: var(--surface-2, #f1f5f9);
    border: 1px solid var(--border, #e2e8f0);
    border-radius: 6px;
    padding: 0.75rem 1rem;
    font-family: 'Courier New', monospace;
    font-size: 0.85rem;
    overflow-x: auto;
    margin: 0.75rem 0;
  }
  .tiptap code {
    background: var(--surface-2, #f1f5f9);
    border-radius: 3px;
    padding: 0.15em 0.35em;
    font-family: 'Courier New', monospace;
    font-size: 0.9em;
    color: var(--primary, #4f46e5);
  }
  .tiptap pre code {
    background: none;
    padding: 0;
    color: inherit;
  }
  .tiptap a.memo-link {
    color: var(--primary, #4f46e5);
    text-decoration: underline;
    cursor: pointer;
  }
  .tiptap a.memo-link:hover {
    opacity: 0.8;
  }
  .tiptap img.memo-image {
    max-width: 100%;
    height: auto;
    border-radius: 6px;
    margin: 0.5rem 0;
  }
  .tiptap hr {
    border: none;
    border-top: 2px solid var(--border, #e2e8f0);
    margin: 1rem 0;
  }
  .tiptap table.memo-table {
    border-collapse: collapse;
    width: 100%;
    margin: 0.75rem 0;
  }
  .tiptap table.memo-table th,
  .tiptap table.memo-table td {
    border: 1px solid var(--border, #e2e8f0);
    padding: 0.5rem 0.75rem;
    text-align: left;
    min-width: 80px;
  }
  .tiptap table.memo-table th {
    background: var(--surface-2, #f1f5f9);
    font-weight: 600;
  }
  .tiptap table.memo-table .selectedCell {
    background: var(--primary-light, #e0e7ff);
  }
  .tiptap table.memo-table .column-resize-handle {
    position: absolute;
    right: -2px;
    top: 0;
    bottom: 0;
    width: 4px;
    background: var(--primary, #4f46e5);
    cursor: col-resize;
  }
  .tiptap .resize-cursor {
    cursor: col-resize;
  }
  .tiptap mark {
    background-color: #fef08a;
    border-radius: 2px;
    padding: 0.1em 0;
  }
`

export default function MemoRichTextEditor({
  value,
  onChange,
  placeholder = 'Write your memo here...',
  editable = true,
  maxLength = 50000,
}: MemoRichTextEditorProps) {
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const editor = useEditor({
    extensions: getExtensions(),
    content: value,
    editable,
    editorProps: {
      attributes: {
        class: 'tiptap',
        'data-placeholder': placeholder,
      },
    },
    onUpdate: ({ editor: e }) => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current)
      }
      debounceTimer.current = setTimeout(() => {
        const html = e.getHTML()
        onChange(html)
      }, 300)
    },
  })

  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current)
      }
    }
  }, [])

  useEffect(() => {
    if (!editor) return
    const currentContent = editor.getHTML()
    if (value !== currentContent) {
      editor.commands.setContent(value, false)
    }
  }, [value, editor])

  useEffect(() => {
    if (editor && !editable) {
      editor.setEditable(false)
    }
  }, [editable, editor])

  const handleImageUpload = useCallback(
    (_file: File) => {
      return new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => {
          const dataUrl = reader.result as string
          if (editor) {
            editor.chain().focus().setImage({ src: dataUrl }).run()
          }
          resolve(dataUrl)
        }
        reader.onerror = reject
        reader.readAsDataURL(_file)
      })
    },
    [editor]
  )

  if (!editor) return null

  const charCount = editor.storage.characterCount?.characters() ?? 0

  return (
    <>
      <style>{editorStyles}</style>
      <div
        style={{
          border: '1px solid var(--border, #cbd5e1)',
          borderRadius: 8,
          overflow: 'hidden',
          background: 'var(--surface, #fff)',
        }}
      >
        {editable && (
          <EditorToolbar
            editor={editor}
            onImageUpload={handleImageUpload}
          />
        )}
        {editable && (
          <TableMenu editor={editor} />
        )}
        <EditorContent editor={editor} />
        {editable && maxLength && (
          <div
            style={{
              padding: '0.375rem 0.75rem',
              borderTop: '1px solid var(--border, #e2e8f0)',
              fontSize: '0.7rem',
              color: charCount > maxLength * 0.9
                ? '#ef4444'
                : 'var(--text-muted, #94a3b8)',
              textAlign: 'right',
            }}
          >
            {charCount.toLocaleString()} / {maxLength.toLocaleString()} characters
          </div>
        )}
      </div>
    </>
  )
}
