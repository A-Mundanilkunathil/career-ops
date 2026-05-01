#!/usr/bin/env python3
"""Build a self-contained HTML dashboard from career-ops data files."""
import os, re, json, html, glob, subprocess, sys, webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "index.html"


def parse_applications_md(text: str) -> list[dict]:
    """Parse the markdown table in applications.md → list of dicts."""
    rows = []
    in_table = False
    headers = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|") and not in_table:
            cells = [c.strip() for c in line.strip("|").split("|")]
            headers = cells
            in_table = True
            continue
        if in_table and re.match(r"^\|[\s\-|]+\|$", line):
            continue
        if in_table and line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
        elif in_table and not line.startswith("|"):
            in_table = False
    return rows


def collect_reports() -> dict[str, str]:
    """Read all report .md files, return {filename: markdown_content}."""
    out = {}
    reports_dir = ROOT / "reports"
    for path in sorted(reports_dir.glob("*.md")):
        if path.name.startswith("."):
            continue
        out[path.name] = path.read_text(encoding="utf-8")
    return out


def collect_pdfs() -> list[str]:
    """List PDF filenames in output/."""
    output_dir = ROOT / "output"
    return sorted([p.name for p in output_dir.glob("*.pdf")])


def collect_pipeline() -> int:
    """Count pending pipeline entries."""
    pipeline = ROOT / "data" / "pipeline.md"
    if not pipeline.exists():
        return 0
    text = pipeline.read_text(encoding="utf-8")
    return len(re.findall(r"^- \[ \]", text, re.MULTILINE))


def main() -> None:
    apps_path = ROOT / "data" / "applications.md"
    apps = parse_applications_md(apps_path.read_text(encoding="utf-8")) if apps_path.exists() else []
    reports = collect_reports()
    pdfs = collect_pdfs()
    pipeline_count = collect_pipeline()

    # Build single self-contained HTML
    template = HTML_TEMPLATE.replace(
        "__DATA__",
        json.dumps(
            {"apps": apps, "reports": reports, "pdfs": pdfs, "pipeline_count": pipeline_count, "root": str(ROOT)},
            ensure_ascii=False,
        ),
    )
    OUT.write_text(template, encoding="utf-8")
    print(f"Wrote {OUT}")
    if "--open" in sys.argv:
        webbrowser.open(f"file://{OUT}")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Career Ops Dashboard — Aaron</title>
