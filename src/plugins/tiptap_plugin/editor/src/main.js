import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight'
import { common, createLowlight } from 'lowlight'

import './style.css'

const lowlight = createLowlight(common)

let editor = null
let bridge = null   // set once QWebChannel connects

// ── Bridge ────────────────────────────────────────────────────────────────

function initBridge () {
  // QWebChannel is injected by Qt before this script runs.
  // In standalone browser mode (dev/preview) it won't be present.
  if (typeof QWebChannel === 'undefined' || typeof qt === 'undefined') {
    console.warn('[tiptap] Running without QWebChannel — bridge unavailable.')
    return
  }

  /* global qt */
  new QWebChannel(qt.webChannelTransport, (channel) => {
    bridge = channel.objects.bridge

    // Python → JS: load new content
    bridge.loadContent.connect((title, html) => {
      loadEditorContent(title, html)
    })

    // Python → JS: theme switch
    bridge.applyTheme.connect((theme) => {
      setTheme(theme)
    })

    // Python → JS: insert base64 image after native file-picker
    bridge.insertImageData.connect((dataUri) => {
      editor?.chain().focus().setImage({ src: dataUri }).run()
    })

    // Tell Python the editor is ready to receive content
    bridge.onReady()
  })
}

// ── Editor ────────────────────────────────────────────────────────────────

function initEditor () {
  editor = new Editor({
    element: document.getElementById('editor'),
    extensions: [
      StarterKit.configure({ codeBlock: false }),   // replaced by CodeBlockLowlight
      Underline,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Image.configure({ allowBase64: true }),
      Placeholder.configure({ placeholder: 'Start writing…' }),
      CodeBlockLowlight.configure({ lowlight }),
    ],
    onUpdate () {
      syncBridge()
      updateToolbarState()
    },
    onSelectionUpdate () {
      updateToolbarState()
    },
  })
}

function syncBridge () {
  if (!bridge || !editor) return
  bridge.onContentChanged(
    document.getElementById('title').value,
    editor.getHTML(),
  )
}

// ── Content ───────────────────────────────────────────────────────────────

function loadEditorContent (title, html) {
  const titleEl = document.getElementById('title')
  if (titleEl) titleEl.value = title ?? ''
  if (editor) {
    editor.commands.setContent(html || '<p></p>', false /* no history entry */)
    editor.commands.focus('end')
  }
}

// ── Toolbar ───────────────────────────────────────────────────────────────

const ACTIONS = {
  bold:        () => editor.chain().focus().toggleBold().run(),
  italic:      () => editor.chain().focus().toggleItalic().run(),
  underline:   () => editor.chain().focus().toggleUnderline().run(),
  strike:      () => editor.chain().focus().toggleStrike().run(),
  code:        () => editor.chain().focus().toggleCode().run(),
  h1:          () => editor.chain().focus().toggleHeading({ level: 1 }).run(),
  h2:          () => editor.chain().focus().toggleHeading({ level: 2 }).run(),
  h3:          () => editor.chain().focus().toggleHeading({ level: 3 }).run(),
  bulletList:  () => editor.chain().focus().toggleBulletList().run(),
  orderedList: () => editor.chain().focus().toggleOrderedList().run(),
  codeBlock:   () => editor.chain().focus().toggleCodeBlock().run(),
  blockquote:  () => editor.chain().focus().toggleBlockquote().run(),
  image:       () => bridge?.onInsertImage(),
  undo:        () => editor.chain().focus().undo().run(),
  redo:        () => editor.chain().focus().redo().run(),
}

// Which actions have a toggled / active visual state
const STATEFUL = [
  'bold', 'italic', 'underline', 'strike', 'code',
  'bulletList', 'orderedList', 'codeBlock', 'blockquote',
]

function updateToolbarState () {
  if (!editor) return
  for (const action of STATEFUL) {
    const btn = document.querySelector(`[data-action="${action}"]`)
    if (!btn) continue
    const active = action.startsWith('h')
      ? editor.isActive('heading', { level: Number(action[1]) })
      : editor.isActive(action)
    btn.classList.toggle('is-active', active)
  }
  // Heading buttons
  for (const level of [1, 2, 3]) {
    const btn = document.querySelector(`[data-action="h${level}"]`)
    if (btn) btn.classList.toggle('is-active', editor.isActive('heading', { level }))
  }
  // Undo / redo availability
  const undoBtn = document.querySelector('[data-action="undo"]')
  const redoBtn = document.querySelector('[data-action="redo"]')
  if (undoBtn) undoBtn.disabled = !editor.can().undo()
  if (redoBtn) redoBtn.disabled = !editor.can().redo()
}

// ── Theme ─────────────────────────────────────────────────────────────────

function setTheme (theme) {
  document.documentElement.setAttribute('data-theme', theme)
}

// Initialise from OS preference; Python overrides via applyTheme signal
if (window.matchMedia('(prefers-color-scheme: dark)').matches) setTheme('dark')

// ── Bootstrap ─────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initEditor()

  // Toolbar click delegation — single listener on the container
  document.getElementById('toolbar').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-action]')
    if (!btn || !editor) return
    ACTIONS[btn.dataset.action]?.()
    updateToolbarState()   // reflect state immediately (before next onUpdate fires)
  })

  // Save button
  document.getElementById('btn-save')?.addEventListener('click', () => {
    if (!bridge || !editor) return
    bridge.onSaveRequested(
      document.getElementById('title').value,
      editor.getHTML(),
    )
  })

  // Delete button
  document.getElementById('btn-delete')?.addEventListener('click', () => {
    bridge?.onDeleteRequested()
  })

  // Title input fires content-changed so Python cache stays current
  document.getElementById('title')?.addEventListener('input', syncBridge)

  // Ctrl+S / Cmd+S
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      if (bridge && editor) {
        bridge.onSaveRequested(
          document.getElementById('title').value,
          editor.getHTML(),
        )
      }
    }
  })

  initBridge()
})
