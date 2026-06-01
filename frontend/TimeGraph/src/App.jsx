import { useStore } from './store/useStore'
import TopBar from './components/layout/TopBar'
import Sidebar from './components/layout/Sidebar'
import DetailPanel from './components/layout/DetailPanel'
import Timeline from './components/timeline/Timeline'
import GraphView from './components/graph/GraphView'
import EntitiesView from './components/entities/EntitiesView'
import IngestView from './components/layout/IngestView'

export default function App() {
  const { activeView } = useStore()
  const isThreeCol = activeView === 'timeline' || activeView === 'graph'

  return (
    <div className="shell">
      <TopBar />
      {isThreeCol ? (
        <div className="main-grid">
          <Sidebar />
          <main style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            {activeView === 'timeline' && <Timeline />}
            {activeView === 'graph'    && <GraphView />}
          </main>
          <DetailPanel />
        </div>
      ) : (
        <div style={{ height: '100%', overflow: 'hidden' }}>
          {activeView === 'entities' && <EntitiesView />}
          {activeView === 'ingest'   && <IngestView />}
        </div>
      )}
    </div>
  )
}
