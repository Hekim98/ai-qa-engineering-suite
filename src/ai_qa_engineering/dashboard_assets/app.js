const state = {
  configurations: [],
  audits: [],
  jobs: [],
  selectedAuditId: null,
};

const token = document.querySelector('meta[name="ai-qa-token"]').content;
let pollTimer = null;

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#039;');

const label = (value) => String(value ?? '—').replaceAll('-', ' ');

function showToast(message, tone = 'success') {
  const toast = document.querySelector('#toast');
  toast.textContent = message;
  toast.className = `toast ${tone}`;
  toast.hidden = false;
  window.setTimeout(() => { toast.hidden = true; }, 4200);
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function selectedConfiguration() {
  const path = document.querySelector('#config-select').value;
  return state.configurations.find((item) => item.path === path);
}

function renderProfiles() {
  const selected = selectedConfiguration();
  const target = document.querySelector('#profiles');
  target.innerHTML = '<legend>Browser coverage</legend>' + (selected?.profiles || []).map((profile) => `
    <label class="profile-choice">
      <input type="checkbox" value="${escapeHtml(profile.name)}" checked>
      <span><strong>${escapeHtml(profile.name)}</strong><small>${escapeHtml(profile.browser)} · ${escapeHtml(profile.suite)}</small></span>
    </label>
  `).join('');
}

function renderJob() {
  const job = state.jobs[0];
  const active = job && ['queued', 'running'].includes(job.status);
  const button = document.querySelector('#run-audit');
  button.disabled = Boolean(active);
  button.textContent = active ? 'Audit in progress…' : 'Run selected profiles';
  const target = document.querySelector('#job-state');
  if (!job) {
    target.innerHTML = '';
    return;
  }
  if (active) {
    target.innerHTML = `<span class="spinner"></span><strong>${escapeHtml(label(job.status))}</strong><small>${job.profiles.length} profile${job.profiles.length === 1 ? '' : 's'} selected</small>`;
  } else if (job.status === 'failed') {
    target.innerHTML = `<span class="job-error"><strong>Audit could not finish</strong><small>${escapeHtml(job.error)}</small></span>`;
  } else {
    target.innerHTML = `<span class="job-success"><strong>Latest audit completed</strong><small>${escapeHtml(job.audit_id)}</small></span>`;
  }
}

function renderAuditList() {
  document.querySelector('#audit-count').textContent = state.audits.length;
  const latest = state.audits[0];
  document.querySelector('#latest-status').textContent = latest ? label(latest.status) : 'No runs';
  document.querySelector('#latest-passed').textContent = latest ? `${latest.passed}/${latest.tests}` : '—';
  document.querySelector('#latest-review').textContent = latest?.review?.pending ?? '—';
  const target = document.querySelector('#audit-list');
  target.innerHTML = state.audits.length ? state.audits.map((audit) => `
    <button class="audit-row${audit.audit_id === state.selectedAuditId ? ' selected' : ''}" type="button" data-audit-id="${escapeHtml(audit.audit_id)}">
      <span><strong>${escapeHtml(audit.project)}</strong><small>${escapeHtml(audit.environment)} · ${audit.passed}/${audit.tests} passed</small></span>
      <span class="status ${escapeHtml(audit.status)}">${escapeHtml(label(audit.status))}</span>
    </button>
  `).join('') : '<p class="muted">No audit packages yet. Start with the controlled authentication sandbox.</p>';
  target.querySelectorAll('[data-audit-id]').forEach((button) => {
    button.addEventListener('click', () => loadAudit(button.dataset.auditId));
  });
}

function renderShell() {
  const select = document.querySelector('#config-select');
  const prior = select.value;
  select.innerHTML = state.configurations.map((item) => `<option value="${escapeHtml(item.path)}">${escapeHtml(item.name)} · ${escapeHtml(item.environment)}</option>`).join('');
  if (state.configurations.some((item) => item.path === prior)) select.value = prior;
  renderProfiles();
  renderJob();
  renderAuditList();
}

function profileRows(profiles) {
  return profiles.map((profile) => {
    const latest = profile.attempts.at(-1);
    return `<tr>
      <td><strong>${escapeHtml(profile.profile)}</strong><small>${escapeHtml(profile.browser)}</small></td>
      <td><span class="status ${escapeHtml(profile.status)}">${escapeHtml(label(profile.status))}</span></td>
      <td>${profile.attempts.length}</td>
      <td>${latest?.passed ?? 0}/${latest?.test_count ?? 0}</td>
      <td>${profile.persistent_failures.length}</td>
      <td>${profile.flaky_tests.length}</td>
      <td>${profile.api_passed ?? 0}/${profile.api_checks ?? 0}</td>
    </tr>`;
  }).join('');
}

function apiRows(checks) {
  return checks.map((check) => `<tr>
    <td><strong>${escapeHtml(check.name)}</strong><small>${escapeHtml(check.profile)}</small></td>
    <td>${escapeHtml(check.method)}</td>
    <td><code>${escapeHtml(check.path)}</code></td>
    <td><span class="status ${escapeHtml(check.outcome)}">${escapeHtml(label(check.outcome))}</span></td>
    <td>${check.actual_status ?? '—'}</td>
    <td>${check.latency_ms ?? '—'} / ${check.latency_budget_ms} ms</td>
    <td>${escapeHtml(check.response_schema || 'Not requested')}</td>
    <td><a class="evidence-pill" href="${escapeHtml(check.evidence_url || '#')}" target="_blank" rel="noopener">API evidence</a></td>
  </tr>`).join('');
}

function evidenceLinks(detail, paths) {
  const lookup = new Map(detail.evidence.flatMap((record) => record.files.map((file) => [file.path, file])));
  return paths.map((path) => {
    const file = lookup.get(path);
    return file ? `<a class="evidence-pill" href="${escapeHtml(file.url)}" target="_blank" rel="noopener">${escapeHtml(file.kind)} · ${escapeHtml(file.name)}</a>` : '';
  }).join('');
}

function reviewForm(detail, candidate) {
  const review = candidate.review;
  const decision = review?.decision || 'rejected';
  const isConfirmed = decision === 'confirmed';
  return `<article class="candidate-card">
    <div class="candidate-top">
      <div><span class="candidate-id">${escapeHtml(candidate.id)}</span><h4>${escapeHtml(candidate.title)}</h4></div>
      <span class="status ${escapeHtml(candidate.status)}">${escapeHtml(label(candidate.status))}</span>
    </div>
    <p class="test-name">${escapeHtml(candidate.test)}</p>
    <div class="evidence-pills">${evidenceLinks(detail, candidate.evidence)}</div>
    <form class="review-form" data-candidate-id="${escapeHtml(candidate.id)}">
      <div class="form-grid compact">
        <label>Decision
          <select name="decision">
            <option value="rejected"${decision === 'rejected' ? ' selected' : ''}>Reject as product finding</option>
            <option value="confirmed"${isConfirmed ? ' selected' : ''}>Confirm as verified finding</option>
          </select>
        </label>
        <label>Review rationale
          <input name="rationale" minlength="3" required value="${escapeHtml(review?.rationale || '')}" placeholder="Why this decision is correct">
        </label>
      </div>
      <div class="confirmed-fields"${isConfirmed ? '' : ' hidden'}>
        <div class="form-grid">
          <label>Severity
            <select name="severity">
              ${['Critical', 'Major', 'Minor'].map((item) => `<option${review?.severity === item ? ' selected' : ''}>${item}</option>`).join('')}
            </select>
          </label>
          <label>Score category
            <select name="category">
              ${['core-flows', 'reliability-error-handling', 'ux-content', 'responsive', 'accessibility-smoke', 'network-health'].map((item) => `<option value="${item}"${review?.category === item ? ' selected' : ''}>${label(item)}</option>`).join('')}
            </select>
          </label>
        </div>
        <label>Reproduction steps <small>One step per line</small>
          <textarea name="steps" rows="3" placeholder="Open the page&#10;Perform the action&#10;Observe the result">${escapeHtml((review?.steps || []).join('\n'))}</textarea>
        </label>
        <div class="form-grid">
          <label>Expected<textarea name="expected" rows="2">${escapeHtml(review?.expected || '')}</textarea></label>
          <label>Actual<textarea name="actual" rows="2">${escapeHtml(review?.actual || '')}</textarea></label>
        </div>
        <label>Recommendation<textarea name="recommendation" rows="2">${escapeHtml(review?.recommendation || '')}</textarea></label>
      </div>
      <div class="review-actions">
        <span>${review ? `Saved ${escapeHtml(new Date(review.reviewed_at).toLocaleString())}` : 'Decision pending'}</span>
        <button class="secondary" type="submit">Save review</button>
      </div>
    </form>
  </article>`;
}

function statusOptions(statuses, selected) {
  return `<option value="">Choose status</option>${statuses.map((status) => `
    <option value="${escapeHtml(status)}"${selected === status ? ' selected' : ''}>${escapeHtml(status)}</option>
  `).join('')}`;
}

function reportWorkspace(detail) {
  const workspace = detail.report_workspace;
  const form = workspace.form;
  const verification = workspace.verification;
  const assessments = form.assessments.map((assessment) => `
    <article class="assessment-card" data-category="${escapeHtml(assessment.category)}">
      <div><span class="category-weight">${escapeHtml(label(assessment.category))}</span></div>
      <label>Status
        <select name="assessment-status" required>${statusOptions(workspace.assessment_statuses, assessment.status)}</select>
      </label>
      <label>Evidence-based rationale
        <textarea name="assessment-rationale" rows="3" required placeholder="What verified evidence supports this status?">${escapeHtml(assessment.rationale)}</textarea>
      </label>
    </article>
  `).join('');
  const flows = form.critical_flows.map((flow) => {
    const definition = workspace.critical_flow_definitions.find((item) => item.id === flow.id);
    return `<article class="flow-card" data-flow-id="${escapeHtml(flow.id)}" data-flow-name="${escapeHtml(flow.name)}">
      <div><span class="candidate-id">${escapeHtml(flow.id)}</span><h4>${escapeHtml(flow.name)}</h4><p>${escapeHtml(definition?.description || '')}</p></div>
      <label>Status
        <select name="flow-status" required>${statusOptions(workspace.assessment_statuses, flow.status)}</select>
      </label>
      <label>Verified evidence
        <textarea name="flow-evidence" rows="2" required placeholder="Test result, evidence file, or manual observation">${escapeHtml(flow.evidence)}</textarea>
      </label>
    </article>`;
  }).join('');
  const checks = verification?.automated_checks?.map((check) => `
    <li><span class="check-mark">✓</span><div><strong>${escapeHtml(check.name)}</strong><small>${escapeHtml(check.detail)}</small></div></li>
  `).join('') || '';
  const pages = verification?.pages?.map((page, index) => `
    <a class="page-preview" href="${escapeHtml(page.url)}" target="_blank" rel="noopener">
      <img src="${escapeHtml(page.url)}" alt="Rendered PDF page ${index + 1}">
      <span>Page ${index + 1}</span>
    </a>
  `).join('') || '';
  const outputLabel = verification?.current ? 'Current generated report' : 'Previous report · inputs changed';
  const outputs = verification ? `
    <div class="generated-output${verification.current ? '' : ' stale-output'}">
      <div><small>${escapeHtml(outputLabel)}</small><strong>${verification.score ?? 'Not published'}${verification.score === null ? '' : ' / 100'} · ${escapeHtml(label(verification.recommendation))}</strong></div>
      <div class="report-links">
        <a href="${escapeHtml(verification.html_url)}" target="_blank" rel="noopener">Open HTML report</a>
        <a href="${escapeHtml(verification.pdf_url)}" target="_blank" rel="noopener">Open PDF report</a>
      </div>
    </div>
    <ul class="verification-checks">${checks}</ul>
    <div class="page-grid">${pages}</div>
  ` : '<p class="muted">No final report has been generated from this workspace yet.</p>';
  const visualApproval = workspace.can_approve_visual ? `
    <form id="visual-review-form" class="visual-review-form">
      <label>Visual review note
        <textarea name="rationale" rows="2" minlength="3" required placeholder="I inspected every rendered page for clipping, overflow, broken tables, and unreadable content."></textarea>
      </label>
      <button class="primary" type="submit">Approve visually verified report</button>
    </form>
  ` : verification?.status === 'verified' && verification.current ? `
    <div class="visual-approved"><strong>Visual review approved</strong><p>${escapeHtml(verification.visual_review_rationale)}</p></div>
  ` : '';

  return `<div class="detail-section report-workspace">
    <div class="section-heading"><div><p class="eyebrow">VERIFIED REPORT WORKSPACE</p><h3>Turn evidence into a launch decision</h3></div><span class="workspace-state ${escapeHtml(workspace.status)}">${escapeHtml(label(workspace.status))}</span></div>
    <section class="workspace-gate ${escapeHtml(workspace.status)}"><strong>${escapeHtml(workspace.reason)}</strong><p>Scores are deterministic. Every assessment and finding remains tied to a human-reviewed input.</p></section>
    <form id="report-workspace-form">
      <div class="form-grid">
        <label>Report title
          <input name="title" minlength="3" maxlength="200" required value="${escapeHtml(form.title)}">
        </label>
        <label>Audit date
          <input value="${escapeHtml(new Date(detail.audit.finished_at).toLocaleDateString())}" disabled>
        </label>
      </div>
      <label>Executive summary
        <textarea name="executive-summary" rows="4" minlength="20" maxlength="5000" required placeholder="Summarize launch risk, verified strengths, and the recommended decision.">${escapeHtml(form.executive_summary)}</textarea>
      </label>
      <div class="workspace-subheading"><h4>Category assessments</h4><span>PASS = full weight · WARNING = half · FAIL = zero</span></div>
      <div class="assessment-grid">${assessments}</div>
      <div class="workspace-subheading"><h4>Critical flows</h4><span>A failed critical flow forces DO NOT LAUNCH</span></div>
      <div class="flow-list">${flows}</div>
      <div class="form-grid">
        <label>Limitations <small>One item per line</small>
          <textarea name="limitations" rows="4" required placeholder="What was outside the verified scope?">${escapeHtml(form.limitations.join('\n'))}</textarea>
        </label>
        <label>Allowlisted network / console observations <small>Optional, one per line</small>
          <textarea name="observations" rows="4" placeholder="Known harmless third-party noise">${escapeHtml(form.allowlisted_observations.join('\n'))}</textarea>
        </label>
      </div>
      <div class="workspace-actions">
        <span>${workspace.saved ? 'Workspace inputs saved locally.' : 'Save complete inputs before generating.'}</span>
        <button class="secondary" type="submit">Save report inputs</button>
      </div>
    </form>
    <div class="generation-panel">
      <div class="generation-heading"><div><small>FINAL OUTPUT</small><h4>HTML + PDF verification</h4></div><button id="generate-report" class="primary compact-button" type="button"${workspace.can_generate ? '' : ' disabled'}>${verification?.current ? 'Regenerate report' : 'Generate report'}</button></div>
      ${outputs}
      ${visualApproval}
    </div>
  </div>`;
}

function renderDetail(detail) {
  const audit = detail.audit;
  const summary = detail.review;
  document.querySelector('#review-empty').hidden = true;
  const target = document.querySelector('#review-detail');
  target.hidden = false;
  const candidates = detail.candidates.length
    ? detail.candidates.map((candidate) => reviewForm(detail, candidate)).join('')
    : '<div class="clear-state"><strong>No candidate findings</strong><p>The automation run completed without persistent or flaky failures.</p></div>';
  const evidence = detail.evidence.map((record) => `<article class="evidence-group">
    <div><strong>${escapeHtml(record.profile)}</strong><small>${escapeHtml(record.run_id)}</small></div>
    <div class="evidence-pills">${record.files.map((file) => `<a class="evidence-pill" href="${escapeHtml(file.url)}" target="_blank" rel="noopener">${escapeHtml(file.kind)} · ${escapeHtml(file.name)}</a>`).join('')}</div>
  </article>`).join('');
  target.innerHTML = `
    <div class="detail-header">
      <div><p class="eyebrow">${escapeHtml(audit.environment)}</p><h3>${escapeHtml(audit.project)}</h3><p>${escapeHtml(audit.audit_id)}</p></div>
      <span class="status large ${escapeHtml(audit.status)}">${escapeHtml(label(audit.status))}</span>
    </div>
    <div class="detail-metrics">
      <article><strong>${audit.passed_tests}/${audit.total_tests}</strong><span>tests passed</span></article>
      <article><strong>${audit.persistent_failures}</strong><span>persistent failures</span></article>
      <article><strong>${audit.flaky_tests}</strong><span>flaky tests</span></article>
      <article><strong>${summary.pending}</strong><span>review decisions pending</span></article>
    </div>
    <section class="gate ${escapeHtml(summary.report_gate)}">
      <div><small>FINAL REPORT GATE</small><strong>${summary.report_gate === 'open' ? 'Review complete' : 'Blocked'}</strong></div>
      <p>${escapeHtml(summary.report_gate_reason)}</p>
      <div class="report-links">${detail.reports.map((file) => `<a href="${escapeHtml(file.url)}" target="_blank" rel="noopener">Open ${escapeHtml(file.name.endsWith('.pdf') ? 'PDF' : 'HTML')} draft</a>`).join('')}</div>
    </section>
    <div class="detail-section"><div class="section-heading"><h3>Browser profiles</h3><span>${detail.profiles.length} profiles</span></div>
      <div class="table-wrap"><table><thead><tr><th>Profile</th><th>Status</th><th>Attempts</th><th>Passed</th><th>Persistent</th><th>Flaky</th><th>API passed</th></tr></thead><tbody>${profileRows(detail.profiles)}</tbody></table></div>
    </div>
    ${audit.api_checks.length ? `<div class="detail-section"><div class="section-heading"><h3>API contract and workflow checks</h3><span>${audit.api_checks.length} checks</span></div>
      <div class="table-wrap"><table><thead><tr><th>Check</th><th>Method</th><th>Path</th><th>Outcome</th><th>Status</th><th>Latency / budget</th><th>Schema</th><th>Evidence</th></tr></thead><tbody>${apiRows(audit.api_checks)}</tbody></table></div>
    </div>` : ''}
    <div class="detail-section"><div class="section-heading"><h3>Candidate review</h3><span>${summary.confirmed} confirmed · ${summary.rejected} rejected · ${summary.pending} pending</span></div>${candidates}</div>
    <div class="detail-section"><div class="section-heading"><h3>Evidence index</h3><span>Read-only</span></div>${evidence || '<p class="muted">No retained evidence files.</p>'}</div>
    ${reportWorkspace(detail)}
  `;
  target.querySelectorAll('.review-form').forEach((form) => {
    const decision = form.querySelector('[name="decision"]');
    decision.addEventListener('change', () => {
      form.querySelector('.confirmed-fields').hidden = decision.value !== 'confirmed';
    });
    form.addEventListener('submit', saveReview);
  });
  target.querySelector('#report-workspace-form').addEventListener('submit', saveReportWorkspace);
  target.querySelector('#generate-report').addEventListener('click', generateReport);
  target.querySelector('#visual-review-form')?.addEventListener('submit', approveVisualReport);
}

async function loadAudit(auditId) {
  state.selectedAuditId = auditId;
  renderAuditList();
  const target = document.querySelector('#review-detail');
  target.hidden = false;
  target.innerHTML = '<p class="muted loading">Loading audit evidence…</p>';
  try {
    const detail = await request(`/api/audits/${encodeURIComponent(auditId)}`);
    renderDetail(detail);
  } catch (error) {
    target.innerHTML = `<p class="error-message">${escapeHtml(error.message)}</p>`;
  }
}

async function saveReview(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const confirmed = data.get('decision') === 'confirmed';
  const payload = {
    candidate_id: form.dataset.candidateId,
    decision: data.get('decision'),
    rationale: data.get('rationale'),
    severity: confirmed ? data.get('severity') : null,
    category: confirmed ? data.get('category') : null,
    expected: confirmed ? data.get('expected') : null,
    actual: confirmed ? data.get('actual') : null,
    recommendation: confirmed ? data.get('recommendation') : null,
    steps: confirmed ? String(data.get('steps')).split('\n').map((item) => item.trim()).filter(Boolean) : [],
  };
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await request(`/api/audits/${encodeURIComponent(state.selectedAuditId)}/reviews`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-AI-QA-Token': token },
      body: JSON.stringify(payload),
    });
    showToast('Review decision saved.');
    await refreshState();
    await loadAudit(state.selectedAuditId);
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    button.disabled = false;
  }
}

