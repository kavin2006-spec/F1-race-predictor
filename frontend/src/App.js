import { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";

const API = "http://localhost:8000";

const TEAM_COLORS = {
  "Mercedes":          "#00D2BE",
  "Red Bull Racing":   "#3671C6",
  "Ferrari":           "#E8002D",
  "McLaren":           "#FF8000",
  "Aston Martin":      "#229971",
  "Alpine":            "#FF87BC",
  "Williams":          "#64C4FF",
  "Racing Bulls":      "#6692FF",
  "Haas F1 Team":      "#B6BABD",
  "Kick Sauber":       "#52E252",
  "Audi":              "#E5E5E5",
  "Cadillac":          "#C8A84B",
};

const DRIVER_NAMES = {
  VER:"Max Verstappen", NOR:"Lando Norris", LEC:"Charles Leclerc",
  HAM:"Lewis Hamilton", RUS:"George Russell", ANT:"Kimi Antonelli",
  PIA:"Oscar Piastri",  SAI:"Carlos Sainz",  ALB:"Alexander Albon",
  GAS:"Pierre Gasly",   OCO:"Esteban Ocon",  BEA:"Oliver Bearman",
  STR:"Lance Stroll",   ALO:"Fernando Alonso",LAW:"Liam Lawson",
  HAD:"Isack Hadjar",   LIN:"Arvid Lindblad", COL:"Franco Colapinto",
  HUL:"Nico Hülkenberg",BOR:"Gabriel Bortoleto",PER:"Sergio Pérez",
  BOT:"Valtteri Bottas",TSU:"Yuki Tsunoda",
};

// Full 2026 calendar — Bahrain and Saudi cancelled due to conflict
const CALENDAR_2026 = [
  { round:1,  name:"Australian GP",  date:"2026-03-08T05:00:00Z", done:true  },
  { round:2,  name:"Chinese GP",     date:"2026-03-15T07:00:00Z", done:true  },
  { round:3,  name:"Japanese GP",    date:"2026-03-29T05:00:00Z", done:true },
  { round:4,  name:"Miami GP",       date:"2026-05-03T19:00:00Z", done:false },
  { round:5,  name:"Canadian GP",    date:"2026-05-24T18:00:00Z", done:false },
  { round:6,  name:"Monaco GP",      date:"2026-06-07T13:00:00Z", done:false },
  { round:7,  name:"Barcelona GP",   date:"2026-06-14T13:00:00Z", done:false },
  { round:8,  name:"Austrian GP",    date:"2026-06-28T13:00:00Z", done:false },
  { round:9,  name:"British GP",     date:"2026-07-05T14:00:00Z", done:false },
  { round:10, name:"Belgian GP",     date:"2026-07-19T13:00:00Z", done:false },
  { round:11, name:"Hungarian GP",   date:"2026-07-26T13:00:00Z", done:false },
  { round:12, name:"Dutch GP",       date:"2026-08-23T13:00:00Z", done:false },
  { round:13, name:"Italian GP",     date:"2026-09-06T13:00:00Z", done:false },
  { round:14, name:"Madrid GP",      date:"2026-09-13T13:00:00Z", done:false },
  { round:15, name:"Azerbaijan GP",  date:"2026-09-26T11:00:00Z", done:false },
  { round:16, name:"Singapore GP",   date:"2026-10-11T12:00:00Z", done:false },
  { round:17, name:"US GP",          date:"2026-10-25T19:00:00Z", done:false },
  { round:18, name:"Mexico City GP", date:"2026-11-01T20:00:00Z", done:false },
  { round:19, name:"São Paulo GP",   date:"2026-11-08T17:00:00Z", done:false },
  { round:20, name:"Las Vegas GP",   date:"2026-11-21T06:00:00Z", done:false },
  { round:21, name:"Qatar GP",       date:"2026-11-29T13:00:00Z", done:false },
  { round:22, name:"Abu Dhabi GP",   date:"2026-12-06T13:00:00Z", done:false },
];

function getNextRace() {
  const now = new Date();
  return CALENDAR_2026.find(r => new Date(r.date) > now) || CALENDAR_2026[CALENDAR_2026.length - 1];
}

function useCountdown(targetDate) {
  const [time, setTime] = useState({});
  useEffect(() => {
    const calc = () => {
      const diff = new Date(targetDate) - new Date();
      if (diff <= 0) return setTime({ d:0, h:0, m:0, s:0 });
      setTime({
        d: Math.floor(diff / 86400000),
        h: Math.floor((diff % 86400000) / 3600000),
        m: Math.floor((diff % 3600000) / 60000),
        s: Math.floor((diff % 60000) / 1000),
      });
    };
    calc();
    const id = setInterval(calc, 1000);
    return () => clearInterval(id);
  }, [targetDate]);
  return time;
}

// ── ChatBot bubble ──────────────────────────────────────────────
function ChatBot({ predictions, track, year }) {
  const [open, setOpen]       = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput]     = useState("");
  const [loading, setLoading] = useState(false);
  const endRef                = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior:"smooth" });
  }, [messages]);

  useEffect(() => {
    if (open && messages.length === 0) {
      setMessages([{
      role: "assistant", 
      content: "RACE ENGINEER ONLINE. I'm your AI Analyst for the upcoming(and finished) Grand Prixs. I have the full predicted grid loaded — ask me anything. Who's going to win? Why is a driver starting so far back? What does the data say about a specific matchup? I'm here for it."
      }]);
    }
  }, [open]);

  async function send() {
    if (!input.trim() || loading) return;
    const msg = { role:"user", content: input };
    const next = [...messages, msg];
    setMessages(next);
    setInput("");
    setLoading(true);
    const r = await axios.post(`${API}/chat`, { track, year, predictions, messages: next });
    setMessages([...next, { role:"assistant", content: r.data.reply }]);
    setLoading(false);
  }

  return (
    <div className="chatbot-wrap">
      {open && (
        <div className="chatbot-panel">
          <div className="chatbot-header">
            <span>AI ANALYST</span>
            <button onClick={() => setOpen(false)}>✕</button>
          </div>
          <div className="chatbot-messages">
            {messages.length === 0 && loading && (
              <div className="cb-msg assistant"><div className="typing"><span/><span/><span/></div></div>
            )}
            {messages.map((m,i) => (
              <div key={i} className={`cb-msg ${m.role}`}>
                <div className="cb-label">{m.role === "assistant" ? "ANALYST" : "YOU"}</div>
                <div className="cb-content">{m.content}</div>
              </div>
            ))}
            {loading && messages.length > 0 && (
              <div className="cb-msg assistant"><div className="typing"><span/><span/><span/></div></div>
            )}
            <div ref={endRef}/>
          </div>
          <div className="chatbot-input">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && send()}
              placeholder="Ask about the predictions..."
              disabled={loading}
            />
            <button onClick={send} disabled={loading || !input.trim()}>→</button>
          </div>
        </div>
      )}
      <button className="chatbot-fab" onClick={() => setOpen(o => !o)}>
        {open ? "✕" : "?"}
        {!open && <span className="fab-ping"/>}
      </button>
    </div>
  );
}

