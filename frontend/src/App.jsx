import { useState, useEffect, useMemo, useRef } from 'react'

const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '') || 'http://localhost:8000'

const FIELDS = [
  { k: 'S', label: 'Spot', min: 20, max: 200, step: 1, fmt: v => v.toFixed(0) },
  { k: 'K', label: 'Strike', min: 20, max: 200, step: 1, fmt: v => v.toFixed(0) },
  { k: 'T', label: 'Expiry (yrs)', min: 0.02, max: 3, step: 0.02, fmt: v => v.toFixed(2) },
  { k: 'r', label: 'Rate', min: 0, max: 0.15, step: 0.005, fmt: v => (v * 100).toFixed(1) + '%' },
  { k: 'sigma', label: 'Volatility', min: 0.05, max: 1, step: 0.01, fmt: v => (v * 100).toFixed(0) + '%' },
]
const GREEKS = ['delta', 'gamma', 'theta', 'vega', 'rho']

const fmt2 = v => (v != null && isFinite(v)) ? Number(v).toFixed(2) : '—'
const fmtGreek = v => (v != null && isFinite(v)) ? (Math.abs(v) < 1 ? Number(v).toFixed(4) : Number(v).toFixed(3)) : '—'
const fmtBps = v => (v != null && isFinite(v)) ? `${Number(v).toFixed(0)} bps` : ''

