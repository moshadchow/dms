import type { Editor } from '@tiptap/react'
import {
  Trash2, Plus, Minus,
  TableCellsMerge, TableCellsSplit,
  ArrowUp, ArrowDown,
} from 'lucide-react'

interface TableMenuProps {
  editor: Editor
}

const btnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 26,
  height: 26,
  borderRadius: 4,
  border: 'none',
  background: 'transparent',
  color: 'var(--text, #475569)',
  cursor: 'pointer',
  transition: 'all 0.15s',
}

const dividerStyle: React.CSSProperties = {
  width: 1,
  height: 18,
  background: 'var(--border, #e2e8f0)',
  margin: '0 3px',
}

export default function TableMenu({ editor }: TableMenuProps) {
  if (!editor.isActive('table')) return null

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        padding: '4px 8px',
        borderBottom: '1px solid var(--border, #e2e8f0)',
        background: 'var(--surface-2, #f8fafc)',
        fontSize: '0.75rem',
      }}
    >
      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted, #64748b)', marginRight: 4 }}>
        Table:
      </span>

      <button
        type="button"
        onClick={() => editor.chain().focus().addColumnAfter().run()}
        style={btnStyle}
        title="Add Column After"
      >
        <Plus size={13} />
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().deleteColumn().run()}
        style={btnStyle}
        title="Delete Column"
      >
        <Minus size={13} />
      </button>

      <div style={dividerStyle} />

      <button
        type="button"
        onClick={() => editor.chain().focus().addRowAfter().run()}
        style={btnStyle}
        title="Add Row After"
      >
        <ArrowDown size={13} />
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().deleteRow().run()}
        style={btnStyle}
        title="Delete Row"
      >
        <ArrowUp size={13} />
      </button>

      <div style={dividerStyle} />

      <button
        type="button"
        onClick={() => editor.chain().focus().mergeCells().run()}
        disabled={!editor.can().mergeCells()}
        style={btnStyle}
        title="Merge Cells"
      >
        <TableCellsMerge size={13} />
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().splitCell().run()}
        disabled={!editor.can().splitCell()}
        style={btnStyle}
        title="Split Cell"
      >
        <TableCellsSplit size={13} />
      </button>

      <div style={dividerStyle} />

      <button
        type="button"
        onClick={() => editor.chain().focus().deleteTable().run()}
        style={{ ...btnStyle, color: '#ef4444' }}
        title="Delete Table"
      >
        <Trash2 size={13} />
      </button>
    </div>
  )
}
