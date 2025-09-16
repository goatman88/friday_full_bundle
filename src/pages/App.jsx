import { Link } from 'react-router-dom'

export default function App() {
  return (
    <main style={{ padding: 24, fontFamily: 'system-ui, sans-serif' }}>
      <h1>Friday Frontend</h1>
      <p>Welcome. Choose a page:</p>
      <ul>
        <li><Link to="/multi-uploader">Multi-file Upload + Progress + SSE</Link></li>
      </ul>
    </main>
  )
}
