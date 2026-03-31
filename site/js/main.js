const DATA_URL = 'data/analysis.json';

let data = null;

const FLYWHEEL_DESCRIPTIONS = {
    adoption: 'Promotion of PMI certifications, tools, standards, or PMI-branded offerings',
    advocacy: 'Member stories, partnerships, ambassadors, or external visibility',
    contribution: 'Volunteer engagement, member-led content, thought leadership',
    retention: 'Engaging, inclusive, and value-driven programming',
};

async function init() {
    try {
        const resp = await fetch(DATA_URL);
        data = await resp.json();
    } catch (e) {
        document.querySelector('main').innerHTML =
            '<p class="section" style="color:#dc3545">Could not load analysis data. Run the analysis pipeline first.</p>';
        return;
    }

    renderLastUpdated();
    renderStats();
    renderFlywheel();
    renderNotable();
    renderChapters();
    renderPatterns();
    setupFilters();
}

function renderLastUpdated() {
    const el = document.getElementById('lastUpdated');
    if (data.generated_at) {
        const d = new Date(data.generated_at);
        el.textContent = `Last updated: ${d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`;
    }
}

function renderStats() {
    const grid = document.getElementById('statsGrid');
    const totalFindings = data.chapters.reduce((n, ch) => n + (ch.findings?.length || 0), 0);
    const stats = [
        { number: data.total_chapters, label: 'Chapters' },
        { number: data.analyzed, label: 'Analyzed' },
        { number: totalFindings, label: 'Findings' },
        { number: data.unchanged || 0, label: 'Unchanged' },
    ];
    grid.innerHTML = stats.map(s =>
        `<div class="stat-card"><div class="number">${s.number}</div><div class="label">${s.label}</div></div>`
    ).join('');
}

function renderFlywheel() {
    const grid = document.getElementById('flywheelGrid');
    const counts = data.patterns?.flywheel_counts || {};
    grid.innerHTML = Object.entries(FLYWHEEL_DESCRIPTIONS).map(([key, desc]) =>
        `<div class="flywheel-card ${key}">
            <div class="fw-name">${key}</div>
            <div class="fw-count">${counts[key] || 0}</div>
            <div class="fw-desc">${desc}</div>
        </div>`
    ).join('');
}

function renderNotable() {
    const container = document.getElementById('notableFindings');
    const findings = data.patterns?.notable_findings || [];
    if (!findings.length) {
        container.innerHTML = '<p class="section-desc">No notable findings yet.</p>';
        return;
    }
    container.innerHTML = findings.map(f =>
        `<div class="notable-card">
            <div class="notable-header">
                <span class="chapter-name">${f.chapter}</span>
                <span>
                    <span class="badge-fw ${f.flywheel_element}">${f.flywheel_element}</span>
                    <span class="badge-action">${f.suggested_action.replace('_', ' ')}</span>
                </span>
            </div>
            <div class="activity">${f.activity}</div>
            <div class="why">${f.why_it_matters}</div>
        </div>`
    ).join('');
}

function renderChapters(filters = {}) {
    const container = document.getElementById('chapterList');
    let chapters = data.chapters.filter(ch => ch.status === 'analyzed' || ch.status === 'unchanged');

    // Apply filters
    if (filters.flywheel) {
        chapters = chapters.filter(ch =>
            ch.findings?.some(f => f.flywheel_element === filters.flywheel)
        );
    }
    if (filters.action) {
        chapters = chapters.filter(ch =>
            ch.findings?.some(f => f.suggested_action === filters.action)
        );
    }
    if (filters.country) {
        chapters = chapters.filter(ch =>
            (ch.country || '').toLowerCase().includes(filters.country.toLowerCase())
        );
    }
    if (filters.search) {
        const q = filters.search.toLowerCase();
        chapters = chapters.filter(ch =>
            ch.chapter_name.toLowerCase().includes(q) ||
            (ch.state_province || '').toLowerCase().includes(q)
        );
    }

    if (!chapters.length) {
        container.innerHTML = '<p class="section-desc">No chapters match the current filters.</p>';
        return;
    }

    container.innerHTML = chapters.map(ch => {
        const findingsHtml = (ch.findings || []).map(f =>
            `<div class="finding-row">
                <div class="f-activity">
                    <span class="badge-fw ${f.flywheel_element}">${f.flywheel_element}</span>
                    <span class="badge-action">${f.suggested_action.replace('_', ' ')}</span>
                    ${f.activity}
                </div>
                <div class="f-why">${f.why_it_matters}</div>
            </div>`
        ).join('');

        const findingCount = (ch.findings || []).length;
        const location = [ch.state_province, ch.country].filter(Boolean).join(', ');

        return `<div class="chapter-card" onclick="this.classList.toggle('expanded')">
            <div class="ch-header">
                <span>
                    <span class="status-dot ${ch.status}"></span>
                    <span class="ch-name">${ch.chapter_name}</span>
                    <span class="ch-location">${location}</span>
                </span>
                <span class="ch-location">${findingCount} finding${findingCount !== 1 ? 's' : ''}</span>
            </div>
            ${ch.summary ? `<div class="ch-summary">${ch.summary}</div>` : ''}
            <div class="ch-findings">${findingsHtml || '<p class="section-desc">No findings.</p>'}</div>
        </div>`;
    }).join('');
}

function renderPatterns() {
    const container = document.getElementById('patterns');
    const p = data.patterns;
    if (!p) {
        container.innerHTML = '<p class="section-desc">No patterns available.</p>';
        return;
    }

    const actionHtml = Object.entries(p.action_counts || {})
        .sort((a, b) => b[1] - a[1])
        .map(([action, count]) => `<li><strong>${action.replace('_', ' ')}:</strong> ${count} findings</li>`)
        .join('');

    const gapsHtml = (p.gaps || []).length
        ? `<div class="pattern-section">
            <h3>Gaps &amp; Opportunities</h3>
            <p>These ${p.gaps.length} chapters had no distinctive findings beyond standard operations. They may benefit from CEP outreach:</p>
            <p class="section-desc">${p.gaps.join(' &middot; ')}</p>
        </div>`
        : '';

    container.innerHTML = `
        <div class="pattern-section">
            <h3>Coverage</h3>
            <p>${p.chapters_with_findings} chapters with distinctive findings, ${p.chapters_without_findings} without.</p>
        </div>
        <div class="pattern-section">
            <h3>Suggested Actions</h3>
            <ul>${actionHtml}</ul>
        </div>
        ${gapsHtml}
    `;
}

function setupFilters() {
    const ids = ['filterFlywheel', 'filterAction', 'filterCountry', 'filterSearch'];
    for (const id of ids) {
        document.getElementById(id).addEventListener(id === 'filterSearch' ? 'input' : 'change', applyFilters);
    }
}

function applyFilters() {
    renderChapters({
        flywheel: document.getElementById('filterFlywheel').value,
        action: document.getElementById('filterAction').value,
        country: document.getElementById('filterCountry').value,
        search: document.getElementById('filterSearch').value,
    });
}

init();
