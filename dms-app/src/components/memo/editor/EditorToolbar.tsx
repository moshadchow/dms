import { useState, useRef, useCallback } from 'react'
import type { Editor } from '@tiptap/react'
import {
  Bold, Italic, Underline as UnderlineIcon, Strikethrough,
  Code, Heading1, Heading2, Heading3, Heading4,
  List, ListOrdered, ListChecks,
  Quote, Minus, CodeSquare,
  AlignLeft, AlignCenter, AlignRight, AlignJustify,
  Link as LinkIcon, Image as ImageIcon,
  Undo2, Redo2, Highlighter, Palette,
} from 'lucide-react'

interface ToolbarProps {
  editor: Editor
  onImageUpload?: (file: File) => Promise<string>
}

interface ToolbarButtonProps {
  onClick: () => void
  active?: boolean
  disabled?: boolean
  title?: string
  children: React.ReactNode
}

function ToolbarButton({ onClick, active = false, disabled = false, title, children }: ToolbarButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 30,
        height: 30,
        borderRadius: 4,
        border: 'none',
        background: active ? 'var(--primary, #4f46e5)' : 'transparent',
        color: active ? '#fff' : 'var(--text, #475569)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        transition: 'all 0.15s',
        flexShrink: 0,
      }}
      onMouseEnter={(e) => {
        if (!active && !disabled) {
          e.currentTarget.style.background = 'var(--surface-2, #f1f5f9)'
        }
      }}
      onMouseLeave={(e) => {
        if (!active && !disabled) {
          e.currentTarget.style.background = 'transparent'
        }
      }}
    >
      {children}
    </button>
  )
}

function ToolbarDivider() {
  return (
    <div
      style={{
        width: 1,
        height: 20,
        background: 'var(--border, #e2e8f0)',
        margin: '0 4px',
        flexShrink: 0,
      }}
    />
  )
}

function ColorPicker({
  value,
  onChange,
  onClose,
}: {
  value: string
  onChange: (color: string) => void
  onClose: () => void
}) {
  const colors = [
    '#000000', '#434343', '#666666', '#999999', '#cccccc', '#ffffff',
    '#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db', '#9b59b6',
    '#1abc9c', '#34495e', '#c0392b', '#d35400', '#f39c12', '#27ae60',
    '#2980b9', '#8e44ad', '#16a085', '#2c3e50',
  ]
  return (
    <div
      style={{
        position: 'absolute',
        top: '100%',
        left: 0,
        zIndex: 100,
        background: 'var(--surface, #fff)',
        border: '1px solid var(--border, #e2e8f0)',
        borderRadius: 8,
        padding: 8,
        boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
        display: 'grid',
        gridTemplateColumns: 'repeat(6, 1fr)',
        gap: 4,
        width: 180,
      }}
    >
      {colors.map((c) => (
        <button
          key={c}
          type="button"
          onClick={() => { onChange(c); onClose() }}
          style={{
            width: 24,
            height: 24,
            borderRadius: 4,
            border: value === c ? '2px solid var(--primary, #4f46e5)' : '1px solid var(--border, #e2e8f0)',
            background: c,
            cursor: 'pointer',
          }}
        />
      ))}
    </div>
  )
}

