
import { useCallback, useEffect, useState } from 'react'
import {
  FileText,
  Upload,
  Search,
  Database,
  Loader2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Sparkles,
  ShieldCheck,
} from 'lucide-react'

const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

interface RagDocument {
  id: string
  content: string
  metadata: {
    file_name?: string
    source?: string
    year?: number
    [key: string]: unknown
  }
  similarity: number
  distance: number
}

interface RagSearchResult {
  query: string
  context: string
  documents: RagDocument[]
  sources: {
    id: string
    source: string
    page: number | null
    year?: number | null
    similarity: number
  }[]
  retrieved_count: number
  has_context: boolean
  answer?: string | null
  ai_status?: string
  ai_reason?: string
  ai_model?: string | null
  ai_duration_ms?: number
  year_filter?: number[] | null
}

interface RagStats {
  service: string
  batch_size: number
  vector_store: {
    collection_name: string
    document_count: number
    persist_directory: string
    embedding_model: string
    distance_metric: string
  }
}

export default function RagPanel() {
  const [token, setToken] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [searching, setSearching] = useState(false)
  const [loadingStats, setLoadingStats] = useState(false)

  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)

  const [stats, setStats] = useState<RagStats | null>(null)
  const [searchResult, setSearchResult] =
    useState<RagSearchResult | null>(null)

  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const authHeaders = useCallback(() => ({
    Authorization: `Bearer ${token.trim()}`,
    Accept: 'application/json',
  }), [token])

  const refreshStats = useCallback(async () => {
    if (!token.trim()) {
      setError('Enter your JWT access token first.')
      return
    }

    setLoadingStats(true)
    setError('')

    try {
      const response = await fetch(`${API}/api/rag/stats`, {
        method: 'GET',
        headers: authHeaders(),
        cache: 'no-store',
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.detail || `Stats request failed: ${response.status}`,
        )
      }

      setStats(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to load RAG stats.',
      )
    } finally {
      setLoadingStats(false)
    }
  }, [authHeaders, token])

  useEffect(() => {
    if (token.trim()) {
      void refreshStats()
    } else {
      setStats(null)
    }
  }, [token, refreshStats])

  const uploadDocument = async () => {
    if (!token.trim()) {
      setError('Enter your JWT access token first.')
      return
    }

    if (!file) {
      setError('Please select a document to upload.')
      return
    }

    setUploading(true)
    setError('')
    setMessage('')
    setSearchResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${API}/api/rag/ingest`, {
        method: 'POST',
        headers: authHeaders(),
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.detail || `Upload failed: ${response.status}`,
        )
      }

      setMessage(
        `Successfully ingested ${data.chunks_stored ?? data.chunks_created ?? 0} document chunks.`,
      )
      setFile(null)

      await refreshStats()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Document upload failed.',
      )
    } finally {
      setUploading(false)
    }
  }

  const searchDocuments = async () => {
    if (!token.trim()) {
      setError('Enter your JWT access token first.')
      return
    }

    if (query.trim().length < 3) {
      setError('Search query must contain at least 3 characters.')
      return
    }

    setSearching(true)
    setError('')
    setMessage('')
    setSearchResult(null)

    try {
      const response = await fetch(`${API}/api/rag/search`, {
        method: 'POST',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query.trim(),
          top_k: topK,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.detail || `Search failed: ${response.status}`,
        )
      }

      setSearchResult(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Document search failed.',
      )
    } finally {
      setSearching(false)
    }
  }

  return (
    <section className="rag-page">
      <div className="rag-heading">
        <div>
          <div className="rag-eyebrow">
            <Sparkles size={14} />
            INTELLIGENCE / KNOWLEDGE BASE
          </div>
          <h2>Document Intelligence</h2>
          <p>
            Upload business documents and retrieve relevant information
            using semantic search.
          </p>
        </div>

        <div className="rag-status">
          <Database size={15} />
          CHROMADB
        </div>
      </div>

      {/* Authentication */}
      <div className="rag-panel">
        <div className="rag-panel-title">
          <ShieldCheck size={18} />
          <div>
            <b>Authentication</b>
            <small>Use your existing ORBIT JWT access token.</small>
          </div>
        </div>

        <input
          className="rag-input"
          type="password"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="Paste JWT access token"
          autoComplete="off"
        />

        <p className="rag-hint">
          Token stays in this component's memory and is not saved to storage.
        </p>
      </div>

      {/* Statistics */}
      <div className="rag-stats-grid">
        <div className="rag-stat">
          <Database size={19} />
          <small>STORED DOCUMENTS</small>
          <strong>
            {stats ? stats.vector_store.document_count : '—'}
          </strong>
        </div>

        <div className="rag-stat">
          <Sparkles size={19} />
          <small>EMBEDDING MODEL</small>
          <strong className="rag-model">
            {stats?.vector_store.embedding_model || '—'}
          </strong>
        </div>

        <div className="rag-stat">
          <FileText size={19} />
          <small>DISTANCE METRIC</small>
          <strong>
            {stats?.vector_store.distance_metric || '—'}
          </strong>
        </div>
      </div>

      {/* Upload Documents */}
      <div className="rag-panel">
        <div className="rag-panel-title">
          <Upload size={18} />
          <div>
            <b>Upload Documents</b>
            <small>Supported formats: PDF, TXT and CSV · Max 20 MB</small>
          </div>
        </div>

        <label className="rag-file-picker">
          <input
            type="file"
            accept=".pdf,.txt,.csv"
            onChange={(event) =>
              setFile(event.target.files?.[0] || null)
            }
          />

          <FileText size={25} />
          <b>{file ? file.name : 'Choose a document'}</b>
          <small>
            {file
              ? `${(file.size / 1024 / 1024).toFixed(2)} MB`
              : 'Click to browse PDF, TXT or CSV files'}
          </small>
        </label>

        <button
          className="rag-primary-button"
          onClick={() => void uploadDocument()}
          disabled={!file || uploading}
        >
          {uploading ? (
            <>
              <Loader2 className="rag-spin" size={16} />
              Processing document...
            </>
          ) : (
            <>
              <Upload size={16} />
              Upload and index
            </>
          )}
        </button>
      </div>

      {/* Semantic Search */}
      <div className="rag-panel">
        <div className="rag-panel-title">
          <Search size={18} />
          <div>
            <b>Semantic Document Search</b>
            <small>Search using natural language questions.</small>
          </div>
        </div>

        <textarea
          className="rag-input rag-search-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Example: Which product generated the highest revenue in 2024?"
        />

        <div className="rag-search-options">
          <label>
            Results to retrieve
            <select
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
            >
              {[1, 3, 5, 10, 15, 20].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <button
            className="rag-primary-button"
            onClick={() => void searchDocuments()}
            disabled={searching || query.trim().length < 3}
          >
            {searching ? (
              <>
                <Loader2 className="rag-spin" size={16} />
                Searching...
              </>
            ) : (
              <>
                <Search size={16} />
                Search documents
              </>
            )}
          </button>
        </div>
      </div>

      {/* Messages */}
      {message && (
        <div className="rag-message rag-success">
          <CheckCircle2 size={17} />
          {message}
        </div>
      )}

      {error && (
        <div className="rag-message rag-error">
          <AlertCircle size={17} />
          {error}
        </div>
      )}

      {/* Search Results */}
      {searchResult && (
        <div className="rag-results">

          <div className="rag-results-heading">
            <div>
              <small>SEARCH RESULTS</small>
              <h3>
                {searchResult.retrieved_count} documents retrieved
              </h3>
            </div>

            <span className="rag-found">
              {searchResult.has_context ? 'CONTEXT FOUND' : 'NO CONTEXT'}
            </span>
          </div>

          {/* ORBIT AI ANSWER */}
          {searchResult.answer && (
            <section
              className="rag-ai-answer"
              aria-live="polite"
              style={{
                marginBottom: '22px',
                padding: '22px',
                borderRadius: '14px',
                border: '1px solid rgba(139, 92, 246, 0.35)',
                background: 'rgba(139, 92, 246, 0.07)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  flexWrap: 'wrap',
                  marginBottom: '14px',
                }}
              >
                <Sparkles size={19} color="#a78bfa" />

                <div style={{ flex: 1 }}>
                  <b style={{ display: 'block' }}>
                    ORBIT AI Answer
                  </b>
                  <small style={{ opacity: 0.7 }}>
                    {searchResult.ai_model || 'Document-grounded response'}
                  </small>
                </div>

                {searchResult.ai_status && (
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '5px 9px',
                      borderRadius: '20px',
                      background:
                        searchResult.ai_status === 'accepted'
                          ? 'rgba(34,197,94,0.15)'
                          : 'rgba(234,179,8,0.15)',
                      color:
                        searchResult.ai_status === 'accepted'
                          ? '#22c55e'
                          : '#eab308',
                    }}
                  >
                    {searchResult.ai_status.toUpperCase()}
                  </span>
                )}
              </div>

              <p
                style={{
                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.8,
                  margin: 0,
                }}
              >
                {searchResult.answer}
              </p>

              {searchResult.ai_status === 'accepted' &&
                searchResult.ai_duration_ms !== undefined && (
                  <small
                    style={{
                      display: 'block',
                      marginTop: '14px',
                      opacity: 0.65,
                    }}
                  >
                    <CheckCircle2
                      size={12}
                      style={{
                        display: 'inline',
                        verticalAlign: 'middle',
                        marginRight: '5px',
                      }}
                    />
                    Generated in {searchResult.ai_duration_ms} ms
                  </small>
                )}

              {searchResult.ai_reason &&
                searchResult.ai_status !== 'accepted' && (
                  <small
                    style={{
                      display: 'block',
                      marginTop: '12px',
                      opacity: 0.7,
                    }}
                  >
                    AI status: {searchResult.ai_reason}
                  </small>
                )}

              {searchResult.year_filter &&
                searchResult.year_filter.length > 0 && (
                  <small
                    style={{
                      display: 'block',
                      marginTop: '10px',
                      opacity: 0.7,
                    }}
                  >
                    Years searched: {searchResult.year_filter.join(', ')}
                  </small>
                )}
            </section>
          )}

          {!searchResult.has_context && (
            <p className="rag-hint">
              No relevant document context was found. Try another query
              or upload additional documents.
            </p>
          )}

          {/* Retrieved Documents */}
          {searchResult.documents.map((document) => (
            <article className="rag-document" key={document.id}>
              <div className="rag-document-heading">
                <FileText size={17} />

                <b>
                  {document.metadata.file_name ||
                    document.metadata.source ||
                    'Retrieved document'}
                </b>

                <span>
                  {(document.similarity * 100).toFixed(1)}% match
                </span>
              </div>

              <p>{document.content}</p>

              <small>
                Similarity score: {document.similarity.toFixed(4)}
                {document.metadata.year
                  ? ` · Year: ${document.metadata.year}`
                  : ''}
              </small>
            </article>
          ))}
        </div>
      )}

      {/* Refresh Stats */}
      <div className="rag-refresh">
        <button
          className="rag-secondary-button"
          onClick={() => void refreshStats()}
          disabled={loadingStats || !token.trim()}
        >
          {loadingStats ? (
            <Loader2 className="rag-spin" size={15} />
          ) : (
            <RefreshCw size={15} />
          )}
          Refresh document statistics
        </button>
      </div>
    </section>
  )
}
