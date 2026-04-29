/** Friction Map — main React app */
const { useState, useMemo, useEffect, useRef } = React;

const TWEAK_DEFAULTS = {
  palette: "warm",
  accent: "#c4502a",
  excerptDensity: "collapsed",
};

// Friction palettes — 6 stops each, light + dark variants.
const PALETTES = {
  warm: {
    light: ["oklch(94% 0.025 85)", "oklch(90% 0.075 85)", "oklch(82% 0.13 75)", "oklch(72% 0.165 55)", "oklch(60% 0.19 35)", "oklch(48% 0.22 25)"],
    dark:  ["oklch(35% 0.04 80)",  "oklch(45% 0.075 80)", "oklch(55% 0.12 70)", "oklch(62% 0.16 55)",  "oklch(58% 0.20 35)", "oklch(52% 0.22 25)"],
  },
  cool: {
    light: ["oklch(95% 0.02 240)", "oklch(88% 0.06 240)", "oklch(78% 0.11 230)", "oklch(68% 0.15 215)", "oklch(56% 0.18 200)", "oklch(44% 0.20 195)"],
    dark:  ["oklch(35% 0.04 240)", "oklch(45% 0.07 235)", "oklch(55% 0.11 225)", "oklch(62% 0.15 215)", "oklch(58% 0.18 200)", "oklch(52% 0.20 195)"],
  },
  viridis: {
    light: ["oklch(95% 0.04 110)", "oklch(82% 0.13 130)", "oklch(70% 0.15 165)", "oklch(58% 0.13 200)", "oklch(46% 0.13 250)", "oklch(34% 0.13 290)"],
    dark:  ["oklch(38% 0.05 110)", "oklch(50% 0.10 130)", "oklch(60% 0.13 165)", "oklch(62% 0.13 200)", "oklch(54% 0.14 250)", "oklch(45% 0.15 290)"],
  },
  diverging: {
    light: ["oklch(70% 0.12 240)", "oklch(85% 0.06 230)", "oklch(94% 0.02 90)",  "oklch(86% 0.10 70)",  "oklch(70% 0.16 40)",  "oklch(50% 0.21 25)"],
    dark:  ["oklch(50% 0.13 240)", "oklch(45% 0.08 230)", "oklch(40% 0.02 90)",  "oklch(50% 0.10 70)",  "oklch(58% 0.17 40)",  "oklch(52% 0.21 25)"],
  },
  mono: {
    light: ["oklch(95% 0.005 80)", "oklch(85% 0.008 80)", "oklch(70% 0.010 80)", "oklch(55% 0.015 70)", "oklch(40% 0.020 60)", "oklch(25% 0.025 50)"],
    dark:  ["oklch(28% 0.008 80)", "oklch(38% 0.010 80)", "oklch(50% 0.012 70)", "oklch(62% 0.015 60)", "oklch(75% 0.018 50)", "oklch(88% 0.020 40)"],
  },
};

function applyPalette(name, theme) {
  const stops = PALETTES[name] ? PALETTES[name][theme] : PALETTES.warm[theme];
  const root = document.documentElement;
  stops.forEach((c, i) => root.style.setProperty(`--f${i}`, c));
}

function applyAccent(hex) {
  document.documentElement.style.setProperty("--accent", hex);
}

// Map a normalized score [0..1] to a CSS variable color via 6 stops.
function frictionColor(t) {
  const idx = Math.min(5, Math.max(0, Math.floor(t * 6)));
  return `var(--f${idx})`;
}