const lines = (value) => String(value).split('\n').map((item) => item.trim()).filter(Boolean);

async function saveReportWorkspace(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const assessments = [...form.querySelectorAll('.assessment-card')].map((card) => ({
    category: card.dataset.category,
    status: card.querySelector('[name="assessment-status"]').value,
    rationale: card.querySelector('[name="assessment-rationale"]').value,
  }));
  const criticalFlows = [...form.querySelectorAll('.flow-card')].map((card) => ({
    id: card.dataset.flowId,
    name: card.dataset.flowName,
    status: card.querySelector('[name="flow-status"]').value,
    evidence: card.querySelector('[name="flow-evidence"]').value,
  }));
  const payload = {
    title: form.elements.title.value,
    executive_summary: form.elements['executive-summary'].value,
    assessments,
    critical_flows: criticalFlows,
    limitations: lines(form.elements.limitations.value),
    allowlisted_observations: lines(form.elements.observations.value),
  };
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await request(`/api/audits/${encodeURIComponent(state.selectedAuditId)}/report-workspace`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-AI-QA-Token': token },
      body: JSON.stringify(payload),
    });
    showToast('Verified report inputs saved.');
    await loadAudit(state.selectedAuditId);
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    button.disabled = false;
  }
}

async function generateReport(event) {
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = 'Verifying every page…';
  try {
    await request(`/api/audits/${encodeURIComponent(state.selectedAuditId)}/report-generation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-AI-QA-Token': token },
      body: JSON.stringify({ action: 'generate' }),
    });
    showToast('HTML and PDF passed automated verification.');
    await loadAudit(state.selectedAuditId);
  } catch (error) {
    showToast(error.message, 'error');
    button.disabled = false;
    button.textContent = 'Generate report';
  }
}

async function approveVisualReport(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await request(`/api/audits/${encodeURIComponent(state.selectedAuditId)}/visual-review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-AI-QA-Token': token },
      body: JSON.stringify({ rationale: form.elements.rationale.value }),
    });
    showToast('Final report marked visually verified.');
    await loadAudit(state.selectedAuditId);
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    button.disabled = false;
  }
}

async function startAudit() {
  const config = selectedConfiguration();
  const profiles = [...document.querySelectorAll('#profiles input:checked')].map((item) => item.value);
  if (!config || profiles.length === 0) {
    showToast('Select a configuration and at least one browser profile.', 'error');
    return;
  }
  try {
    await request('/api/audits', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-AI-QA-Token': token },
      body: JSON.stringify({ config_path: config.path, profiles }),
    });
    showToast('Audit started. Results will appear here automatically.');
    await refreshState();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

async function refreshState() {
  Object.assign(state, await request('/api/state'));
  renderShell();
  const job = state.jobs[0];
  const active = job && ['queued', 'running'].includes(job.status);
  window.clearTimeout(pollTimer);
  if (active) {
    pollTimer = window.setTimeout(refreshState, 1500);
  } else if (job?.status === 'completed' && job.audit_id && state.selectedAuditId !== job.audit_id) {
    loadAudit(job.audit_id);
  }
}

document.querySelector('#config-select').addEventListener('change', renderProfiles);
document.querySelector('#run-audit').addEventListener('click', startAudit);
refreshState().catch((error) => {
  document.querySelector('#audit-list').innerHTML = `<p class="error-message">${escapeHtml(error.message)}</p>`;
});
