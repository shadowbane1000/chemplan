import { Editor } from 'ketcher-react'
import { StandaloneStructServiceProvider } from 'ketcher-standalone'
import 'ketcher-react/dist/index.css'
import './App.css'

const structServiceProvider = new StandaloneStructServiceProvider()

function App() {
  return (
    <div className="app">
      <main className="canvas">
        <Editor
          staticResourcesUrl=""
          structServiceProvider={structServiceProvider}
          errorHandler={(message: string) => console.error('ketcher error:', message)}
        />
      </main>
      <aside className="sidepanel">
        <header>
          <h2>chat</h2>
          <p className="muted">canvas-aware chat lands next.</p>
        </header>
      </aside>
    </div>
  )
}

export default App
