import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import { useStore } from '../../store/useStore'
import { useGraph } from '../../hooks/useGraph'
import { getEntityColor } from '../../utils/formatters'
import styles from './GraphView.module.css'

function nodeR(d) { return 7 + Math.min(18, (d.weight || 1) * 0.4) }

export default function GraphView() {
  const { setSelectedEventId } = useStore()
  const [minConf, setMinConf] = useState(0.4)
  const { graph, loading } = useGraph({ minConfidence: minConf })
  const svgRef = useRef()

  useEffect(() => {
    if (!graph || !svgRef.current) return
    const el = svgRef.current
    const W = el.clientWidth
    const H = el.clientHeight

    d3.select(el).selectAll('*').remove()
    const svg = d3.select(el)
    const g   = svg.append('g')

    svg.call(d3.zoom().scaleExtent([0.15, 5]).on('zoom', (e) => g.attr('transform', e.transform)))

    const nodes = graph.nodes.map((n) => ({ ...n }))
    const edges = graph.edges.map((e) => ({ ...e }))

    const sim = d3.forceSimulation(nodes)
      .force('link',      d3.forceLink(edges).id((d) => d.id).distance(130).strength(0.4))
      .force('charge',    d3.forceManyBody().strength(-350))
      .force('center',    d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide().radius((d) => nodeR(d) + 6))

    const link = g.append('g').selectAll('line').data(edges).join('line')
      .attr('stroke', '#ffffff12')
      .attr('stroke-width', (d) => Math.max(0.5, (d.confidence || 0) * 2.5))
      .attr('stroke-dasharray', (d) => d.type === 'temporal_proximity' ? '4 3' : null)

    link.append('title').text((d) => `${d.type}\n${d.explanation || ''}`)

    const node = g.append('g').selectAll('g').data(nodes).join('g')
      .attr('cursor', 'pointer')
      .call(d3.drag()
        .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y })
        .on('end',   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null }))
      .on('click', (_, d) => setSelectedEventId(d.id))

    node.append('circle')
      .attr('r', nodeR)
      .attr('fill',         (d) => getEntityColor(d.type) + 'bb')
      .attr('stroke',       (d) => getEntityColor(d.type))
      .attr('stroke-width', 1.5)

    node.append('text')
      .text((d) => (d.label || '').substring(0, 20))
      .attr('text-anchor', 'middle')
      .attr('y', (d) => nodeR(d) + 13)
      .attr('fill', '#9ba3b8')
      .attr('font-size', '10px')
      .attr('font-family', 'IBM Plex Mono, monospace')
      .attr('pointer-events', 'none')

    node.append('title').text((d) => `${d.label}\n${d.type}\nFrequency: ${d.weight || 0}`)

    sim.on('tick', () => {
      link.attr('x1', (d) => d.source.x).attr('y1', (d) => d.source.y)
          .attr('x2', (d) => d.target.x).attr('y2', (d) => d.target.y)
      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
    })

    return () => sim.stop()
  }, [graph, setSelectedEventId])

  return (
    <div className={styles.wrap}>
      {loading && <div className={styles.loading}><div className="spinner" /><span>Building graph…</span></div>}
      <svg ref={svgRef} className={styles.svg} />

      <div className={styles.controls}>
        <label className={styles.confLabel}>
          Min confidence
          <input type="range" min={0} max={0.9} step={0.05} value={minConf}
            onChange={(e) => setMinConf(Number(e.target.value))} className={styles.slider} />
          <span className={styles.confVal}>{Math.round(minConf * 100)}%</span>
        </label>
      </div>

      <div className={styles.legend}>
        {[['politician','Politician'],['organization','Organization'],['institution','Institution'],['country','Country'],['topic','Topic']].map(([type, label]) => (
          <div key={type} className={styles.legendRow}>
            <div className={styles.legendDot} style={{ background: getEntityColor(type) }} />
            {label}
          </div>
        ))}
      </div>

      <div className={styles.notice}>Edges = observable co-occurrence only.<br />No causal claims are implied.</div>

      {!graph && !loading && (
        <div className="empty-state" style={{ position: 'absolute', inset: 0 }}>
          <div className="empty-icon">◎</div>
          <div className="empty-label">No graph data yet.<br />Ingest GDELT data to populate the graph.</div>
        </div>
      )}
    </div>
  )
}