export default function EditorToolbar({ editor, onImageUpload }: ToolbarProps) {
  const [showLinkInput, setShowLinkInput] = useState(false)
  const [linkUrl, setLinkUrl] = useState('')
  const [showTextColor, setShowTextColor] = useState(false)
  const [showHighlightColor, setShowHighlightColor] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const linkInputRef = useRef<HTMLInputElement>(null)

  const setLink = useCallback(() => {
    if (linkUrl) {
      editor.chain().focus().setLink({ href: linkUrl }).run()
    } else {
      editor.chain().focus().unsetLink().run()
    }
    setShowLinkInput(false)
    setLinkUrl('')
  }, [editor, linkUrl])

  const handleImageClick = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file && onImageUpload) {
        onImageUpload(file)
      }
      e.target.value = ''
    },
    [onImageUpload]
  )

  const iconSize = 16

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 2,
          padding: '6px 8px',
          borderBottom: '1px solid var(--border, #e2e8f0)',
          background: 'var(--surface-2, #f8fafc)',
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}
      >
        {/* Undo / Redo */}
        <ToolbarButton
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          title="Undo (Ctrl+Z)"
        >
          <Undo2 size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          title="Redo (Ctrl+Y)"
        >
          <Redo2 size={iconSize} />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Headings */}
        <div style={{ position: 'relative' }}>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            active={editor.isActive('heading', { level: 1 })}
            title="Heading 1"
          >
            <Heading1 size={iconSize} />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            active={editor.isActive('heading', { level: 2 })}
            title="Heading 2"
          >
            <Heading2 size={iconSize} />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            active={editor.isActive('heading', { level: 3 })}
            title="Heading 3"
          >
            <Heading3 size={iconSize} />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 4 }).run()}
            active={editor.isActive('heading', { level: 4 })}
            title="Heading 4"
          >
            <Heading4 size={iconSize} />
          </ToolbarButton>
        </div>

        <ToolbarDivider />

        {/* Text Formatting */}
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBold().run()}
          active={editor.isActive('bold')}
          title="Bold (Ctrl+B)"
        >
          <Bold size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleItalic().run()}
          active={editor.isActive('italic')}
          title="Italic (Ctrl+I)"
        >
          <Italic size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          active={editor.isActive('underline')}
          title="Underline (Ctrl+U)"
        >
          <UnderlineIcon size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleStrike().run()}
          active={editor.isActive('strike')}
          title="Strikethrough"
        >
          <Strikethrough size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleCode().run()}
          active={editor.isActive('code')}
          title="Inline Code"
        >
          <Code size={iconSize} />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Colors */}
        <div style={{ position: 'relative' }}>
          <ToolbarButton
            onClick={() => { setShowTextColor(!showTextColor); setShowHighlightColor(false) }}
            active={editor.isActive('textStyle', { color: editor.getAttributes('textStyle').color })}
            title="Text Color"
          >
            <Palette size={iconSize} />
          </ToolbarButton>
          {showTextColor && (
            <ColorPicker
              value={editor.getAttributes('textStyle').color || '#000000'}
              onChange={(color) => editor.chain().focus().setColor(color).run()}
              onClose={() => setShowTextColor(false)}
            />
          )}
        </div>
        <div style={{ position: 'relative' }}>
          <ToolbarButton
            onClick={() => { setShowHighlightColor(!showHighlightColor); setShowTextColor(false) }}
            active={editor.isActive('highlight')}
            title="Highlight Color"
          >
            <Highlighter size={iconSize} />
          </ToolbarButton>
          {showHighlightColor && (
            <ColorPicker
              value={editor.getAttributes('highlight').color || '#fef08a'}
              onChange={(color) => editor.chain().focus().toggleHighlight({ color }).run()}
              onClose={() => setShowHighlightColor(false)}
            />
          )}
        </div>

        <ToolbarDivider />

        {/* Font Family */}
        <select
          onChange={(e) => {
            if (e.target.value) {
              editor.chain().focus().setFontFamily(e.target.value).run()
            } else {
              editor.chain().focus().unsetFontFamily().run()
            }
          }}
          value={editor.getAttributes('textStyle').fontFamily || ''}
          style={{
            height: 28,
            padding: '0 6px',
            borderRadius: 4,
            border: '1px solid var(--border, #e2e8f0)',
            fontSize: '0.75rem',
            background: 'var(--surface, #fff)',
            color: 'var(--text, #475569)',
            cursor: 'pointer',
          }}
        >
          <option value="">Default</option>
          <option value="Arial">Arial</option>
          <option value="Georgia">Georgia</option>
          <option value="Times New Roman">Times New Roman</option>
          <option value="Courier New">Courier New</option>
          <option value="Verdana">Verdana</option>
        </select>

        <ToolbarDivider />

        {/* Alignment */}
        <ToolbarButton
          onClick={() => editor.chain().focus().setTextAlign('left').run()}
          active={editor.isActive({ textAlign: 'left' })}
          title="Align Left"
        >
          <AlignLeft size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().setTextAlign('center').run()}
          active={editor.isActive({ textAlign: 'center' })}
          title="Align Center"
        >
          <AlignCenter size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().setTextAlign('right').run()}
          active={editor.isActive({ textAlign: 'right' })}
          title="Align Right"
        >
          <AlignRight size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().setTextAlign('justify').run()}
          active={editor.isActive({ textAlign: 'justify' })}
          title="Justify"
        >
          <AlignJustify size={iconSize} />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Lists */}
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          active={editor.isActive('bulletList')}
          title="Bullet List"
        >
          <List size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          active={editor.isActive('orderedList')}
          title="Numbered List"
        >
          <ListOrdered size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleTaskList().run()}
          active={editor.isActive('taskList')}
          title="Checklist"
        >
          <ListChecks size={iconSize} />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Block Elements */}
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          active={editor.isActive('blockquote')}
          title="Blockquote"
        >
          <Quote size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().setHorizontalRule().run()}
          title="Horizontal Rule"
        >
          <Minus size={iconSize} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleCodeBlock().run()}
          active={editor.isActive('codeBlock')}
          title="Code Block"
        >
          <CodeSquare size={iconSize} />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Link */}
        <ToolbarButton
          onClick={() => {
            if (editor.isActive('link')) {
              editor.chain().focus().unsetLink().run()
            } else {
              setShowLinkInput(true)
            }
          }}
          active={editor.isActive('link')}
          title="Insert Link"
        >
          <LinkIcon size={iconSize} />
        </ToolbarButton>

        {/* Image */}
        <ToolbarButton
          onClick={handleImageClick}
          title="Insert Image"
        >
          <ImageIcon size={iconSize} />
        </ToolbarButton>
      </div>

      {/* Link Input Popup */}
      {showLinkInput && (
        <div
          style={{
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 200,
            background: 'var(--surface, #fff)',
            border: '1px solid var(--border, #e2e8f0)',
            borderRadius: 8,
            padding: 16,
            boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            width: 320,
          }}
        >
          <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text, #334155)' }}>
            Insert Link
          </label>
          <input
            ref={linkInputRef}
            type="url"
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="https://example.com"
            autoFocus
            style={{
              padding: '8px 12px',
              border: '1px solid var(--border, #cbd5e1)',
              borderRadius: 6,
              fontSize: '0.85rem',
              width: '100%',
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') setLink()
              if (e.key === 'Escape') { setShowLinkInput(false); setLinkUrl('') }
            }}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
            <button
              type="button"
              onClick={() => { setShowLinkInput(false); setLinkUrl('') }}
              style={{
                padding: '6px 12px',
                border: '1px solid var(--border, #cbd5e1)',
                borderRadius: 6,
                background: 'var(--surface, #fff)',
                cursor: 'pointer',
                fontSize: '0.8rem',
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={setLink}
              style={{
                padding: '6px 12px',
                border: 'none',
                borderRadius: 6,
                background: 'var(--primary, #4f46e5)',
                color: '#fff',
                cursor: 'pointer',
                fontSize: '0.8rem',
              }}
            >
              Apply
            </button>
          </div>
        </div>
      )}

      {/* Backdrop for link popup */}
      {showLinkInput && (
        <div
          onClick={() => { setShowLinkInput(false); setLinkUrl('') }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 150,
          }}
        />
      )}
    </>
  )
}