// ── Hero section ────────────────────────────────────────────────
function Hero({ onScrollDown }) {
  const next  = getNextRace();
  const time  = useCountdown(next.date);

  return (
    <section className="hero">
      <div className="grain"/>
      <div className="scanlines"/>
      <div className="hero-inner">
        <div className="hero-eyebrow">FORMULA 1 · 2026 SEASON · ROUND {next.round}</div>
        <h1 className="hero-title">{next.name.toUpperCase()}</h1>
        <div className="countdown">
          {[["DAYS",time.d],["HRS",time.h],["MIN",time.m],["SEC",time.s]].map(([l,v]) => (
            <div key={l} className="countdown-unit">
              <span className="countdown-num">{String(v ?? 0).padStart(2,"0")}</span>
              <span className="countdown-label">{l}</span>
            </div>
          ))}
        </div>
        <button className="scroll-cue" onClick={onScrollDown}>
          PREDICTIONS <span className="arrow-down">↓</span>
        </button>
      </div>
    </section>
  );
}

// ── Predictions section ─────────────────────────────────────────

function Predictions({ predRef }) {
  const next = getNextRace();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);



useEffect(() => {
    const tryLoad = async () => {
      try {
        // Always call /next-race — backend figures out what to show
        const r = await axios.get(`${API}/next-race`);
        setData(r.data);
      } catch (e) {
        console.error("Could not load next race prediction", e);
      }
      setLoading(false);
    };
    tryLoad();
  }, []);