export default function App() {
  const [p, setP] = useState({ S: 100, K: 100, T: 1, r: 0.05, sigma: 0.2, option_type: 'call' })
  const [out, setOut] = useState(null)
  const [curve, setCurve] = useState(null)
  const [sel, setSel] = useState('delta')
  const [state, setState] = useState('idle')
  const timer = useRef()

  useEffect(() => {
    clearTimeout(timer.current)
    setState('loading')
    timer.current = setTimeout(async () => {
      try {
        const body = JSON.stringify(p)
        const opt = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body }
        const [price, greeks, quote, gc] = await Promise.all([
          fetch(`${API}/price`, opt).then(r => r.json()),
          fetch(`${API}/greeks`, opt).then(r => r.json()),
          fetch(`${API}/quote`, opt).then(r => r.json()),
          fetch(`${API}/greek-curve?greek=${sel}&points=70`, opt).then(r => r.json()),
        ])
        setOut({ price: price?.price, greeks, quote })
        setCurve(gc)
        setState('ok')
      } catch (e) {
        console.error('API error:', e)
        setState('error')
      }
    }, 250)
    return () => clearTimeout(timer.current)
  }, [p, sel])

  const set = (k, v) => setP(prev => ({ ...prev, [k]: v }))

  return (
    <div className="app">
      <header className="head">
        <div className="wordmark">THEO<span className="dot">.</span></div>
        <div className="tag">Black–Scholes pricing & Greeks · <b>live</b></div>
      </header>

      <div className="grid">
        <aside className="panel">
          <h3>Contract</h3>
          <div className="toggle">
            <button className={p.option_type === 'call' ? 'on call' : ''}
              onClick={() => set('option_type', 'call')}>Call</button>
            <button className={p.option_type === 'put' ? 'on put' : ''}
              onClick={() => set('option_type', 'put')}>Put</button>
          </div>
          {FIELDS.map(f => (
            <div className="field" key={f.k}>
              <div className="lab"><span>{f.label}</span><b>{f.fmt(p[f.k])}</b></div>
              <input type="range" min={f.min} max={f.max} step={f.step} value={p[f.k]}
                onChange={e => set(f.k, parseFloat(e.target.value))} />
            </div>
          ))}
        </aside>

        <main>
          <div className="panel" style={{ marginBottom: 20 }}>
            {state === 'error' && (
              <div className="empty err" style={{marginBottom:16}}>
                Can't reach the API at <code>{API}</code>.<br/>
                Check the VITE_API_URL env variable in Vercel settings.
              </div>
            )}
            <div className="theo-row">
              <div className="theo">{fmt2(out?.price)}</div>
              <div className="theo-lab">theoretical<br />value</div>
            </div>

            <div className="quote">
              <div className="bid"><div className="k">Bid</div>
                <div className="v">{fmt2(out?.quote?.bid)}</div></div>
              <div><div className="k">Mid / Theo</div>
                <div className="v">{fmt2(out?.quote?.theo)}</div>
                <div className="spread">{out?.quote?.spread != null ? `${fmt2(out.quote.spread)} wide` : ''}</div></div>
              <div className="ask"><div className="k">Ask</div>
                <div className="v">{fmt2(out?.quote?.ask)}</div>
                <div className="spread">{fmtBps(out?.quote?.spread_bps)}</div></div>
            </div>

            <div className="greeks">
              {GREEKS.map(g => (
                <div key={g} className={`cell ${sel === g ? 'sel' : ''}`} onClick={() => setSel(g)}>
                  <div className="name">{g}</div>
                  <div className="num">{fmtGreek(out?.greeks?.[g])}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="chart-head">
              <h3 style={{ margin: 0 }}>{sel} vs spot</h3>
              <div className="hint">click a Greek above to plot it · ◆ = current spot</div>
            </div>
            <Chart curve={curve} spot={p.S} state={state} />
          </div>

          <div className="foot">
            data from a FastAPI service over your Black–Scholes engine ·{' '}
            <a href={`${API}/docs`} target="_blank" rel="noreferrer">API docs ↗</a>
          </div>
        </main>
      </div>
    </div>
  )
}

function Chart({ curve, spot, state }) {
  const W = 760, H = 300, padL = 52, padR = 16, padT = 16, padB = 34

  const geom = useMemo(() => {
    if (!curve?.spot?.length || !curve?.value?.length) return null
    const xs = curve.spot, ys = curve.value
    if (!xs || !ys) return null
    const xmin = xs[0], xmax = xs[xs.length - 1]
    let ymin = Math.min(...ys), ymax = Math.max(...ys)
    if (ymin === ymax) { ymin -= 1; ymax += 1 }
    const pad = (ymax - ymin) * 0.08; ymin -= pad; ymax += pad
    const px = x => padL + (x - xmin) / (xmax - xmin) * (W - padL - padR)
    const py = y => H - padB - (y - ymin) / (ymax - ymin) * (H - padT - padB)
    const path = xs.map((x, i) => `${i ? 'L' : 'M'}${px(x).toFixed(1)} ${py(ys[i]).toFixed(1)}`).join(' ')
    const idx = xs.findIndex(x => x >= spot)
    const i = Math.max(0, idx < 0 ? xs.length - 1 : idx)
    let mv = ys[i]
    if (i > 0 && idx >= 0) { const t = (spot - xs[i-1])/(xs[i]-xs[i-1]); mv = ys[i-1]+t*(ys[i]-ys[i-1]) }
    return { px, py, path, xmin, xmax, ymin, ymax,
      mx: px(Math.min(Math.max(spot, xmin), xmax)),
      my: py(mv ?? ys[0]),
      zeroY: ymin < 0 && ymax > 0 ? py(0) : null }
  }, [curve, spot])

  if (state === 'error') return null
  if (!geom) return <div className="empty">{state === 'loading' ? 'computing…' : 'drag a slider to plot'}</div>

  const yticks = [geom.ymax, (geom.ymax + geom.ymin) / 2, geom.ymin]
  const xticks = [geom.xmin, (geom.xmin + geom.xmax) / 2, geom.xmax]

  function fmtTick(v) {
    const a = Math.abs(v)
    if (!isFinite(v)) return ''
    if (a >= 1000) return (v/1000).toFixed(1)+'k'
    if (a < 1 && a > 0) return v.toFixed(3)
    return v.toFixed(1)
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" preserveAspectRatio="xMidYMid meet">
      {geom.zeroY && <line className="axis" x1={padL} x2={W-padR} y1={geom.zeroY} y2={geom.zeroY}/>}
      {yticks.map((t,i) => (
        <g key={i}>
          <line className="gridln" x1={padL} x2={W-padR} y1={geom.py(t)} y2={geom.py(t)}/>
          <text className="axlab" x={padL-8} y={geom.py(t)+3} textAnchor="end">{fmtTick(t)}</text>
        </g>
      ))}
      {xticks.map((t,i) => (
        <text key={i} className="axlab" x={geom.px(t)} y={H-12} textAnchor="middle">{Number(t).toFixed(0)}</text>
      ))}
      <line className="axis" x1={padL} x2={padL} y1={padT} y2={H-padB}/>
      <line className="marker" x1={geom.mx} x2={geom.mx} y1={padT} y2={H-padB}/>
      <path className="curve" d={geom.path}/>
      <circle className="mark-dot" cx={geom.mx} cy={geom.my} r="4.5"/>
    </svg>
  )
}
