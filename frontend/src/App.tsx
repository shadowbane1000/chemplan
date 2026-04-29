import { useEffect, useRef, useState } from 'react'
import { Editor } from 'ketcher-react'
import type { Ketcher } from 'ketcher-core'
import { StandaloneStructServiceProvider } from 'ketcher-standalone'
import 'ketcher-react/dist/index.css'
import './App.css'

const structServiceProvider = new StandaloneStructServiceProvider()

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8123'

type PlanStats = {
  is_solved: boolean
  number_of_steps: number
  number_of_precursors: number
  number_of_precursors_in_stock: number
  precursors_in_stock: string
  precursors_not_in_stock: string
  search_time: number
}

type PlanResponse = {
  smiles: string
  stats: PlanStats
  top_route: {
    score: { 'state score': number }
    image_png_b64: string
  }
}

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
}

function App() {
  const ketcherRef = useRef<Ketcher | null>(null)
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [planError, setPlanError] = useState<string | null>(null)
  const [planLoading, setPlanLoading] = useState(false)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatStreaming, setChatStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [chatError, setChatError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  async function handlePlan() {
    setPlanError(null)
    setPlan(null)

    const ketcher = ketcherRef.current
    if (!ketcher) {
      setPlanError('Editor not ready yet.')
      return
    }

    let smiles: string
    try {
      smiles = await ketcher.getSmiles()
    } catch (e) {
      setPlanError(`Couldn't read SMILES from canvas: ${String(e)}`)
      return
    }

    if (!smiles || !smiles.trim()) {
      setPlanError('Draw a target molecule first.')
      return
    }

    setPlanLoading(true)
    try {
      const res = await fetch(`${BACKEND}/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ smiles: smiles.trim() }),
      })
      if (!res.ok) {
        const detail = await res.text()
        throw new Error(`HTTP ${res.status}: ${detail}`)
      }
      const data = (await res.json()) as PlanResponse
      setPlan(data)
    } catch (e) {
      setPlanError(String(e))
    } finally {
      setPlanLoading(false)
    }
  }

  async function handleChatSubmit(e: React.FormEvent) {
    e.preventDefault()
    const text = chatInput.trim()
    if (!text || chatStreaming) return

    setChatError(null)

    let canvasSmiles: string | null = null
    try {
      canvasSmiles = (await ketcherRef.current?.getSmiles()) ?? null
    } catch {
      canvasSmiles = null
    }

    const newHistory: ChatMessage[] = [...messages, { role: 'user', content: text }]
    setMessages(newHistory)
    setChatInput('')
    setChatStreaming(true)
    setStreamingText('')

    try {
      const res = await fetch(`${BACKEND}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          history: newHistory,
          canvas_smiles: canvasSmiles,
          plan,
        }),
      })
      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let assistantText = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.trim()) continue
          let event: { type: string; text?: string; message?: string }
          try {
            event = JSON.parse(line)
          } catch {
            continue
          }
          if (event.type === 'delta' && event.text) {
            assistantText += event.text
            setStreamingText(assistantText)
          } else if (event.type === 'error') {
            throw new Error(event.message ?? 'unknown error')
          }
        }
      }

      setMessages([...newHistory, { role: 'assistant', content: assistantText }])
      setStreamingText('')
    } catch (e) {
      setChatError(String(e))
      setStreamingText('')
    } finally {
      setChatStreaming(false)
    }
  }

  return (
    <div className="app">
      <main className="canvas">
        <Editor
          staticResourcesUrl=""
          structServiceProvider={structServiceProvider}
          errorHandler={(message: string) => console.error('ketcher error:', message)}
          buttons={{
            miew: { hidden: true },
          }}
          onInit={(k: Ketcher) => {
            ketcherRef.current = k
            ;(window as unknown as { ketcher: Ketcher }).ketcher = k
          }}
        />
      </main>
      <aside className="sidepanel">
        <section className="plan-section">
          <header>
            <h2>plan</h2>
            <button className="primary" onClick={handlePlan} disabled={planLoading}>
              {planLoading ? 'Planning…' : 'Plan synthesis'}
            </button>
          </header>

          {planError && <div className="error">{planError}</div>}

          {plan && (
            <div className="result">
              <div className="stats">
                <Stat label="Solved" value={plan.stats.is_solved ? 'yes' : 'no'} />
                <Stat label="Steps" value={String(plan.stats.number_of_steps)} />
                <Stat
                  label="In stock"
                  value={`${plan.stats.number_of_precursors_in_stock} / ${plan.stats.number_of_precursors}`}
                />
                <Stat label="Search" value={`${plan.stats.search_time.toFixed(1)}s`} />
              </div>

              <img
                className="route-image"
                src={`data:image/png;base64,${plan.top_route.image_png_b64}`}
                alt="Retrosynthesis route"
              />

              {plan.stats.precursors_in_stock && (
                <Block label="Building blocks (in stock)" body={plan.stats.precursors_in_stock} />
              )}
              {plan.stats.precursors_not_in_stock && (
                <Block label="Missing precursors" body={plan.stats.precursors_not_in_stock} />
              )}
            </div>
          )}
        </section>

        <section className="chat-section">
          <header>
            <h2>chat</h2>
          </header>

          <div className="messages">
            {messages.length === 0 && !streamingText && (
              <div className="muted small">
                Ask about the molecule, the route, or how to run a step. The chat sees your canvas and plan.
              </div>
            )}
            {messages.map((m, i) => (
              <Message key={i} role={m.role} content={m.content} />
            ))}
            {streamingText && <Message role="assistant" content={streamingText} streaming />}
            <div ref={messagesEndRef} />
          </div>

          {chatError && <div className="error">{chatError}</div>}

          <form className="chat-input" onSubmit={handleChatSubmit}>
            <textarea
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleChatSubmit(e as unknown as React.FormEvent)
                }
              }}
              placeholder={chatStreaming ? 'Thinking…' : 'Ask about this molecule or route'}
              disabled={chatStreaming}
              rows={2}
            />
            <button className="primary" type="submit" disabled={chatStreaming || !chatInput.trim()}>
              Send
            </button>
          </form>
        </section>
      </aside>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  )
}

function Block({ label, body }: { label: string; body: string }) {
  return (
    <div className="block">
      <div className="block-label">{label}</div>
      <code className="block-body">{body}</code>
    </div>
  )
}

function Message({ role, content, streaming }: { role: 'user' | 'assistant'; content: string; streaming?: boolean }) {
  return (
    <div className={`message message-${role}${streaming ? ' streaming' : ''}`}>
      <div className="message-role">{role}</div>
      <div className="message-content">{content}</div>
    </div>
  )
}

export default App
