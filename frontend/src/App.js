import { useState } from 'react';
import './App.css';

const API = 'https://tro-collector-production.up.railway.app';

const PLATFORMS = ['', 'Amazon', 'eBay', 'Wish', 'Walmart'];

function RiskBadge({ score }) {
  if (score == null) return null;
  const cls =
    score >= 70 ? 'badge badge-high' :
    score >= 40 ? 'badge badge-mid' :
                  'badge badge-low';
  return <span className={cls}>风险 {score}</span>;
}

function ResultCard({ item }) {
  const storeName = item.store_name || item.cleaned_name || item.defendant_name || '—';
  const court     = item.court || '—';

  return (
    <div className="card">
      <div className="card-top">
        <span className="card-name">{storeName}</span>
        <RiskBadge score={item.risk_score} />
      </div>

      <div className="card-meta">
        {item.platform && <span className="platform-tag">{item.platform}</span>}
        <span className="court-text">{court}</span>
      </div>

      {item.case_name && <p className="card-case">{item.case_name}</p>}
      {item.date_filed && <p className="card-date">立案日期：{item.date_filed}</p>}

      {item.source_url && (
        <div className="card-footer">
          <a
            className="source-link"
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            查看原始案件 →
          </a>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [query,     setQuery]     = useState('');
  const [platform,  setPlatform]  = useState('');
  const [court,     setCourt]     = useState('');
  const [afterDate, setAfterDate] = useState('');
  const [minScore,  setMinScore]  = useState('');
  const [results,   setResults]   = useState(null);
  const [loading,   setLoading]   = useState(false);

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ company: query.trim() });
      if (platform)  params.set('platform',  platform);
      if (court)     params.set('court',      court);
      if (afterDate) params.set('after_date', afterDate);
      if (minScore)  params.set('min_score',  minScore);

      const res  = await fetch(`${API}/search?${params}`);
      const data = await res.json();
      setResults(data.results ?? []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <nav className="nav">
        <div className="nav-brand">
          <div className="nav-logo" />
          <span className="nav-title">TRO Monitor</span>
        </div>
        <span className="nav-sub">供应商风险查询系统</span>
      </nav>

      <main className="main">
        <div className="hero">
          <h1>查询供应商侵权记录</h1>
          <p>输入公司名或店铺名，查询美国联邦法院 TRO 案件记录</p>
        </div>

        <form onSubmit={handleSearch}>
          <div className="search-row">
            <input
              className="search-input"
              type="text"
              placeholder="输入店铺名或公司名……"
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
            <button className="search-btn" type="submit" disabled={loading}>
              {loading ? '搜索中…' : '搜索'}
            </button>
          </div>

          <div className="filters">
            <select
              className="filter-select"
              value={platform}
              onChange={e => setPlatform(e.target.value)}
            >
              {PLATFORMS.map(p => (
                <option key={p} value={p}>{p || '全部平台'}</option>
              ))}
            </select>

            <input
              className="filter-input"
              type="text"
              placeholder="法院（如 ilnd）"
              value={court}
              onChange={e => setCourt(e.target.value)}
            />

            <input
              className="filter-input"
              type="date"
              value={afterDate}
              onChange={e => setAfterDate(e.target.value)}
              title="立案日期不早于"
            />

            <input
              className="filter-input filter-input--sm"
              type="number"
              min="0"
              max="100"
              placeholder="最低风险分"
              value={minScore}
              onChange={e => setMinScore(e.target.value)}
            />
          </div>
        </form>

        {results !== null && (
          results.length > 0 ? (
            <>
              <p className="result-count">找到 {results.length} 条记录</p>
              {results.map((item, i) => (
                <ResultCard key={item.defendant_id ?? i} item={item} />
              ))}
            </>
          ) : (
            <div className="empty">
              <div className="empty-icon">📭</div>
              <h3>未找到相关记录</h3>
              <p>请尝试简化搜索词，或直接搜索英文店铺名</p>
            </div>
          )
        )}
      </main>
    </>
  );
}