// Recompute highlight offsets by string-matching the marker substring.
// This avoids drift between data and rendered text.
function fixHighlights(text, highlights) {
  if (!highlights || highlights.length === 0) return [];
  const out = [];
  let cursor = 0;
  for (const h of highlights) {
    const wanted = (h.marker || "").trim();
    if (!wanted) continue;
    const re = new RegExp(`\\b${wanted.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
    const slice = text.slice(cursor);
    const m = slice.match(re);
    if (m && m.index != null) {
      const start = cursor + m.index;
      out.push({ start, end: start + m[0].length, marker: m[0] });
      cursor = start + m[0].length;
    }
  }
  return out;
}

// Trim an excerpt to the marker-bearing sentences (+1 leading, +1 trailing).
function condenseExcerpt(text, highlights) {
  if (!highlights || highlights.length === 0) {
    // No markers — show first 2 sentences.
    const sentences = splitSentences(text);
    return { text: sentences.slice(0, 2).join(" ").trim(), highlights: [], truncated: sentences.length > 2 };
  }
  const sentences = splitSentences(text);
  const offsets = sentenceOffsets(text, sentences);
  const keep = new Set();
  for (const h of highlights) {
    for (let i = 0; i < offsets.length; i++) {
      const [s, e] = offsets[i];
      if (h.start >= s && h.start < e) {
        keep.add(i);
        if (i > 0) keep.add(i - 1);
        break;
      }
    }
  }
  if (keep.size === 0) keep.add(0);
  const idxs = [...keep].sort((a, b) => a - b);
  // Build condensed text — gaps shown as ellipsis.
  let condensed = "";
  let newHighlights = [];
  let prevIdx = -2;
  for (const i of idxs) {
    if (prevIdx >= 0 && i > prevIdx + 1) condensed += " […] ";
    else if (condensed.length > 0) condensed += " ";
    const sentenceText = sentences[i];
    const sentenceStart = offsets[i][0];
    const condStart = condensed.length;
    condensed += sentenceText;
    // Re-map highlights that fall in this sentence.
    for (const h of highlights) {
      if (h.start >= sentenceStart && h.start < sentenceStart + sentenceText.length) {
        const newStart = condStart + (h.start - sentenceStart);
        const newEnd = newStart + (h.end - h.start);
        newHighlights.push({ start: newStart, end: newEnd, marker: h.marker });
      }
    }
    prevIdx = i;
  }
  const truncated = idxs.length < sentences.length;
  return { text: condensed.trim(), highlights: newHighlights, truncated };
}

function splitSentences(text) {
  // Simple splitter: break on . ! ? followed by space + capital. Keeps punctuation.
  const out = [];
  let buf = "";
  for (let i = 0; i < text.length; i++) {
    buf += text[i];
    if (/[.!?]/.test(text[i])) {
      const next = text[i + 1];
      const after = text[i + 2];
      if (!next || /\s/.test(next)) {
        if (!after || /[A-Z\n]/.test(after) || (next === "\n")) {
          out.push(buf.trim());
          buf = "";
        }
      }
    }
  }
  if (buf.trim()) out.push(buf.trim());
  return out.filter(Boolean);
}

function sentenceOffsets(text, sentences) {
  const out = [];
  let cursor = 0;
  for (const s of sentences) {
    const idx = text.indexOf(s, cursor);
    if (idx >= 0) { out.push([idx, idx + s.length]); cursor = idx + s.length; }
    else out.push([cursor, cursor + s.length]);
  }
  return out;
}

// Squarified treemap (lightweight, no d3 dep needed).
function squarify(items, x, y, w, h) {
  // items: [{value, ...}], returns same with {x,y,w,h} added.
  const total = items.reduce((s, it) => s + it.value, 0);
  if (total <= 0 || items.length === 0) return [];
  const result = [];
  let rect = { x, y, w, h };
  let i = 0;
  while (i < items.length) {
    const remaining = items.slice(i);
    const remTotal = remaining.reduce((s, it) => s + it.value, 0);
    const short = Math.min(rect.w, rect.h);
    const row = [];
    let bestRatio = Infinity;
    for (let k = 0; k < remaining.length; k++) {
      const candidate = remaining.slice(0, k + 1);
      const sum = candidate.reduce((s, it) => s + it.value, 0);
      const area = (sum / remTotal) * (rect.w * rect.h);
      const rowLen = area / short;
      let worst = 0;
      for (const it of candidate) {
        const itArea = (it.value / remTotal) * (rect.w * rect.h);
        const itShort = itArea / rowLen;
        worst = Math.max(worst, Math.max(rowLen / itShort, itShort / rowLen));
      }
      if (worst < bestRatio) { bestRatio = worst; row.push(candidate[k]); }
      else break;
    }
    if (row.length === 0) row.push(remaining[0]);
    const rowSum = row.reduce((s, it) => s + it.value, 0);
    const rowArea = (rowSum / remTotal) * (rect.w * rect.h);
    const rowLen = rowArea / short;
    let cursor = 0;
    if (rect.w >= rect.h) {
      // horizontal slab on left
      for (const it of row) {
        const itArea = (it.value / remTotal) * (rect.w * rect.h);
        const itH = itArea / rowLen;
        result.push({ ...it, x: rect.x, y: rect.y + cursor, w: rowLen, h: itH });
        cursor += itH;
      }
      rect = { x: rect.x + rowLen, y: rect.y, w: rect.w - rowLen, h: rect.h };
    } else {
      for (const it of row) {
        const itArea = (it.value / remTotal) * (rect.w * rect.h);
        const itW = itArea / rowLen;
        result.push({ ...it, x: rect.x + cursor, y: rect.y, w: itW, h: rowLen });
        cursor += itW;
      }
      rect = { x: rect.x, y: rect.y + rowLen, w: rect.w, h: rect.h - rowLen };
    }
    i += row.length;
  }
  return result;
}

// Trim an absolute path to project-relative by stripping everything up
// through `/<codebaseName>/`. Returns the original path if the codebase
// segment isn't present (e.g. files under ~/.claude/ touched in a session).
function relativePath(path, codebaseName) {
  if (!codebaseName) return path;
  const marker = `/${codebaseName}/`;
  const idx = path.indexOf(marker);
  if (idx < 0) return path;
  return path.slice(idx + marker.length);
}

function fmtNum(n) {
  if (n == null) return "–";
  if (Math.abs(n) >= 1) return Number(n).toFixed(2);
  return Number(n).toFixed(3);
}

// Apply highlights to text → array of React nodes
function renderExcerptText(text, highlights) {
  if (!highlights || highlights.length === 0) return text;
  const sorted = [...highlights].sort((a, b) => a.start - b.start);
  const out = [];
  let pos = 0;
  sorted.forEach((h, i) => {
    if (h.start > pos) out.push(text.slice(pos, h.start));
    out.push(<span key={i} className="marker">{text.slice(h.start, h.end)}</span>);
    pos = h.end;
  });
  if (pos < text.length) out.push(text.slice(pos));
  return out;
}

function Header({ data, theme, setTheme }) {
  return (
    <header className="header">
      <div className="brand">friction<span className="dot">·</span>map</div>
      <div className="stats">
        <span><strong>{data.meta.name}</strong></span>
        <span><strong>{data.meta.session_count}</strong> sessions</span>
        <span><strong>{data.meta.file_count}</strong> files</span>
        <span><strong>{data.meta.thinking_block_count.toLocaleString()}</strong> thinking blocks</span>
      </div>
      <div className="header-right">
        <button
          className="icon-btn"
          aria-label="Toggle theme"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/></svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 13A9 9 0 0 1 11 3a7 7 0 1 0 10 10z"/></svg>
          )}
        </button>
      </div>
    </header>
  );
}

function ScoreBars({ components }) {
  const rows = [
    ["markers", components.markers],
    ["block length", components.block_length_words],
    ["question rate", components.question_rate_per_100w],
    ["tool coupling", components.tool_use_coupling],
    ["reread bursts", components.reread_bursts],
    ["edit churn", components.edit_churn],
  ];
  const max = Math.max(...rows.map(([, c]) => Math.abs(c.contribution)), 0.001);
  return (
    <div className="score-bars">
      {rows.map(([lbl, c]) => {
        const w = (Math.abs(c.contribution) / max) * 100;
        return (
          <div className="score-bar" key={lbl}>
            <div className="lbl">{lbl}</div>
            <div className="track">
              <div className={`fill ${c.contribution < 0 ? "neg" : ""}`} style={{ width: `${w}%` }} />
            </div>
            <div className="val">{c.contribution >= 0 ? "+" : ""}{fmtNum(c.contribution)}</div>
          </div>
        );
      })}
    </div>
  );
}

function ExcerptCard({ excerpt, currentPath, onJumpFile, density }) {
  const [expanded, setExpanded] = useState(density === "expanded");
  useEffect(() => { setExpanded(density === "expanded"); }, [density]);
  const fixedHighlights = useMemo(
    () => fixHighlights(excerpt.text, excerpt.highlights),
    [excerpt]
  );
  const condensed = useMemo(
    () => condenseExcerpt(excerpt.text, fixedHighlights),
    [excerpt, fixedHighlights]
  );

  const otherFiles = (excerpt.attribution.file_paths || []).filter(p => p !== currentPath);
  const tier = excerpt.attribution.tier;
  const isExact = tier === "exact_path";
  const tierLabel = null;

  const showFull = expanded;
  const renderText = showFull ? excerpt.text : condensed.text;
  const renderHL = showFull ? fixedHighlights : condensed.highlights;
  const canCollapse = true;

  // Compact tooltip for hidden meta details.
  const metaTip =
    `block ${excerpt.block_index + 1} of ${excerpt.block_total} in session\n` +
    `${excerpt.block_length_words} words` +
    (excerpt.cluster_count > 1 ? `\ncluster ${excerpt.cluster_index + 1} of ${excerpt.cluster_count}` : "") +
    `\nattribution: ${isExact ? "exact path match" : tierLabel}`;

  return (
    <div className={`excerpt ${expanded ? "expanded" : "collapsed"}`}>
      <div
        className="excerpt-meta"
        title={metaTip}
        onClick={() => setExpanded(!expanded)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setExpanded(!expanded); } }}
      >
        <span className="caret">{expanded ? "▾" : "▸"}</span>
        <span className="sid">{excerpt.session_id_short}</span>
        {(window.SESSION_TITLES && window.SESSION_TITLES[excerpt.session_id_short]) && (
          <span className="session-title" title={window.SESSION_TITLES[excerpt.session_id_short]}>
            {window.SESSION_TITLES[excerpt.session_id_short]}
          </span>
        )}
        {excerpt.agent_sourced && <span className="agent-tag">sub-agent</span>}
        {tierLabel && (
          <span className={`attribution-tag ${excerpt.attribution.confidence === "low" ? "low" : ""}`}
                title="How this excerpt was matched to the file">
            {tierLabel}
          </span>
        )}
      </div>
      {expanded && (
        <div className="excerpt-text">
          {renderExcerptText(renderText, renderHL)}
        </div>
      )}
      {!expanded && fixedHighlights.length > 0 && (
        <div className="excerpt-preview" onClick={() => setExpanded(true)}>
          {"[ "}
          {fixedHighlights.slice(0, 4).map((h, i) => (
            <React.Fragment key={i}>
              <span className="ellipsis">…</span>
              <span className="marker">{h.marker}</span>
            </React.Fragment>
          ))}
          {fixedHighlights.length > 4 && <span className="ellipsis"> +{fixedHighlights.length - 4} more</span>}
          <span className="ellipsis"> …]</span>
        </div>
      )}
      {expanded && condensed.truncated && excerpt.text !== condensed.text && (
        <button className="expand-btn" onClick={() => setExpanded(false)}>
          collapse
        </button>
      )}
      {otherFiles.length > 0 && (
        <div className="also-touches">
          <span className="lead">also touches</span>
          {otherFiles.map(p => (
            <button key={p} className="file-chip" onClick={(e) => { e.stopPropagation(); onJumpFile(p); }}>
              {p.split("/").pop()}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Evidence({ file, onJumpFile, density, codebaseName }) {
  if (!file) {
    return (
      <div className="evidence-empty">
        <p className="prompt">Select a file from the map or list to read what the model thought while editing it.</p>
      </div>
    );
  }
  const visibleExcerpts = (file.excerpts || []).slice().reverse().slice(0, 5);
  const cap = (file.excerpts || []).length > 5 ? `Showing 5 of ${file.excerpts.length} excerpts, most recent first` : null;
  return (
    <div>
      <div className="evidence-head">
        <div className="ev-name">{file.name}</div>
        <div className="ev-path">{relativePath(file.path, codebaseName)}</div>
        <div className="ev-magnitude">
          <span className="num">{file.tangle_count}</span>
          <span className="lbl">tangles across <strong style={{ color: "var(--ink-body)" }}>{file.session_count}</strong> sessions · score <strong style={{ color: "var(--ink-body)" }}>{file.score.toFixed(3)}</strong></span>
        </div>
      </div>

      <details className="ev-disclosure" open>
        <summary>why this score</summary>
        <ScoreBars components={file.score_components} />
      </details>

      {visibleExcerpts.length > 0 ? (
        <>
          <div className="ev-section-title">Thinking excerpts</div>
          {cap && <div className="ev-cap-note">{cap}</div>}
          <div className="excerpts">
            {visibleExcerpts.map((ex, i) => (
              <ExcerptCard key={i} excerpt={ex} currentPath={file.path} onJumpFile={onJumpFile} density={density} />
            ))}
          </div>
        </>
      ) : (
        <div style={{ padding: "40px 24px", textAlign: "center", color: "var(--ink-muted)", fontSize: 12, fontFamily: "var(--mono)" }}>
          No qualifying thinking excerpts for this file.
        </div>
      )}
    </div>
  );
}

function App() {
  const data = window.FRICTION_DATA;
  const tweaks = TWEAK_DEFAULTS;
  const [theme, setTheme] = useState(() => {
    if (typeof window !== "undefined" && window.matchMedia) {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    return "light";
  });
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);
  useEffect(() => { applyPalette(tweaks.palette, theme); }, [tweaks.palette, theme]);
  useEffect(() => { applyAccent(tweaks.accent); }, [tweaks.accent]);

  const [selectedPath, setSelectedPath] = useState("src/attune/core/storage.py");

  const fileByPath = useMemo(() => {
    const m = new Map();
    data.files.forEach(f => m.set(f.path, f));
    return m;
  }, [data]);
  const selectedFile = fileByPath.get(selectedPath);

  return (
    <div className="app">
      <Header data={data} theme={theme} setTheme={setTheme} />

      <div className="grid">
        <CorpusOverview data={data} selectedPath={selectedPath} onSelect={setSelectedPath} />

        <aside className="panel evidence">
          <Evidence file={selectedFile} onJumpFile={setSelectedPath} density={tweaks.excerptDensity} codebaseName={data.meta.name} />
        </aside>
      </div>
    </div>
  );
}

/* === Corpus overview v2 ===
   Append-only block per Phase 4B continuation. Defines CorpusOverview, the
   corpus-shape-aware left panel: empty / calm / healthy modes, a Standouts
   strip for outliers, a long-tail collapse cell, and an honest empty state.

   Notes vs the source handoff (handoff/corpus-overview.jsx):
   - The duplicate `const { useState, useMemo, useEffect, useRef } = React;`
     destructure was dropped (already present at the top of this file).
   - The `export` keyword on classifyCorpus was dropped (no module system in
     the Babel-in-browser harness; the window.classifyCorpus assignment at
     the bottom is what makes it accessible).
   - The duplicate `squarify` helper was dropped; this code reuses the
     existing one defined above (identical signature and algorithm).
*/

const FRICTION_FLOOR = 0.10;     // absolute score floor for "meaningful friction"
const TREEMAP_MIN_FILES = 10;    // need this many meaningful files to justify Map
const STANDOUT_CLIFF_RATIO = 2;  // ≥2× ratio between consecutive scores = cliff
const STANDOUT_MAX_POSITIONS = 3;// only the top 3 files can be standouts
const STANDOUT_DOMINANCE_SHARE = 0.30; // single-file fallback: ≥30% of total
const TAIL_COLLAPSE_RATIO = 0.25; // collapse files <25% of top-rest score

/* classifyCorpus — pure function. Decides mode + segments.

   Modes:
     - "empty"   : no files with any signal — empty state, both tabs disabled
     - "calm"    : <TREEMAP_MIN_FILES meaningful — list only, Map tab hidden
     - "healthy" : ≥TREEMAP_MIN_FILES meaningful — Map primary; standouts/rest/tail

   Healthy-mode algorithm:
     1. Sort meaningful files descending by score.
     2. Scan top STANDOUT_MAX_POSITIONS for the first ≥STANDOUT_CLIFF_RATIO
        ratio between consecutive files. Everything ABOVE that cliff is a standout.
     3. If no cliff, fall back to dominance: any file ≥30% of total is a standout.
     4. From the rest, collapse files <25% of top-rest score into the tail.
*/
function classifyCorpus(files, opts = {}) {
  const floor = opts.floor ?? FRICTION_FLOOR;
  const minFiles = opts.minFiles ?? TREEMAP_MIN_FILES;

  if (!files || files.length === 0) {
    return { mode: "empty", meaningful: [], standouts: [], rest: [], tail: [], totalScore: 0 };
  }
  const meaningful = files.filter(f => f.score >= floor);
  if (meaningful.length === 0) {
    return { mode: "empty", meaningful: [], standouts: [], rest: [], tail: [], totalScore: 0 };
  }
  const totalScore = meaningful.reduce((s, f) => s + f.score, 0);

  if (meaningful.length < minFiles) {
    const sorted = [...meaningful].sort((a, b) => b.score - a.score);
    return { mode: "calm", meaningful: sorted, standouts: [], rest: sorted, tail: [], totalScore };
  }

  const sorted = [...meaningful].sort((a, b) => b.score - a.score);
  let cliffIndex = -1;
  for (let i = 0; i < Math.min(STANDOUT_MAX_POSITIONS, sorted.length - 1); i++) {
    const ratio = sorted[i].score / sorted[i + 1].score;
    if (ratio >= STANDOUT_CLIFF_RATIO) { cliffIndex = i; break; }
  }
  if (cliffIndex === -1) {
    for (let i = 0; i < Math.min(STANDOUT_MAX_POSITIONS, sorted.length); i++) {
      if (sorted[i].score / totalScore >= STANDOUT_DOMINANCE_SHARE) cliffIndex = i;
      else break;
    }
  }
  const standouts = cliffIndex >= 0 ? sorted.slice(0, cliffIndex + 1) : [];
  const restAll = cliffIndex >= 0 ? sorted.slice(cliffIndex + 1) : sorted;

  const restTopScore = restAll[0]?.score || 0;
  const tailFloor = restTopScore * TAIL_COLLAPSE_RATIO;
  const rest = restAll.filter(f => f.score >= tailFloor);
  const tail = restAll.filter(f => f.score < tailFloor);

  return { mode: "healthy", meaningful: sorted, standouts, rest, tail, totalScore };
}

// Bin a score into one of 6 friction stops (continuous via t in [0..1]).
// Distinct from frictionColor() above — takes (score, max) instead of t.
function fricColor(score, max = 1) {
  const t = max > 0 ? Math.min(1, score / max) : 0;
  const idx = Math.min(5, Math.max(0, Math.floor(t * 6)));
  return `var(--f${idx})`;
}

function StandoutsStrip({ standouts, totalScore, selectedPath, onSelect }) {
  if (!standouts || standouts.length === 0) return null;
  const standoutTotal = standouts.reduce((s, f) => s + f.score, 0);
  const sharePct = Math.round((standoutTotal / totalScore) * 100);

  return (
    <div className="standouts">
      <div className="standouts-head">
        <span className="standouts-label">Standouts</span>
        <span className="standouts-meta">
          {standouts.length} {standouts.length === 1 ? "file" : "files"} · {sharePct}% of total friction
        </span>
      </div>
      <div className="standouts-cards">
        {standouts.map(f => {
          const sel = f.path === selectedPath;
          return (
            <button
              key={f.path}
              className={`standout-card ${sel ? "selected" : ""}`}
              onClick={() => onSelect(f.path)}
              style={{ borderLeftColor: fricColor(f.score) }}
            >
              <div className="standout-name" title={f.path}>{f.name}</div>
              <div className="standout-score-row">
                <span className="standout-score">{f.score.toFixed(2)}</span>
                <span className="standout-bar">
                  <span style={{ width: `${Math.min(100, f.score * 100)}%`, background: fricColor(f.score) }} />
                </span>
              </div>
              <div className="standout-meta">
                <span>{f.tangle_count} tangle{f.tangle_count !== 1 ? "s" : ""}</span>
                <span className="dot">·</span>
                <span>{f.session_count} session{f.session_count !== 1 ? "s" : ""}</span>
              </div>
            </button>
          );
        })}
      </div>
      <div className="standouts-note">
        These files dominate. They're shown separately so they don't crowd the map below.
      </div>
    </div>
  );
}

function TreemapView({ rest, tail, selectedPath, onSelect, height = 540 }) {
  const wrapRef = useRef(null);
  const [size, setSize] = useState({ w: 720, h: height });

  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver(([e]) => {
      setSize({ w: Math.max(200, e.contentRect.width), h: height });
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, [height]);

  const items = useMemo(() => {
    const out = rest.map(f => ({ ...f, value: f.score, kind: "file" }));
    if (tail && tail.length > 0) {
      const tailSum = tail.reduce((s, f) => s + f.score, 0);
      out.push({
        path: "__tail__",
        name: `+ ${tail.length} more`,
        score: tailSum / tail.length,
        tangle_count: tail.reduce((s, f) => s + f.tangle_count, 0),
        session_count: tail.reduce((s, f) => s + f.session_count, 0),
        value: Math.max(tailSum * 0.6, rest[rest.length - 1]?.score * 0.5 || 0.05),
        kind: "tail",
        tail_files: tail,
      });
    }
    return out;
  }, [rest, tail]);

  const tiled = useMemo(() => squarify(items, 0, 0, size.w, size.h), [items, size]);
  const maxScore = Math.max(...rest.map(f => f.score), 0.001);

  return (
    <div ref={wrapRef} className="treemap" style={{ height: size.h }}>
      {tiled.map(cell => {
        const isTail = cell.kind === "tail";
        const t = isTail ? 0.05 : cell.score / maxScore;
        const stopIdx = Math.min(5, Math.max(0, Math.floor(t * 6)));
        const tiny = cell.w < 70 || cell.h < 32;
        const sel = cell.path === selectedPath;
        const darkStop = !isTail && stopIdx >= 4;

        if (isTail) {
          return (
            <div
              key={cell.path}
              className="cell tail-cell"
              style={{ left: cell.x, top: cell.y, width: cell.w, height: cell.h }}
            >
              <div className="cell-name">{cell.name}</div>
              <div className="cell-meta">below threshold</div>
            </div>
          );
        }

        return (
          <button
            key={cell.path}
            className={`cell ${tiny ? "tiny" : ""} ${sel ? "selected" : ""} ${darkStop ? "dark-stop" : ""}`}
            style={{
              left: cell.x, top: cell.y, width: cell.w, height: cell.h,
              background: fricColor(cell.score, maxScore),
            }}
            onClick={() => onSelect(cell.path)}
            title={`${cell.path}\nscore ${cell.score.toFixed(3)} · ${cell.tangle_count} tangles · ${cell.session_count} sessions`}
          >
            <div className="cell-name">{cell.name}</div>
            <div className="cell-meta">{cell.tangle_count} · {cell.session_count}s</div>
          </button>
        );
      })}
    </div>
  );
}

function ListView({ files, sortBy, selectedPath, onSelect }) {
  const sorted = useMemo(() => {
    const arr = [...files];
    if (sortBy === "tangles") arr.sort((a, b) => b.tangle_count - a.tangle_count);
    else if (sortBy === "sessions") arr.sort((a, b) => b.session_count - a.session_count);
    else arr.sort((a, b) => b.score - a.score);
    return arr;
  }, [files, sortBy]);
  const max = Math.max(...sorted.map(f => f.score), 0.001);
  return (
    <div className="list">
      {sorted.map((f, i) => {
        const sel = f.path === selectedPath;
        return (
          <div
            key={f.path}
            className={`row ${sel ? "selected" : ""}`}
            onClick={() => onSelect(f.path)}
          >
            <span className="row-rank">{i + 1}</span>
            <div className="row-swatch" style={{ background: fricColor(f.score, max) }} />
            <div className="row-text">
              <div className="row-name">{f.name}</div>
              <div className="row-path">{f.directory === "/" ? f.name : f.path}</div>
            </div>
            <div className="row-meta">
              <div><strong>{f.score.toFixed(3)}</strong> score</div>
              <div>{f.tangle_count} tangles · {f.session_count} sx</div>
            </div>
          </div>
        );
      })}
      {sorted.length === 0 && (
        <div className="list-empty">No files match.</div>
      )}
    </div>
  );
}

function CalmNote({ totalFiles, filesWithSignal }) {
  const quiet = totalFiles - filesWithSignal;
  if (quiet <= 0) return null;
  return (
    <div className="calm-note">
      No friction detected in {quiet} other file{quiet !== 1 ? "s" : ""}.
    </div>
  );
}

function EmptyState({ totalFiles, sessionCount }) {
  return (
    <div className="empty-state">
      <div className="empty-eyebrow">no signal</div>
      <div className="empty-title">No friction detected</div>
      <div className="empty-body">
        Across {sessionCount} session{sessionCount !== 1 ? "s" : ""} and {totalFiles} file{totalFiles !== 1 ? "s" : ""},
        no thinking blocks crossed the friction threshold. The model worked smoothly through this corpus.
      </div>
    </div>
  );
}

function SortControl({ value, onChange }) {
  return (
    <label className="sort-control">
      <span className="sort-label">Sort</span>
      <select value={value} onChange={e => onChange(e.target.value)}>
        <option value="score">friction score</option>
        <option value="tangles">tangle count</option>
        <option value="sessions">sessions touched</option>
      </select>
    </label>
  );
}

function CorpusOverview({ data, selectedPath, onSelect }) {
  const cls = useMemo(() => classifyCorpus(data.files), [data.files]);

  const defaultTab = cls.mode === "healthy" ? "map" : "list";
  const [tab, setTab] = useState(defaultTab);
  const [sortBy, setSortBy] = useState("score");

  useEffect(() => { setTab(defaultTab); }, [defaultTab]);

  const filesWithSignal = cls.meaningful.length;

  if (cls.mode === "empty") {
    return (
      <div className="panel">
        <div className="panel-head panel-head-empty">
          <div className="panel-eyebrow">Friction map</div>
        </div>
        <EmptyState totalFiles={data.meta.file_count} sessionCount={data.meta.session_count} />
      </div>
    );
  }

  if (cls.mode === "calm") {
    return (
      <div className="panel">
        <div className="panel-head">
          <div className="panel-eyebrow">
            <span className="panel-title">Friction map</span>
            <span className="panel-sub">
              {filesWithSignal} file{filesWithSignal !== 1 ? "s" : ""} with friction · low signal corpus
            </span>
          </div>
          <div className="panel-head-right">
            <SortControl value={sortBy} onChange={setSortBy} />
          </div>
        </div>
        <ListView files={cls.rest} sortBy={sortBy} selectedPath={selectedPath} onSelect={onSelect} />
        <CalmNote totalFiles={data.meta.file_count} filesWithSignal={filesWithSignal} />
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <div className="tabs">
          <button className="tab" aria-selected={tab === "map"} onClick={() => setTab("map")}>Map</button>
          <button className="tab" aria-selected={tab === "list"} onClick={() => setTab("list")}>List</button>
        </div>
        <div className="panel-head-right">
          {tab === "list" && <SortControl value={sortBy} onChange={setSortBy} />}
        </div>
      </div>

      <StandoutsStrip
        standouts={cls.standouts}
        totalScore={cls.totalScore}
        selectedPath={selectedPath}
        onSelect={onSelect}
      />

      {tab === "map" ? (
        <>
          <div className="treemap-wrap">
            <TreemapView
              rest={cls.rest}
              tail={cls.tail}
              selectedPath={selectedPath}
              onSelect={onSelect}
            />
          </div>
          <div className="legend">
            <span>high friction</span>
            <div className="legend-bar" />
            <span>low friction</span>
          </div>
        </>
      ) : (
        <ListView
          files={[...cls.rest, ...cls.tail]}
          sortBy={sortBy}
          selectedPath={selectedPath}
          onSelect={onSelect}
        />
      )}
    </div>
  );
}

window.CorpusOverview = CorpusOverview;
window.classifyCorpus = classifyCorpus;

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
