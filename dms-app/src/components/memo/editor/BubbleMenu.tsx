import { BubbleMenu as TipTapBubbleMenu } from '@tiptap/react'
import type { Editor } from '@tiptap/react'
import { Bold, Italic, Underline, Strikethrough, Code, Highlighter } from 'lucide-react'

interface BubbleMenuProps {
  editor: Editor
}

const btnStyle = (active: boolean): React.CSSProperties => ({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 28,
  height: 28,
  borderRadius: 4,
  border: 'none',
  background: active ? 'var(--primary, #4f46e5)' : 'transparent',
  color: active ? '#fff' : 'var(--text, #475569)',
  cursor: 'pointer',
  transition: 'all 0.15s',
})

export default function BubbleMenu({ editor }: BubbleMenuProps) {
  return (
    <TipTapBubbleMenu
      editor={editor}
      tippyOptions={{
        duration: 150,
        placement: 'top',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          padding: '4px 6px',
          background: 'var(--surface, #fff)',
          border: '1px solid var(--border, #e2e8f0)',
          borderRadius: 8,
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
        }}
      >
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBold().run()}
          style={btnStyle(editor.isActive('bold'))}
          title="Bold"
        >
          <Bold size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleItalic().run()}
          style={btnStyle(editor.isActive('italic'))}
          title="Italic"
        >
          <Italic size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          style={btnStyle(editor.isActive('underline'))}
          title="Underline"
        >
          <Underline size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleStrike().run()}
          style={btnStyle(editor.isActive('strike'))}
          title="Strikethrough"
        >
          <Strikethrough size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleCode().run()}
          style={btnStyle(editor.isActive('code'))}
          title="Code"
        >
          <Code size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleHighlight().run()}
          style={btnStyle(editor.isActive('highlight'))}
          title="Highlight"
        >
          <Highlighter size={14} />
        </button>
      </div>
    </TipTapBubbleMenu>
  )
}
