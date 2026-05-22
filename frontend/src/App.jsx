import { useState, useEffect, useRef } from 'react'
import '98.css'
import './App.css'
import Chat from './Chat'

const API = 'http://localhost:8000'

export default function App() {
  const [sessionId, setSessionId] = useState(null)
  const [books, setBooks] = useState([])
  const [selectedBook, setSelectedBook] = useState('')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)

  useEffect(() => {
    async function init() {
      const sessionRes = await fetch(`${API}/session`, { method: 'POST' })
      const { session_id } = await sessionRes.json()
      setSessionId(session_id)

      const booksRes = await fetch(`${API}/books`)
      const { books } = await booksRes.json()
      setBooks(books)
      if (books.length > 0) setSelectedBook(books[0].id)
    }
    init()
  }, [])

  async function handleUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    const uploadRes = await fetch(`${API}/session/${sessionId}/book`, { method: 'POST', body: formData })
    const { book_id } = await uploadRes.json()
    const booksRes = await fetch(`${API}/books`)
    const { books } = await booksRes.json()
    setBooks(books)
    setSelectedBook(book_id)
    setUploading(false)
    e.target.value = ''
  }

  async function handleSend(question) {
    setHistory(prev => [...prev, { role: 'user', content: question }])
    setLoading(true)

    const res = await fetch(`${API}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, book_id: selectedBook, question }),
    })
    const { answer } = await res.json()

    setHistory(prev => [...prev, { role: 'assistant', content: answer }])
    setLoading(false)
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'stretch', padding: '40px 16px', height: '100vh', boxSizing: 'border-box' }}>
      <div className="window" style={{ width: '660px', maxWidth: '100%', display: 'flex', flexDirection: 'column' }}>
        <div className="title-bar">
          <div className="title-bar-text">Steinbot</div>
          <div className="title-bar-controls">
            <button aria-label="Minimize"></button>
            <button aria-label="Maximize"></button>
            <button aria-label="Close"></button>
          </div>
        </div>

        <div className="window-body" style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1, overflow: 'hidden' }}>
          <fieldset>
            <legend>Book</legend>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <select value={selectedBook} onChange={e => setSelectedBook(e.target.value)}>
                {books.map(b => (
                  <option key={b.id} value={b.id}>{b.title}</option>
                ))}
              </select>
              <input
                ref={fileInputRef}
                type="file"
                accept=".epub,.epub.zip"
                style={{ display: 'none' }}
                onChange={handleUpload}
              />
              <button onClick={() => fileInputRef.current.click()} disabled={uploading}>
                {uploading ? 'Uploading...' : 'Upload EPUB'}
              </button>
            </div>
          </fieldset>

          <Chat
            history={history}
            loading={loading}
            onSend={handleSend}
            sessionReady={!!sessionId}
            selectedBook={selectedBook}
          />
        </div>
      </div>
    </div>
  )
}