<style>
  :root {
    --bg: #0f1419;
    --card: #1a1f2e;
    --border: #2a3142;
    --text: #e8eaed;
    --muted: #a0a8b8;
    --accent: #4a9eff;
    --green: #4ade80;
    --yellow: #facc15;
    --red: #f87171;
    --purple: #c084fc;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  header {
    background: var(--card);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px;
    display: flex;
    align-items: center;
    gap: 24px;
  }
  header h1 {
    font-size: 18px;
    font-weight: 700;
    color: var(--accent);
  }
  .stats { display: flex; gap: 16px; font-size: 13px; color: var(--muted); }
  .stats b { color: var(--text); font-weight: 600; }
  main { padding: 24px; max-width: 1400px; margin: 0 auto; }
  .controls {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
    align-items: center;
    flex-wrap: wrap;
  }
  .controls input, .controls select {
    background: var(--card);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-family: inherit;
  }
  .controls input { width: 240px; }
  .controls input::placeholder { color: var(--muted); }
  table {
    width: 100%;
    border-collapse: collapse;
    background: var(--card);
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border);
  }
  thead { background: rgba(255, 255, 255, 0.03); }
  th, td {
    padding: 10px 14px;
    text-align: left;
    font-size: 13px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }
  th {
    font-weight: 600;
    color: var(--muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    cursor: pointer;
    user-select: none;
  }
  th:hover { color: var(--text); }
  tbody tr { transition: background 0.1s; cursor: pointer; }
  tbody tr:hover { background: rgba(74, 158, 255, 0.05); }
  tbody tr:last-child td { border-bottom: 0; }
  .score {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .score-high { color: var(--green); }
  .score-mid { color: var(--yellow); }
  .score-low { color: var(--red); }
  .status {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .status-Evaluated { background: rgba(74, 158, 255, 0.15); color: var(--accent); }
  .status-Applied { background: rgba(192, 132, 252, 0.15); color: var(--purple); }
  .status-Interview { background: rgba(250, 204, 21, 0.15); color: var(--yellow); }
  .status-Offer { background: rgba(74, 222, 128, 0.15); color: var(--green); }
  .status-Rejected, .status-Discarded, .status-SKIP { background: rgba(248, 113, 113, 0.15); color: var(--red); }
  .pdf-link, .report-link {
    color: var(--accent);
    text-decoration: none;
    font-size: 12px;
  }
  .pdf-link:hover, .report-link:hover { text-decoration: underline; }
  .empty {
    padding: 40px;
    text-align: center;
    color: var(--muted);
    font-size: 14px;
  }
  /* Modal for report detail */
  .modal-bg {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    z-index: 100;
    align-items: flex-start;
    justify-content: center;
    padding: 40px 20px;
    overflow-y: auto;
  }
  .modal-bg.show { display: flex; }
  .modal {
    background: var(--card);
    border-radius: 8px;
    border: 1px solid var(--border);
    max-width: 900px;
    width: 100%;
    padding: 24px 32px;
    position: relative;
  }
  .modal-close {
    position: absolute;
    top: 14px;
    right: 18px;
    background: none;
    border: none;
    color: var(--muted);
    font-size: 22px;
    cursor: pointer;
  }
  .modal-close:hover { color: var(--text); }
  .modal-content {
    color: var(--text);
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    font-family: ui-monospace, "SF Mono", monospace;
    max-height: 75vh;
    overflow-y: auto;
    padding-right: 12px;
  }
  .pdf-section {
    margin-top: 24px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px 24px;
  }
  .pdf-section h2 {
    font-size: 13px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 12px;
  }
  .pdf-list { display: flex; flex-direction: column; gap: 6px; }
  .pdf-list a {
    color: var(--accent);
    text-decoration: none;
    font-size: 13px;
    font-family: ui-monospace, monospace;
  }
  .pdf-list a:hover { text-decoration: underline; }
  footer {
    margin-top: 32px;
    padding: 16px 24px;
    color: var(--muted);
    font-size: 12px;
    text-align: center;
    border-top: 1px solid var(--border);
  }
  footer code {
    background: var(--card);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
  }
</style>
</head>
<body>
<header>
  <h1>Career Ops Dashboard</h1>
  <div class="stats">
    <span><b id="stat-total">0</b> evaluated</span>
    <span><b id="stat-high">0</b> high-fit (≥4.5)</span>
    <span><b id="stat-pipeline">0</b> in pipeline</span>
    <span><b id="stat-applied">0</b> applied</span>
    <span><b id="stat-interview">0</b> interviewing</span>
  </div>
</header>

<main>
  <div class="controls">
    <input type="text" id="filter" placeholder="Filter by company / role / notes…">
    <select id="status-filter">
      <option value="">All statuses</option>
      <option value="Evaluated">Evaluated</option>
      <option value="Applied">Applied</option>
      <option value="Responded">Responded</option>
      <option value="Interview">Interview</option>
      <option value="Offer">Offer</option>
      <option value="Rejected">Rejected</option>
      <option value="Discarded">Discarded</option>
    </select>
    <select id="sort">
      <option value="score-desc">Score ↓</option>
      <option value="score-asc">Score ↑</option>
      <option value="date-desc">Date ↓</option>
      <option value="date-asc">Date ↑</option>
      <option value="num-asc">Number ↑</option>
    </select>
    <span style="color: var(--muted); font-size: 12px; margin-left: auto;">Click a row to read the full report</span>
  </div>

  <table id="apps-table">
    <thead>
      <tr>
        <th>#</th>
        <th>Date</th>
        <th>Company</th>
        <th>Role</th>
        <th>Score</th>
        <th>Status</th>
        <th>PDF</th>
        <th>Notes</th>
      </tr>
    </thead>
    <tbody id="apps-body"></tbody>
  </table>

  <div class="pdf-section" id="pdf-section">
    <h2>Generated PDFs (output/)</h2>
    <div class="pdf-list" id="pdf-list"></div>
  </div>
</main>

<footer>
  Regenerate with <code>python3 dashboard-web/build.py --open</code> after running new evaluations.
</footer>

<div class="modal-bg" id="modal-bg">
  <div class="modal">
    <button class="modal-close" onclick="closeModal()">&times;</button>
    <div class="modal-content" id="modal-content"></div>
  </div>
</div>

<script>
const DATA = __DATA__;

function scoreClass(score) {
  const n = parseFloat(score);
  if (isNaN(n)) return '';
  if (n >= 4.5) return 'score-high';
  if (n >= 3.5) return 'score-mid';
  return 'score-low';
}

function render() {
  const filter = document.getElementById('filter').value.toLowerCase();
  const statusFilter = document.getElementById('status-filter').value;
  const sort = document.getElementById('sort').value;
  const tbody = document.getElementById('apps-body');
  tbody.innerHTML = '';

  let rows = DATA.apps.slice();
  if (filter) {
    rows = rows.filter(r =>
      Object.values(r).some(v => v && v.toString().toLowerCase().includes(filter))
    );
  }
  if (statusFilter) rows = rows.filter(r => r.Status === statusFilter);

  const parseScore = r => parseFloat((r.Score || '0').replace(/\/.*$/, ''));
  const parseNum = r => parseInt(r['#'] || 0);
  rows.sort((a, b) => {
    switch (sort) {
      case 'score-desc': return parseScore(b) - parseScore(a);
      case 'score-asc':  return parseScore(a) - parseScore(b);
      case 'date-desc':  return (b.Date || '').localeCompare(a.Date || '');
      case 'date-asc':   return (a.Date || '').localeCompare(b.Date || '');
      case 'num-asc':    return parseNum(a) - parseNum(b);
    }
    return 0;
  });

  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty">No applications match your filters.</td></tr>';
  } else {
    for (const r of rows) {
      const tr = document.createElement('tr');
      const reportMatch = (r.Report || '').match(/\((reports\/[^)]+)\)/);
      const reportFile = reportMatch ? reportMatch[1].replace('reports/', '') : null;
      tr.innerHTML = `
        <td>${r['#'] || ''}</td>
        <td>${r.Date || ''}</td>
        <td>${r.Company || ''}</td>
        <td>${r.Role || ''}</td>
        <td class="score ${scoreClass(r.Score)}">${r.Score || ''}</td>
        <td><span class="status status-${(r.Status || '').replace(/\s/g, '')}">${r.Status || ''}</span></td>
        <td>${r.PDF || ''}</td>
        <td>${r.Notes || ''}</td>
      `;
      if (reportFile && DATA.reports[reportFile]) {
        tr.onclick = () => openModal(DATA.reports[reportFile]);
      }
      tbody.appendChild(tr);
    }
  }

  // Stats
  document.getElementById('stat-total').textContent = DATA.apps.length;
  document.getElementById('stat-high').textContent = DATA.apps.filter(r => parseScore(r) >= 4.5).length;
  document.getElementById('stat-pipeline').textContent = DATA.pipeline_count;
  document.getElementById('stat-applied').textContent = DATA.apps.filter(r => r.Status === 'Applied').length;
  document.getElementById('stat-interview').textContent = DATA.apps.filter(r => r.Status === 'Interview').length;
}

function openModal(content) {
  document.getElementById('modal-content').textContent = content;
  document.getElementById('modal-bg').classList.add('show');
}

function closeModal() {
  document.getElementById('modal-bg').classList.remove('show');
}

document.getElementById('modal-bg').addEventListener('click', (e) => {
  if (e.target.id === 'modal-bg') closeModal();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
});

document.getElementById('filter').addEventListener('input', render);
document.getElementById('status-filter').addEventListener('change', render);
document.getElementById('sort').addEventListener('change', render);

// PDF list
const pdfList = document.getElementById('pdf-list');
if (DATA.pdfs.length === 0) {
  pdfList.innerHTML = '<span style="color: var(--muted); font-size: 12px;">No PDFs generated yet.</span>';
} else {
  for (const pdf of DATA.pdfs) {
    const a = document.createElement('a');
    a.href = `file://${DATA.root}/output/${pdf}`;
    a.target = '_blank';
    a.textContent = pdf;
    pdfList.appendChild(a);
  }
}

render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