return (
  <section className="predictions-section" ref={predRef}>
    <div className="grain"/>
    <div className="scanlines"/>
    <div className="section-topbar">
      <span className="section-label">PREDICTED GRID</span>
      <span className="section-meta">
        {data ? `${data.track} · ${data.year}` : "Loading..."}
      </span>
      <span className="section-stats">MAE 1.80 · 81.9% within P3</span>
    </div>

    {loading && <div className="loading-state">COMPUTING PREDICTIONS...</div>}

    {data && (
      <div className="grid-wrap">
        <div className="prediction-disclaimer">
          <span className="disclaimer-icon">⚠</span>
          <span>
            {data.grid_source === "qualifying"
              ? "POST-QUALIFYING — grid positions from actual qualifying results."
              : "PRE-QUALIFYING — grid positions estimated from recent form. Updates after qualifying."}
          </span>
        </div>

        <div className="grid-cols-header">
          <span>POS</span>
          <span>DRIVER</span>
          <span>TEAM</span>
          <span>GRID</span>
          <span>ΔPOS</span>
        </div>

        {data?.predictions?.map((p, i) => (
          <div
            key={p.driver}
            className="grid-row"
            style={{
              "--team-color": TEAM_COLORS[p.team] || "#666",
              animationDelay: `${i * 30}ms`
            }}
          >
            <span className="g-pos">P{Math.round(p.predicted_position)}</span>
            <span className="g-driver">
              <span className="g-code">{p.driver}</span>
              <span className="g-name">{DRIVER_NAMES[p.driver] || ""}</span>
            </span>
            <span className="g-team" style={{color: TEAM_COLORS[p.team] || "#aaa"}}>
              {p.team}
            </span>
            <span className="g-grid">P{Math.round(p.grid_pos)}</span>
            <span className={`g-delta ${p.predicted_delta > 0 ? "gain":"loss"}`}>
              {p.predicted_delta > 0 ? `+${p.predicted_delta}` : p.predicted_delta}
            </span>
          </div>
        ))}
      </div>
    )}

    {data && (
      <ChatBot
        predictions={data.predictions}
        track={data.track}
        year={data.year}
      />
    )}
  </section>
);
}

