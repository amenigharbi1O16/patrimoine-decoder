import { useState, useEffect } from 'react'
import { jwtDecode } from 'jwt-decode'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const LANGUAGES = [
  'English', 'French', 'Spanish', 'Arabic',
  'German', 'Italian', 'Portuguese', 'Japanese', 'Turkish'
]

// ── SHARED RESULT PANEL ───────────────────────────────────
function AnalysisResultPanel({ result }) {
  if (!result) return null

  const showTranslation = !result.error && !result.vision_unavailable

  return (
    <div className="space-y-4">
      {result.error && (
        <div className="bg-yellow-900/20 border border-yellow-500/40 rounded-xl p-4 text-yellow-300 text-sm leading-relaxed">
          <p className="text-xs font-semibold uppercase text-yellow-400 mb-1">⚠️ Vision Service Unavailable</p>
          <p>{result.error}</p>
        </div>
      )}

      {result.verdict && result.verdict !== 'NO VALIDATION REQUIRED' && result.verdict !== 'NO AUTHOR CLAIM' && (
        <div className={`p-4 rounded-xl border flex items-center justify-between ${result.hallucination_detected
            ? 'bg-red-900/15 border-red-500/30'
            : 'bg-emerald-900/15 border-emerald-500/30'
          }`}>
          <div>
            <p className="text-xs text-slate-500 uppercase mb-1">MCP Validation Result</p>
            <p className={`text-xl font-bold ${result.hallucination_detected ? 'text-red-400' : 'text-emerald-400'}`}>
              {result.hallucination_detected ? '⚠️ HALLUCINATION DETECTED' : '✅ VERIFIED'}
            </p>
            {result.real_author && result.real_author !== 'N/A' && (
              <p className="text-xs text-slate-400 mt-1">
                Real author: <span className="text-white font-medium">{result.real_author}</span>
              </p>
            )}
          </div>
          <div className="text-right">
            <p className="text-xs text-slate-500 mb-1">Confidence</p>
            <p className={`text-3xl font-mono font-light ${result.confidence_score > 60 ? 'text-emerald-400' : 'text-red-400'
              }`}>
              {result.confidence_score}%
            </p>
          </div>
        </div>
      )}

      {result.explanation && (
        <div className="bg-orange-900/15 border border-orange-500/30 rounded-xl p-4">
          <p className="text-xs font-semibold uppercase text-orange-400 mb-1">⚠️ Why it's a hallucination</p>
          <p className="text-sm text-orange-200 leading-relaxed">{result.explanation}</p>
        </div>
      )}

      {result.verified_facts?.length > 0 && (
        <div className="bg-slate-800/40 rounded-xl p-4">
          <p className="text-xs font-semibold uppercase text-slate-500 mb-2">✅ Verified Facts from Catalog</p>
          <ul className="space-y-1">
            {result.verified_facts.map((fact, i) => (
              <li key={i} className="text-xs text-slate-400 flex gap-2">
                <span className="text-emerald-500 flex-shrink-0">›</span>{fact}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.language_detected && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-slate-500">Detected language:</span>
          <span className="text-indigo-300 font-medium">{result.language_detected}</span>
          {result.agent_memory_used && (
            <span className="text-xs bg-indigo-900/40 text-indigo-300 px-2 py-0.5 rounded-full border border-indigo-800 ml-2">
              🧠 Memory Active
            </span>
          )}
        </div>
      )}

      {result.ocr_transcription && (
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500 mb-2">📜 Original Transcription</p>
          <div className="bg-black/40 rounded-xl border border-slate-800 p-4
                          text-slate-300 text-sm leading-relaxed max-h-40
                          overflow-y-auto whitespace-pre-wrap font-serif"
            dir={result.language_detected === 'Arabic' ? 'rtl' : 'ltr'}>
            {result.ocr_transcription}
          </div>
        </div>
      )}

      {showTranslation && (
        result.translation ? (
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500 mb-2">
              🌐 Translation → {result.target_language}
            </p>
            <div className="bg-black/40 rounded-xl border border-indigo-900/40 p-4
                            text-slate-300 text-sm leading-relaxed max-h-48
                            overflow-y-auto whitespace-pre-wrap"
              dir={result.target_language === 'Arabic' ? 'rtl' : 'ltr'}>
              {result.translation}
            </div>
          </div>
        ) : (
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500 mb-2">
              🌐 Translation → {result.target_language}
            </p>
            <div className="bg-black/40 rounded-xl border border-slate-800 p-4 text-slate-600 text-sm italic">
              Translation unavailable — check Groq API or try again.
            </div>
          </div>
        )
      )}

      {result.historical_context && (
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500 mb-2">🏛️ Historical Context</p>
          <div className="bg-black/40 rounded-xl border border-slate-800 p-4
                          text-slate-400 text-sm leading-relaxed italic">
            {result.historical_context}
          </div>
        </div>
      )}

      {result.pipeline_steps?.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800">
          {result.pipeline_steps.map((step, i) => (
            <span key={i} className="text-xs bg-slate-800 text-slate-400 px-2 py-1 rounded-full">
              {step}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ── LOGIN / REGISTER ──────────────────────────────────────
function LoginPage({ onLogin }) {
  const [isLogin, setIsLogin] = useState(true)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return

    setLoading(true)
    setError('')
    
    const endpoint = isLogin ? '/api/login' : '/api/register'
    try {
      const res = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password })
      })
      const data = await res.json()
      
      if (!res.ok) {
        throw new Error(data.detail || 'Authentication failed')
      }
      
      onLogin(data.access_token)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0B0F19] flex items-center justify-center p-6">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden">
        
        {/* Toggle tabs */}
        <div className="flex border-b border-slate-700">
          <button 
            className={`flex-1 py-4 font-semibold text-sm transition-colors ${isLogin ? 'text-indigo-400 border-b-2 border-indigo-400 bg-slate-800/50' : 'text-slate-500 hover:text-slate-300'}`}
            onClick={() => { setIsLogin(true); setError(''); setPassword('') }}
          >
            Login
          </button>
          <button 
            className={`flex-1 py-4 font-semibold text-sm transition-colors ${!isLogin ? 'text-indigo-400 border-b-2 border-indigo-400 bg-slate-800/50' : 'text-slate-500 hover:text-slate-300'}`}
            onClick={() => { setIsLogin(false); setError(''); setPassword('') }}
          >
            Register
          </button>
        </div>

        <div className="p-8">
          <div className="text-center mb-6">
            <div className="text-4xl mb-3">📜</div>
            <h1 className="text-2xl font-bold text-white mb-1">
              Heritage<span className="text-indigo-400">Decoder</span>
            </h1>
            <p className="text-slate-500 text-xs tracking-widest uppercase">
              Secure Agentic Workspace
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-3 mt-1
                           text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                placeholder="Researcher ID"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-3 mt-1
                           text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="text-red-400 text-sm font-medium bg-red-900/20 border border-red-900/50 p-3 rounded-lg">
                ⚠️ {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !username.trim() || !password.trim()}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700
                         disabled:text-slate-500 text-white font-semibold py-3 rounded-lg
                         transition-all mt-4 shadow-lg shadow-indigo-500/20"
            >
              {loading ? 'Authenticating...' : (isLogin ? 'Enter Workspace →' : 'Create Account →')}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

// ── ANALYZE ───────────────────────────────────────────────
function AnalyzePage({ token, onNewResult }) {
  const [inputMode, setInputMode] = useState('image')
  const [file, setFile] = useState(null)
  const [textInput, setTextInput] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [manuscripts, setManuscripts] = useState([])
  const [selectedMs, setSelectedMs] = useState('none')
  const [claimedAuthor, setClaimedAuthor] = useState('')
  const [targetLang, setTargetLang] = useState('English')
  const [loading, setLoading] = useState(false)
  const [logs, setLogs] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API}/api/manuscripts`)
      .then(r => r.json())
      .then(setManuscripts)
      .catch(console.error)
  }, [])

  const addLog = (msg) => setLogs(prev => [...prev, msg])

  const handleFileSelect = (selectedFile) => {
    if (!selectedFile) return
    setFile(selectedFile)
    const name = selectedFile.name.toLowerCase().replace(/-/g, '_').replace(/ /g, '_')
    if (name.includes('add_ms_7474')) {
      setSelectedMs('add_ms_7474')
    } else if (name.includes('or_9011')) {
      setSelectedMs('or_9011')
    }
  }

  const handleAnalyze = async () => {
    if (inputMode === 'image' && !file) return
    if (inputMode === 'text' && !textInput.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)
    setLogs([])

    const logMessages = [
      '🔍 Initializing pipeline...',
      '👁️ OCR Agent reading manuscript...',
      `🌐 Translation Agent working (→ ${targetLang})...`,
      '🗄️ Connecting to MCP Catalog Server...',
      '✅ Validation Agent cross-referencing...',
      '🧠 Memory Agent loading session context...',
      '📊 Assembling final report...'
    ]
    let i = 0
    const interval = setInterval(() => {
      if (i < logMessages.length) addLog(logMessages[i++])
      else clearInterval(interval)
    }, 900)

    const formData = new FormData()
    if (inputMode === 'image' && file) formData.append('file', file)
    formData.append('text_input', inputMode === 'text' ? textInput : '')
    formData.append('manuscript_id', selectedMs)
    formData.append('claimed_author', claimedAuthor)
    formData.append('target_language', targetLang)

    try {
      const res = await fetch(`${API}/api/analyze`, { 
        method: 'POST', 
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData 
      })
      clearInterval(interval)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setResult(data)
      onNewResult()
    } catch (e) {
      clearInterval(interval)
      setError('Analysis failed. Check backend connection or API quota.')
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* ── PANEL GAUCHE : Configuration ── */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-5">
        <h2 className="text-white font-semibold text-lg flex items-center gap-2">
          ⚙️ Pipeline Configuration
        </h2>

        {/* Mode switcher */}
        <div className="flex rounded-xl overflow-hidden border border-slate-700">
          {['image', 'text'].map(mode => (
            <button
              key={mode}
              onClick={() => setInputMode(mode)}
              className={`flex-1 py-2 text-sm font-medium transition-all ${inputMode === mode
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-white'
                }`}
            >
              {mode === 'image' ? '🖼️ Image Upload' : '📝 Paste Text'}
            </button>
          ))}
        </div>

        {/* Image upload */}
        {inputMode === 'image' && (
          <div
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${dragActive ? 'border-indigo-500 bg-indigo-500/10'
                : file ? 'border-emerald-500 bg-emerald-500/5'
                  : 'border-slate-700 hover:border-slate-500'
              }`}
            onDragEnter={e => { e.preventDefault(); setDragActive(true) }}
            onDragLeave={e => { e.preventDefault(); setDragActive(false) }}
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault(); setDragActive(false)
              if (e.dataTransfer.files[0]) handleFileSelect(e.dataTransfer.files[0])
            }}
            onClick={() => document.getElementById('file-input').click()}
          >
            <input
              id="file-input" type="file" accept="image/*" className="hidden"
              onChange={e => e.target.files[0] && handleFileSelect(e.target.files[0])}
            />
            <div className="text-3xl mb-2">{file ? '✅' : '📁'}</div>
            <p className="text-sm text-slate-300">
              {file ? file.name : 'Drag & drop or click to upload'}
            </p>
            <p className="text-xs text-slate-500 mt-1">JPG, PNG, any manuscript image</p>
          </div>
        )}

        {/* Text input */}
        {inputMode === 'text' && (
          <textarea
            value={textInput}
            onChange={e => setTextInput(e.target.value)}
            placeholder="Paste your manuscript text here (Arabic, Latin, French, any language)..."
            rows={6}
            className="w-full bg-slate-800 border border-slate-700 rounded-xl p-4
                       text-slate-200 placeholder-slate-500 focus:outline-none
                       focus:ring-2 focus:ring-indigo-500 resize-none text-sm"
          />
        )}

        {/* Language */}
        <div>
          <label className="text-xs font-semibold uppercase text-slate-500 mb-2 block">
            Target Translation Language
          </label>
          <select
            value={targetLang}
            onChange={e => setTargetLang(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3
                       text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {LANGUAGES.map(l => <option key={l}>{l}</option>)}
          </select>
        </div>

        {/* MCP Catalog */}
        <div>
          <label className="text-xs font-semibold uppercase text-slate-500 mb-2 block">
            MCP Ground Truth Catalog
          </label>
          <select
            value={selectedMs}
            onChange={e => setSelectedMs(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3
                       text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="none">No Catalog (Translation Only)</option>
            {manuscripts.map(m => (
              <option key={m.id} value={m.id}>{m.title} ({m.date})</option>
            ))}
          </select>
        </div>

        {/* Claimed author */}
        {selectedMs !== 'none' && (
          <div>
            <label className="text-xs font-semibold uppercase text-slate-500 mb-2 block">
              Test Claimed Author (Hallucination Check)
            </label>
            <input
              type="text"
              value={claimedAuthor}
              onChange={e => setClaimedAuthor(e.target.value)}
              placeholder="e.g. Ibn al-Haytham"
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3
                         text-slate-200 placeholder-slate-500 focus:outline-none
                         focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        )}

        <button
          onClick={handleAnalyze}
          disabled={loading || (inputMode === 'image' ? !file : !textInput.trim())}
          className="w-full py-3 rounded-xl font-semibold text-white transition-all
                     bg-indigo-600 hover:bg-indigo-500
                     disabled:bg-slate-800 disabled:text-slate-600
                     shadow-[0_0_20px_rgba(99,102,241,0.3)]
                     hover:shadow-[0_0_30px_rgba(99,102,241,0.5)]"
        >
          {loading ? '⏳ Agents Working...' : '🚀 Run Multi-Agent Analysis'}
        </button>
      </div>

      {/* ── PANEL DROIT : Résultats ── */}
      <div className="bg-[#0d1120] border border-slate-800 rounded-2xl overflow-hidden flex flex-col">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="text-sm font-medium text-slate-300">Live Agent Telemetry</span>
        </div>

        <div className="p-6 flex-1 overflow-y-auto space-y-4">
          {/* Logs */}
          {loading && (
            <div className="font-mono text-sm space-y-2">
              {logs.map((log, i) => (
                <div key={i} className="flex gap-2 text-slate-300">
                  <span className="text-indigo-400">›</span> {log}
                </div>
              ))}
              <div className="flex gap-2 text-indigo-400 animate-pulse mt-2">
                <span>▋</span> Processing...
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-900/20 border border-red-500/40 rounded-xl p-4 text-red-400 text-sm font-mono">
              ❌ {error}
            </div>
          )}

          {/* Idle */}
          {!loading && !result && !error && (
            <div className="h-full flex items-center justify-center text-slate-600 font-mono text-sm">
              Awaiting pipeline execution...
            </div>
          )}

          {/* Résultats */}
          {result && !loading && <AnalysisResultPanel result={result} />}
        </div>
      </div>
    </div>
  )
}

// ── HISTORIQUE ────────────────────────────────────────────
function HistoryPage({ token }) {
  const [history, setHistory] = useState([])
  const [stats, setStats] = useState(null)
  const [expanded, setExpanded] = useState(null)
  const [fullResult, setFullResult] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API}/api/history`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => {
        if (!r.ok) throw new Error('Failed to load history')
        return r.json()
      })
      .then(setHistory)
      .catch(err => setError(err.message))

    fetch(`${API}/api/stats`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => {
        if (!r.ok) throw new Error('Failed to load stats')
        return r.json()
      })
      .then(setStats)
      .catch(console.error)
  }, [token])

  const handleExpand = async (id) => {
    if (expanded === id) {
      setExpanded(null)
      setFullResult(null)
      return
    }
    setExpanded(id)
    setLoadingDetail(true)
    try {
      const res = await fetch(`${API}/api/analysis/${id}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      })
      if (res.ok) {
        setFullResult(await res.json())
      } else {
        setFullResult(history.find(h => h.id === id) || null)
      }
    } catch {
      setFullResult(history.find(h => h.id === id) || null)
    } finally {
      setLoadingDetail(false)
    }
  }

  if (error) {
    return <div className="text-center text-red-400 p-8">{error}</div>
  }

  return (
    <div className="space-y-6">
      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Analyses', value: stats.total_analyses, icon: '📊', color: 'indigo' },
            { label: 'Hallucinations Caught', value: stats.hallucinations_caught, icon: '⚠️', color: 'red' },
            { label: 'Hallucination Rate', value: stats.hallucination_rate, icon: '📈', color: 'orange' },
            { label: 'Agent Memory', value: stats.agent_memory, icon: '🧠', color: 'emerald' },
          ].map(s => (
            <div key={s.label} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <p className="text-2xl mb-1">{s.icon}</p>
              <p className={`text-2xl font-bold ${s.color === 'red' ? 'text-red-400' :
                  s.color === 'orange' ? 'text-orange-400' :
                    s.color === 'emerald' ? 'text-emerald-400' : 'text-indigo-400'
                }`}>{s.value}</p>
              <p className="text-xs text-slate-500 uppercase tracking-wide mt-1">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {stats?.languages_used?.length > 0 && (
        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-xs text-slate-500">Languages analyzed:</span>
          {stats.languages_used.map(l => (
            <span key={l} className="text-xs bg-slate-800 text-slate-300 px-2 py-1 rounded-full">{l}</span>
          ))}
        </div>
      )}

      {/* Liste historique */}
      <div className="space-y-3">
        <h3 className="text-white font-semibold flex items-center gap-2">
          📚 Semantic RAG Memory
          <span className="text-xs text-slate-500 font-normal">— agents use this to contextualize future results</span>
        </h3>
        {history.length === 0 ? (
          <div className="text-center text-slate-600 py-12 font-mono text-sm">
            No analyses yet. Run your first pipeline above.
          </div>
        ) : (
          history.map(entry => (
            <div key={entry.id}
              className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden
                         cursor-pointer hover:border-slate-600 transition-all">
              <div className="p-4 flex items-center gap-4" onClick={() => handleExpand(entry.id)}>
                <div className={`w-1.5 h-10 rounded-full flex-shrink-0 ${entry.verdict === 'HALLUCINATION' ? 'bg-red-500' :
                    entry.verdict === 'VERIFIED' ? 'bg-emerald-500' : 'bg-slate-600'
                  }`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">{entry.image_filename}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                     {entry.target_language} · {entry.manuscript_id} ·{' '}
                    {new Date(entry.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="text-right flex-shrink-0">
                  <span className={`text-xs font-bold px-2 py-1 rounded-full ${entry.verdict === 'HALLUCINATION' ? 'bg-red-900/40 text-red-400' :
                      entry.verdict === 'VERIFIED' ? 'bg-emerald-900/40 text-emerald-400' :
                        'bg-slate-800 text-slate-400'
                    }`}>
                    {entry.verdict}
                  </span>
                  <p className="text-xs text-slate-500 mt-1">{entry.confidence_score}%</p>
                </div>
              </div>
              {expanded === entry.id && (
                <div className="px-4 pb-4 border-t border-slate-800 pt-4">
                  {loadingDetail ? (
                    <p className="text-sm text-slate-500 font-mono animate-pulse">Loading full analysis...</p>
                  ) : (
                    <AnalysisResultPanel result={fullResult} />
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ── APP PRINCIPAL ─────────────────────────────────────────
export default function App() {
  const [token, setToken] = useState(
    () => localStorage.getItem('heritage_token') || null
  )
  const [username, setUsername] = useState(null)
  const [tab, setTab] = useState('analyze')
  const [historyKey, setHistoryKey] = useState(0)

  // Verify and decode token on load/change
  useEffect(() => {
    if (token) {
      try {
        const decoded = jwtDecode(token)
        if (decoded.exp * 1000 < Date.now()) {
          handleLogout() // expired
        } else {
          setUsername(decoded.sub)
        }
      } catch (err) {
        handleLogout() // invalid token
      }
    }
  }, [token])

  const handleLogin = (newToken) => {
    localStorage.setItem('heritage_token', newToken)
    setToken(newToken)
  }

  const handleLogout = () => {
    localStorage.removeItem('heritage_token')
    setToken(null)
    setUsername(null)
  }

  if (!token) return <LoginPage onLogin={handleLogin} />

  return (
    <div className="min-h-screen bg-[#0B0F19] text-slate-300">
      <div className="max-w-6xl mx-auto p-6 lg:p-8">
        {/* Header */}
        <header className="flex items-center justify-between mb-8 border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">
              Heritage<span className="text-indigo-400">Decoder</span>
            </h1>
            <p className="text-slate-500 text-xs uppercase tracking-widest mt-1">
              Multi-Agent Translation & Archival Grounding
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-slate-400 bg-slate-900 px-3 py-1.5 rounded-full border border-slate-800">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="font-mono">{username}</span>
            </div>
            <button
              onClick={handleLogout}
              className="text-xs font-semibold text-slate-400 hover:text-white border border-slate-700
                         hover:border-slate-500 px-3 py-1.5 rounded-lg transition-all"
            >
              Logout
            </button>
          </div>
        </header>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {[
            { id: 'analyze', label: '🔍 Analyze' },
            { id: 'history', label: '📚 History & Memory' }
          ].map(t => (
            <button
              key={t.id}
              onClick={() => {
                setTab(t.id)
                if (t.id === 'history') setHistoryKey(k => k + 1)
              }}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${tab === t.id
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                  : 'bg-slate-800/60 text-slate-400 hover:text-white hover:bg-slate-800'
                }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Pages */}
        {tab === 'analyze' && (
          <AnalyzePage token={token} onNewResult={() => { }} />
        )}
        {tab === 'history' && (
          <HistoryPage key={historyKey} token={token} />
        )}
      </div>
    </div>
  )
}