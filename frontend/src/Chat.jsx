import { useState, useEffect, useRef } from 'react'
import { Send } from 'lucide-react'
import Markdown from 'react-markdown'

// Adjust these to change how far the bubbles are inset from each side
const USER_MARGIN_LEFT = 20    // user bubble starts this far from the left
const BOT_MARGIN_RIGHT = 20    // steinbot bubble ends this far from the right

export default function Chat({ history, loading, onSend, sessionReady, selectedBook }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  function handleSubmit(e) {
    e.preventDefault()
    if (!input.trim() || !selectedBook || loading) return
    onSend(input.trim())
    setInput('')
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, gap: '8px' }}>
      <div
        className="sunken-panel"
        style={{ flex: 1, overflowY: 'auto', padding: '8px', fontFamily: 'monospace', fontSize: '13px', lineHeight: '1.5' }}
      >
        {history.length === 0 && (
          <span style={{ color: '#888' }}>Ask a question about the selected book...</span>
        )}
        {history.map((msg, i) => {
          const isUser = msg.role === 'user'
          return (
            <div
              key={i}
              style={{
                marginBottom: '10px',
                marginLeft: isUser ? USER_MARGIN_LEFT : 0,
                marginRight: isUser ? 0 : BOT_MARGIN_RIGHT,
                ...(isUser && { border: '1px solid #999', padding: '6px 8px', backgroundColor: '#ffe5cc' }),
              }}
            >
              <strong>{isUser ? 'You' : 'Steinbot'}:</strong>
              {isUser
                ? <span style={{ marginLeft: '6px', whiteSpace: 'pre-wrap' }}>{msg.content}</span>
                : <Markdown>{msg.content}</Markdown>
              }
            </div>
          )
        })}
        {loading && (
          <div style={{ color: '#888' }}><em>Steinbot is thinking...</em></div>
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '8px' }}>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask something about the book..."
          disabled={loading || !sessionReady}
          rows={4}
          style={{ flex: 1, fontFamily: 'inherit', fontSize: 'inherit', padding: '8px 10px', resize: 'none' }}
        />
        <button type="submit" disabled={loading || !selectedBook} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '8px 12px', color: 'black' }}>
          <Send size={18} />
        </button>
      </form>
    </div>
  )
}
