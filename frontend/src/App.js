import { useState, useEffect } from 'react';
import './App.css';

const API = 'http://127.0.0.1:8000';

const COURT_MAP = {
  ilnd:  'N.D. Ill.',
  nysd:  'S.D.N.Y.',
  flsd:  'S.D. Fla.',
  cacd:  'C.D. Cal.',
  txnd:  'N.D. Tex.',
  nyed:  'E.D.N.Y.',
  nynd:  'N.D.N.Y.',
  njd:   'D.N.J.',
  wawd:  'W.D. Wash.',
  cand:  'N.D. Cal.',
  ohnd:  'N.D. Ohio',
  gamd:  'M.D. Ga.',
};

function courtLabel(court) {
  if (!court) return '—';
  return COURT_MAP[court.toLowerCase()] ?? court.toUpperCase();
}

function highlight(text, query) {
  if (!query || !text) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark>{text.slice(idx, idx + query.length)}</mark>
      {text.slice(idx + query.length)}
    </>
  );
}

function SearchIcon() {
  return (
    <svg
      className="search-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function CaseCard({ c }) {
  return (
    <div className="case-card">
      <div className="card-badges">
        <span className="badge-court">{courtLabel(c.court)}</span>
        <span className="badge-status badge-status--approved">TRO已批准</span>
      </div>
      <p className="card-name">{c.case_name || '—'}</p>
      <div className="card-tags">
        <span className="badge-tag">商标侵权</span>
      </div>
      <p className="card-meta-text">
        立案：{c.date_filed || '—'}
      </p>
    </div>
  );
}

function DefendantCard({ item, query }) {
  const storeName = item.store_name || item.cleaned_name || item.defendant_name || '—';
  return (
    <div className="case-card">
      <div className="card-badges">
        <span className="badge-court">{courtLabel(item.court)}</span>
        {item.platform && <span className="badge-tag">{item.platform}</span>}
      </div>
      <p className="card-name">{item.case_name || '—'}</p>
      <p className="defendant-name">{highlight(storeName, query)}</p>
      <p className="card-meta-text">立案：{item.date_filed || '—'}</p>
      {item.source_url && (
        <a
          className="card-source-link"
          href={item.source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          查看原始案件 →
        </a>
      )}
    </div>
  );
}

export default function App() {
  const [query,       setQuery]       = useState('');
  const [results,     setResults]     = useState(null);
  const [cases,       setCases]       = useState([]);
  const [searching,   setSearching]   = useState(false);
  const [casesLoading, setCasesLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/cases`)
      .then(r => r.json())
      .then(data => setCases(Array.isArray(data) ? data : []))
      .catch(() => setCases([]))
      .finally(() => setCasesLoading(false));
  }, []);

  async function handleSearch(e) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    try {
      const res  = await fetch(`${API}/search?company=${encodeURIComponent(q)}`);
      const data = await res.json();
      setResults(data.results ?? []);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  function clearSearch() {
    setResults(null);
    setQuery('');
  }

  const isSearchMode = results !== null;

  return (
    <>
      {/* ── Nav ── */}
      <nav className="nav">
        <span className="nav-brand">
          TRO <em>侵权监测</em>
        </span>
        <span className="nav-tagline">美国联邦法院 · 持续追踪</span>
      </nav>

      {/* ── Hero ── */}
      <div className="hero">
        <h1 className="hero-title">
          <span className="hero-line1">供应商侵权风险</span>
          <span className="hero-line2">一查便知。</span>
        </h1>
        <p className="hero-sub">
          每一条 TRO 案件，都是你提前规避风险的机会。持续追踪美国联邦法院最新动态。
        </p>

        <form className="search-form" onSubmit={handleSearch}>
          <div className="search-box">
            <SearchIcon />
            <input
              className="search-input"
              type="text"
              placeholder="搜索供应商名称或店铺名…"
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
            <button className="search-btn" type="submit" disabled={searching}>
              {searching ? '搜索中' : '搜索'}
            </button>
          </div>
        </form>

        <p className="hero-count">
          已收录 <strong>1,886+</strong> 条案件记录，持续更新
        </p>
      </div>

      {/* ── Content ── */}
      <div className="section">
        <div className="section-header">
          <span className="section-title">
            {isSearchMode ? '搜索结果' : '最近新增案件'}
          </span>
          {isSearchMode
            ? <span className="section-count">{results.length} 条匹配记录</span>
            : !casesLoading && <span className="section-count">{cases.length} 条</span>
          }
          {isSearchMode && (
            <button className="section-clear" onClick={clearSearch}>
              清除搜索 ×
            </button>
          )}
        </div>

        <div className="card-grid">
          {isSearchMode ? (
            results.length === 0 ? (
              <div className="grid-message">
                <h3>未找到相关记录</h3>
                <p>请尝试简化搜索词，或直接搜索英文店铺名</p>
              </div>
            ) : (
              results.map((item, i) => (
                <DefendantCard
                  key={item.defendant_id ?? i}
                  item={item}
                  query={query.trim()}
                />
              ))
            )
          ) : casesLoading ? (
            <div className="grid-message">
              <p>加载中…</p>
            </div>
          ) : cases.length === 0 ? (
            <div className="grid-message">
              <h3>暂无案件数据</h3>
              <p>请检查后端服务是否正常运行</p>
            </div>
          ) : (
            cases.slice(0, 20).map(c => (
              <CaseCard key={c.id} c={c} />
            ))
          )}
        </div>
      </div>
    </>
  );
}
