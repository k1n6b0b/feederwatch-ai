import { Routes, Route, Navigate } from 'react-router-dom'
import Shell from './components/Shell'
import Feed from './pages/Feed'
import Gallery from './pages/Gallery'
import SpeciesDetail from './pages/SpeciesDetail'
import Daily from './pages/Daily'
import ConnectionStatus from './pages/ConnectionStatus'
import Recap from './pages/Recap'

export default function App() {
  return (
    <Routes>
      {/* Full-viewport pages — rendered outside Shell for complete layout control */}
      {/* recap: accessible via Daily page "Month Recap" button, not in nav */}
      <Route path="/recap/:year/:month" element={<Recap />} />

      {/* Shell-wrapped pages */}
      <Route path="/*" element={
        <Shell>
          <Routes>
            <Route path="/" element={<Feed />} />
            <Route path="/gallery" element={<Gallery />} />
            <Route path="/gallery/:scientificName" element={<SpeciesDetail />} />
            <Route path="/daily" element={<Daily />} />
            {/* connection-status: accessible only via StatusChip, not in nav */}
            <Route path="/connection-status" element={<ConnectionStatus />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Shell>
      } />
    </Routes>
  )
}
