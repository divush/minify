import { useEffect, useState } from 'react'
import { getHealth, type HealthResponse } from './api/client'
import './App.css'

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getHealth().then(setHealth).catch((err: Error) => setError(err.message))
  }, [])

  return (
    <section id="center">
      <h1>Minify</h1>
      {error && <p>Backend unreachable: {error}</p>}
      {!error && !health && <p>Checking backend...</p>}
      {health && (
        <p>
          Backend status: {health.status} ({health.environment})
        </p>
      )}
    </section>
  )
}

export default App