// ── Archive section ─────────────────────────────────────────────
function Archive({ archiveRef }) {
  const done = CALENDAR_2026.filter(r => r.done);
  const [selected, setSelected] = useState(null);
  const [data, setData] = useState(null);
  useEffect(() => {
    if (done.length > 0) setSelected(done[done.length - 1]);
  }, []);
  
  useEffect(() => {
    if (!selected) return;
    setData(null);

    axios.get(`${API}/archive/2026/${selected.round}`)
      .then(r => setData(r.data))
      .catch(() => {});
  }, [selected]);

  return (
    <section className="archive-section" ref={archiveRef}>
      <div className="grain"/>
      <div className="scanlines"/>

      <div className="section-topbar">
        <span className="section-label">RACE ARCHIVE · 2026</span>
        <span className="section-meta">PREDICTED vs ACTUAL</span>
      </div>

      <div className="archive-race-pills">
        {done.map(r => (
          <button
            key={r.round}
            className={`race-pill ${selected?.round === r.round ? "active":""}`}
            onClick={() => setSelected(r)}
          >
            {r.name.replace(" GP","").replace(" Grand Prix","")}
          </button>
        ))}
      </div>

      {data && (
        <div className="archive-grid-wrap">

          {/* Dynamic note */}
          <div className="archive-note">
            {data.has_actual
              ? `Showing predicted vs actual results for ${data.track}.`
              : `Actual results not yet stored — showing model predictions for ${data.track}.`}
          </div>

          {/* Header */}
          <div className="grid-cols-header">
            <span>POS</span>
            <span>DRIVER</span>
            <span>TEAM</span>
            <span>GRID</span>
            <span>ΔPOS</span>
            <span>ACTUAL</span>
            <span>ERROR</span>
          </div>

          {/* Rows */}
          {data.predictions.map((p, i) => (
            <div
              key={p.driver}
              className="grid-row"
              style={{
                "--team-color": TEAM_COLORS[p.team] || "#666",
                animationDelay: `${i * 30}ms`
              }}
            >
              <span className="g-pos">P{Math.round(p.predicted_position)}</span>

              <span className="g-driver">
                <span className="g-code">{p.driver}</span>
                <span className="g-name">{DRIVER_NAMES[p.driver] || ""}</span>
              </span>

              <span className="g-team" style={{color: TEAM_COLORS[p.team] || "#aaa"}}>
                {p.team}
              </span>

              <span className="g-grid">P{Math.round(p.grid_pos)}</span>

              <span className={`g-delta ${p.predicted_delta > 0 ? "gain":"loss"}`}>
                {p.predicted_delta > 0 ? `+${p.predicted_delta}` : p.predicted_delta}
              </span>

              {data.has_actual && (
                <>
                  <span className="g-actual">
                    {p.actual_position ? `P${Math.round(p.actual_position)}` : "—"}
                  </span>

                  <span className={`g-error ${
                    p.actual_position
                    ? Math.abs(p.actual_position - p.predicted_position) <= 2
                    ? "accurate" : "inaccurate"
                    : ""
                  }`}>
                    {p.actual_position 
                     ? Math.abs(Math.round(p.actual_position) - Math.round(p.predicted_position))
                     : "-"
                    }
                  </span>
                </>
              )}
            </div>
          ))}

          <ChatBot
            predictions={data.predictions}
            track={data.track}
            year={data.year}
          />
        </div>
      )}
    </section>
  );
}

// ── App shell ───────────────────────────────────────────────────
export default function App() {
  const predRef    = useRef(null);
  const archiveRef = useRef(null);

  function scrollTo(ref) {
    ref.current?.scrollIntoView({ behavior:"smooth" });
  }

  return (
    <div className="app">
      <nav className="topnav">
        <div className="nav-logo">
          <span className="nav-f1">F1</span>
          <span className="nav-title">PREDICTOR</span>
        </div>
        <div className="nav-links">
          <button onClick={() => window.scrollTo({top:0,behavior:"smooth"})}>HOME</button>
          <button onClick={() => scrollTo(predRef)}>PREDICTIONS</button>
          <button onClick={() => scrollTo(archiveRef)}>ARCHIVE</button>
        </div>
      </nav>

      <Hero onScrollDown={() => scrollTo(predRef)} />

      <div className="scroll-cue-between" onClick={() => scrollTo(predRef)}>
        PREDICTIONS <span>↓</span>
      </div>

      <Predictions predRef={predRef} />

      <div className="scroll-cue-between" onClick={() => scrollTo(archiveRef)}>
        PREVIOUS PREDICTIONS <span>↓</span>
      </div>

      <Archive archiveRef={archiveRef} />

      <footer className="footer">
        <span>F1 PREDICTOR · 2026</span>
        <span>MODEL MAE 1.80 · BUILT WITH FASTF1 + SKLEARN + phi3:mini</span>
      </footer>
    </div>
  );
} 
