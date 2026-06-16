import { useState, useCallback } from 'react'
import {
  Code2,
  Clipboard,
  ClipboardCheck,
  Download,
  Zap,
  Bot,
  AlertCircle,
  CheckCircle2,
  Loader2,
  FileJson,
  LayoutTemplate,
} from 'lucide-react'

const EXAMPLE_HTML = `<section style="background-color:#f8fafc; padding:60px 0">
  <div class="row">
    <div class="col-md-6">
      <h2>Welcome to Our Platform</h2>
      <p>Build beautiful pages with <strong>Elementor</strong> in seconds.</p>
      <a href="/get-started" class="btn">Get Started</a>
    </div>
    <div class="col-md-6">
      <img src="https://picsum.photos/600/400" alt="Hero image" />
    </div>
  </div>
</section>
<section>
  <h3>Features</h3>
  <ul>
    <li>Fast conversion</li>
    <li>Supports Bootstrap grid</li>
    <li>Complex CSS auto-detected</li>
  </ul>
</section>
<hr />`

function Badge({ children, variant = 'default' }) {
  const styles = {
    default:  'bg-slate-700 text-slate-300',
    success:  'bg-emerald-900/60 text-emerald-300 border border-emerald-700',
    warning:  'bg-amber-900/60 text-amber-300 border border-amber-700',
    info:     'bg-blue-900/60 text-blue-300 border border-blue-700',
    ai:       'bg-purple-900/60 text-purple-300 border border-purple-700',
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${styles[variant]}`}>
      {children}
    </span>
  )
}

export default function App() {
  const [html, setHtml]             = useState('')
  const [result, setResult]         = useState(null)
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState(null)
  const [useClaude, setUseClaude]   = useState(false)
  const [asTemplate, setAsTemplate] = useState(false)
  const [copied, setCopied]         = useState(false)

  const convert = useCallback(async () => {
    if (!html.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const endpoint = asTemplate ? '/convert/template' : '/convert'
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html, use_claude: useClaude }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}`)
      }

      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [html, useClaude, asTemplate])

  const jsonOutput = result
    ? (asTemplate ? result.template_json : result.json_string)
    : ''

  const copyToClipboard = useCallback(async () => {
    if (!jsonOutput) return
    await navigator.clipboard.writeText(jsonOutput)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [jsonOutput])

  const downloadJson = useCallback(() => {
    if (!jsonOutput) return
    const blob = new Blob([jsonOutput], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = asTemplate ? 'elementor-template.json' : 'elementor-data.json'
    a.click()
    URL.revokeObjectURL(url)
  }, [jsonOutput, asTemplate])

  const loadExample = () => setHtml(EXAMPLE_HTML)

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-700/60 bg-slate-900/80 backdrop-blur px-6 py-4 flex items-center gap-3">
        <div className="p-1.5 bg-indigo-600 rounded-lg">
          <Code2 className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-white leading-none">HTML → Elementor JSON</h1>
          <p className="text-xs text-slate-400 mt-0.5">Convert raw HTML to Elementor _elementor_data</p>
        </div>
      </header>

      {/* Toolbar */}
      <div className="border-b border-slate-700/60 bg-slate-900 px-6 py-2.5 flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 cursor-pointer select-none text-sm text-slate-300">
          <div
            className={`relative w-8 h-4 rounded-full transition-colors ${useClaude ? 'bg-purple-600' : 'bg-slate-600'}`}
            onClick={() => setUseClaude(v => !v)}
          >
            <span className={`absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform ${useClaude ? 'translate-x-4' : ''}`} />
          </div>
          <Bot className="w-4 h-4" />
          Claude AI fallback
        </label>

        <label className="flex items-center gap-2 cursor-pointer select-none text-sm text-slate-300">
          <div
            className={`relative w-8 h-4 rounded-full transition-colors ${asTemplate ? 'bg-indigo-600' : 'bg-slate-600'}`}
            onClick={() => setAsTemplate(v => !v)}
          >
            <span className={`absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform ${asTemplate ? 'translate-x-4' : ''}`} />
          </div>
          <LayoutTemplate className="w-4 h-4" />
          Template envelope
        </label>

        <button
          onClick={loadExample}
          className="ml-auto text-xs text-slate-400 hover:text-white transition-colors"
        >
          Load example HTML
        </button>
      </div>

      {/* Main panels */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left — HTML input */}
        <div className="flex flex-col flex-1 border-r border-slate-700/60">
          <div className="flex items-center justify-between px-4 py-2 bg-slate-800/60 border-b border-slate-700/60">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">HTML Input</span>
            <span className="text-xs text-slate-500">{html.length} chars</span>
          </div>
          <textarea
            className="flex-1 bg-slate-950 text-slate-200 font-mono text-sm p-4 resize-none outline-none placeholder-slate-600"
            placeholder="Paste your HTML here…"
            value={html}
            onChange={e => setHtml(e.target.value)}
            spellCheck={false}
          />
        </div>

        {/* Right — JSON output */}
        <div className="flex flex-col flex-1">
          <div className="flex items-center justify-between px-4 py-2 bg-slate-800/60 border-b border-slate-700/60">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Elementor JSON</span>
              {result && (
                <>
                  <Badge variant="success">
                    <CheckCircle2 className="w-3 h-3" />
                    {result.widget_count} widgets
                  </Badge>
                  <Badge variant={result.method === 'claude' ? 'ai' : 'info'}>
                    {result.method === 'claude' ? <Bot className="w-3 h-3" /> : <Zap className="w-3 h-3" />}
                    {result.method}
                  </Badge>
                </>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={copyToClipboard}
                disabled={!jsonOutput}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs bg-slate-700 hover:bg-slate-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                {copied ? <ClipboardCheck className="w-3.5 h-3.5 text-emerald-400" /> : <Clipboard className="w-3.5 h-3.5" />}
                {copied ? 'Copied!' : 'Copy'}
              </button>
              <button
                onClick={downloadJson}
                disabled={!jsonOutput}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs bg-slate-700 hover:bg-slate-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                Download
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-auto bg-slate-950 relative">
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm z-10">
                <div className="flex items-center gap-2 text-slate-300">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span className="text-sm">Converting…</span>
                </div>
              </div>
            )}

            {error && (
              <div className="m-4 p-3 rounded-lg bg-red-950/60 border border-red-800 flex gap-2 text-sm text-red-300">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {result?.error && (
              <div className="mx-4 mt-4 p-3 rounded-lg bg-amber-950/60 border border-amber-800 flex gap-2 text-sm text-amber-300">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{result.error}</span>
              </div>
            )}

            {jsonOutput ? (
              <pre className="p-4 text-xs text-emerald-300 font-mono whitespace-pre leading-relaxed">
                {jsonOutput}
              </pre>
            ) : !loading && !error && (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-600">
                <FileJson className="w-12 h-12" />
                <p className="text-sm">JSON output will appear here</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer / Convert button */}
      <div className="border-t border-slate-700/60 bg-slate-900 px-6 py-3 flex items-center justify-between">
        <div className="text-xs text-slate-500">
          {useClaude && <span className="text-purple-400">Claude AI fallback enabled — server-side, key stays private</span>}
        </div>
        <button
          onClick={convert}
          disabled={!html.trim() || loading}
          className="flex items-center gap-2 px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-medium text-white transition-colors shadow-lg shadow-indigo-900/40"
        >
          {loading
            ? <><Loader2 className="w-4 h-4 animate-spin" /> Converting…</>
            : <><Zap className="w-4 h-4" /> Convert</>
          }
        </button>
      </div>
    </div>
  )
}
