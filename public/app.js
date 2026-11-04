/**
 * FixPilot AI · Frontend Application Controller
 * Connects UI to REST API and provides full evidence-guided troubleshooting experience.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Application State
  const state = {
    currentPlan: null,
    scenarios: [],
    manuals: [],
    auditCount: 0
  };

  // DOM Elements
  const form = document.getElementById("troubleshooting-form");
  const machineSelect = document.getElementById("machine-select");
  const errorCodeInput = document.getElementById("error-code-input");
  const queryInput = document.getElementById("query-input");
  const btnDiagnose = document.getElementById("btn-diagnose");

  const planLoading = document.getElementById("plan-loading");
  const planEmpty = document.getElementById("plan-empty");
  const planContent = document.getElementById("plan-content");

  const planIdLabel = document.getElementById("plan-id-label");
  const planMachineTitle = document.getElementById("plan-machine-title");
  const planQueryDisplay = document.getElementById("plan-query-display");
  const badgeUncertainty = document.getElementById("badge-uncertainty");
  const confidencePercentage = document.getElementById("confidence-percentage");
  const planLotoAdvisory = document.getElementById("plan-loto-advisory");
  const lotoText = document.getElementById("loto-text");

  const factsList = document.getElementById("facts-list");
  const hypothesesList = document.getElementById("hypotheses-list");
  const recommendedChecksList = document.getElementById("recommended-checks-list");
  const checksCountBadge = document.getElementById("checks-count-badge");
  const citationsList = document.getElementById("citations-list");

  // Review Gate elements
  const reviewStatusBadge = document.getElementById("review-status-badge");
  const techSigner = document.getElementById("tech-signer");
  const techDecisionNotes = document.getElementById("tech-decision-notes");
  const btnApproveCheck = document.getElementById("btn-approve-check");
  const btnMarkInconclusive = document.getElementById("btn-mark-inconclusive");
  const btnEscalateOem = document.getElementById("btn-escalate-oem");
  const btnResolveFault = document.getElementById("btn-resolve-fault");

  // Alert Banner
  const safetyAlertBanner = document.getElementById("safety-alert-banner");
  const alertBannerText = document.getElementById("alert-banner-text");
  const alertBannerClose = document.getElementById("alert-banner-close");

  // Modals & Drawers
  const modalBenchmark = document.getElementById("modal-benchmark");
  const btnOpenBenchmark = document.getElementById("btn-open-benchmark");
  const btnCloseBenchmark = document.getElementById("btn-close-benchmark");
  const btnDismissBenchmark = document.getElementById("btn-dismiss-benchmark");
  const btnRerunBenchmark = document.getElementById("btn-rerun-benchmark");

  const modalManuals = document.getElementById("modal-manuals");
  const btnOpenManuals = document.getElementById("btn-open-manuals");
  const btnCloseManuals = document.getElementById("btn-close-manuals");
  const btnDismissManuals = document.getElementById("btn-dismiss-manuals");

  const modalAudit = document.getElementById("modal-audit");
  const btnOpenAudit = document.getElementById("btn-open-audit");
  const btnCloseAudit = document.getElementById("btn-close-audit");
  const btnDismissAudit = document.getElementById("btn-dismiss-audit");
  const auditCountEl = document.getElementById("audit-count");

  const drawerEvidence = document.getElementById("drawer-evidence");
  const btnCloseDrawer = document.getElementById("btn-close-drawer");
  const drawerCitationTitle = document.getElementById("drawer-citation-title");
  const drawerCitationSource = document.getElementById("drawer-citation-source");
  const drawerCitationContent = document.getElementById("drawer-citation-content");
  const drawerCitationMeta = document.getElementById("drawer-citation-meta");

  // ==========================================
  // INITIAL DATA LOADING
  // ==========================================
  async function init() {
    try {
      // 1. Fetch system status
      const statusRes = await fetch("/api/status");
      const statusData = await statusRes.json();
      console.log("FixPilot AI Online:", statusData);

      // 2. Fetch scenarios
      const scenRes = await fetch("/api/scenarios");
      state.scenarios = await scenRes.json();

      // 3. Fetch manuals
      const manRes = await fetch("/api/manuals");
      state.manuals = await manRes.json();

      // 4. Update audit count
      await refreshAuditCount();

      // Setup simulated preset buttons
      setupPresetButtons();
    } catch (err) {
      console.error("Initialization error:", err);
    }
  }

  async function refreshAuditCount() {
    try {
      const res = await fetch("/api/audit-log");
      const data = await res.json();
      const count = data.audit_trail ? data.audit_trail.length : 0;
      state.auditCount = count;
      if (auditCountEl) auditCountEl.textContent = count;
    } catch (err) {
      console.error("Failed to refresh audit count:", err);
    }
  }

  // ==========================================
  // PRESET SIMULATED FAULTS (SLIDE 5 & 6)
  // ==========================================
  function setupPresetButtons() {
    const presetButtons = document.querySelectorAll(".preset-btn");
    presetButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const scenId = btn.getAttribute("data-scenario");
        const scen = state.scenarios.find(s => s.scenario_id === scenId);
        if (scen) {
          machineSelect.value = scen.machine_model || "";
          errorCodeInput.value = scen.error_code || "";
          queryInput.value = scen.reported_symptoms || "";
          // Automatically trigger diagnosis
          executeDiagnosis();
        }
      });
    });
  }

  // ==========================================
  // DIAGNOSIS PIPELINE
  // ==========================================
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    executeDiagnosis();
  });

  async function executeDiagnosis() {
    const rawQuery = queryInput.value.trim();
    const errCode = errorCodeInput.value.trim();
    const machine = machineSelect.value;

    let fullQuery = rawQuery;
    if (errCode && !rawQuery.toLowerCase().includes(errCode.toLowerCase())) {
      fullQuery = `[Fault ${errCode}] ${rawQuery}`;
    }

    if (!fullQuery) return;

    // Show loading state
    planEmpty.classList.add("hidden");
    planContent.classList.add("hidden");
    planLoading.classList.remove("hidden");
    safetyAlertBanner.classList.add("hidden");

    try {
      const res = await fetch("/api/diagnose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: fullQuery, machine_model: machine })
      });

      const plan = await res.json();
      state.currentPlan = plan;
      renderDiagnosticPlan(plan);
    } catch (err) {
      console.error("Diagnosis request failed:", err);
      alert("Failed to connect to FixPilot reasoning server.");
    } finally {
      planLoading.classList.add("hidden");
    }
  }

  function renderDiagnosticPlan(plan) {
    planContent.classList.remove("hidden");

    // Header info
    planIdLabel.textContent = plan.plan_id;
    planMachineTitle.textContent = `${plan.machine_model} · ${plan.error_code || 'Diagnostic'}`;
    planQueryDisplay.textContent = `"${plan.query}"`;

    // Confidence and Uncertainty Badge
    const unc = plan.uncertainty_level;
    badgeUncertainty.textContent = unc.replace("_", " ");
    badgeUncertainty.className = "badge-uncertainty";

    if (unc === "HIGH_CONFIDENCE") {
      badgeUncertainty.classList.add("high");
    } else if (unc === "MEDIUM_HYPOTHESIS") {
      badgeUncertainty.classList.add("medium");
    } else if (unc === "UNSAFE_REJECTED") {
      badgeUncertainty.classList.add("unsafe");
    } else {
      badgeUncertainty.classList.add("low");
    }

    confidencePercentage.textContent = `${Math.round(plan.confidence_score * 100)}%`;

    // Safety Banner & LOTO
    if (plan.safety) {
      if (plan.safety.blocked) {
        safetyAlertBanner.classList.remove("hidden");
        alertBannerText.textContent = plan.safety.warning_message;
      }
      if (plan.safety.loto_required) {
        planLotoAdvisory.classList.remove("hidden");
        lotoText.textContent = plan.safety.required_precautions[0] || "OSHA Lockout/Tagout protocol mandatory.";
      } else {
        planLotoAdvisory.classList.add("hidden");
      }
    }

    // 1. Facts Rendering (OEM Grounded)
    factsList.innerHTML = "";
    if (plan.facts && plan.facts.length > 0) {
      plan.facts.forEach(fact => {
        const li = document.createElement("li");
        li.textContent = fact;
        factsList.appendChild(li);
      });
    } else {
      factsList.innerHTML = "<li>No direct factual statements matched in approved documentation.</li>";
    }

    // 2. Hypotheses Rendering (Facts Stay Separate from Hypotheses)
    hypothesesList.innerHTML = "";
    if (plan.hypotheses && plan.hypotheses.length > 0) {
      plan.hypotheses.forEach(h => {
        const card = document.createElement("div");
        card.className = "hypo-card";
        card.innerHTML = `
          <div class="hypo-header">
            <span class="hypo-title">${h.cause}</span>
            <span class="hypo-prob">${Math.round(h.probability * 100)}% Probability</span>
          </div>
          <div class="hypo-summary">${h.evidence_summary}</div>
        `;
        hypothesesList.appendChild(card);
      });
    } else if (plan.safety && plan.safety.blocked) {
      hypothesesList.innerHTML = `
        <div class="hypo-card" style="border-color: var(--rose-danger);">
          <div class="hypo-header">
            <span class="hypo-title" style="color: var(--rose-danger);">Safety Trip Active</span>
            <span class="hypo-prob">BLOCKED</span>
          </div>
          <div class="hypo-summary">Hypothesis generation suspended due to critical safety interlock violation.</div>
        </div>
      `;
    }

    // 3. Recommended Checks Rendering (Ordered steps with citations)
    recommendedChecksList.innerHTML = "";
    checksCountBadge.textContent = `${plan.recommended_checks.length} Steps`;

    plan.recommended_checks.forEach(check => {
      const card = document.createElement("div");
      card.className = "check-item-card";

      let citationHtml = "";
      if (check.citation) {
        citationHtml = `
          <button class="citation-pill" data-anchor="${check.citation.anchor_id}">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
            ${check.citation.section_id} (p. ${check.citation.page_number})
          </button>
        `;
      }

      card.innerHTML = `
        <div class="check-num-badge">${check.step_number}</div>
        <div class="check-content-col">
          <div class="check-action-text">${check.action}</div>
          <div class="check-expected-row">
            <span class="check-expected-label">Expected:</span> ${check.expected_outcome}
          </div>
          <div class="check-method-tag">
            <span>🔧 Method:</span> ${check.verification_method || 'Visual / Instrument'}
          </div>
        </div>
        <div class="check-meta-col">
          <span class="risk-badge risk-${check.risk_level}">${check.risk_level} RISK</span>
          ${citationHtml}
        </div>
      `;
      recommendedChecksList.appendChild(card);
    });

    // Attach citation pill click listeners
    attachCitationListeners();

    // 4. Evidence Shelf (Ranked Passages)
    citationsList.innerHTML = "";
    if (plan.citations && plan.citations.length > 0) {
      plan.citations.forEach(cit => {
        const card = document.createElement("div");
        card.className = "citation-card";
        card.setAttribute("data-anchor", cit.anchor_id);
        card.innerHTML = `
          <div class="cit-card-header">
            <span>${cit.section_id} · ${cit.section_title}</span>
            <span>Match ${cit.relevance_score}</span>
          </div>
          <div class="cit-card-excerpt">${cit.excerpt}</div>
        `;
        card.addEventListener("click", () => openEvidenceDrawer(cit));
        citationsList.appendChild(card);
      });
    } else {
      citationsList.innerHTML = "<div style='font-size:12px;color:var(--text-muted);'>No direct manual citations available for this query.</div>";
    }

    // Reset Review Gate UI
    updateReviewGateUI(plan.review_status);
  }

  function attachCitationListeners() {
    const pills = document.querySelectorAll(".citation-pill");
    pills.forEach(pill => {
      pill.addEventListener("click", () => {
        const anchor = pill.getAttribute("data-anchor");
        if (state.currentPlan && state.currentPlan.citations) {
          const cit = state.currentPlan.citations.find(c => c.anchor_id === anchor);
          if (cit) {
            openEvidenceDrawer(cit);
          }
        }
      });
    });
  }

  function openEvidenceDrawer(citation) {
    drawerCitationTitle.textContent = `${citation.section_id} · ${citation.section_title}`;
    drawerCitationSource.textContent = `${citation.manual_title} (Page ${citation.page_number})`;
    drawerCitationContent.textContent = citation.excerpt;
    drawerCitationMeta.innerHTML = `
      <div><strong>Relevance Score:</strong> ${citation.relevance_score}</div>
      <div><strong>Status:</strong> Approved Factory Maintenance Documentation</div>
      <div><strong>Anchor ID:</strong> <code>${citation.anchor_id}</code></div>
    `;
    drawerEvidence.classList.remove("hidden");
  }

  btnCloseDrawer.addEventListener("click", () => {
    drawerEvidence.classList.add("hidden");
  });

  alertBannerClose.addEventListener("click", () => {
    safetyAlertBanner.classList.add("hidden");
  });

  // ==========================================
  // TECHNICIAN REVIEW GATE ACTIONS (SLIDE 3)
  // ==========================================
  function updateReviewGateUI(status) {
    if (status === "APPROVED_EXECUTED") {
      reviewStatusBadge.textContent = "CHECK 1 EXECUTED & VERIFIED";
      reviewStatusBadge.className = "badge-gate-approved";
    } else if (status === "RESOLVED") {
      reviewStatusBadge.textContent = "FAULT RESOLVED · PRODUCTION RELEASED";
      reviewStatusBadge.className = "badge-gate-approved";
    } else if (status === "ESCALATED_OEM") {
      reviewStatusBadge.textContent = "ESCALATED TO OEM SERVICE";
      reviewStatusBadge.className = "badge-uncertainty unsafe";
    } else if (status === "INCONCLUSIVE") {
      reviewStatusBadge.textContent = "CHECK INCONCLUSIVE · NEXT STEP REQUIRED";
      reviewStatusBadge.className = "badge-uncertainty medium";
    } else {
      reviewStatusBadge.textContent = "AWAITING TECHNICIAN SIGN-OFF";
      reviewStatusBadge.className = "badge-gate-pending";
    }
  }

  async function handleReviewDecision(status, actionDesc) {
    if (!state.currentPlan) {
      alert("No active plan to review.");
      return;
    }

    const tech = techSigner.value.trim() || "Arjun (Lead Tech)";
    const notes = techDecisionNotes.value.trim() || actionDesc;

    try {
      const res = await fetch("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_id: state.currentPlan.plan_id,
          technician_id: tech,
          status: status,
          action_taken: actionDesc,
          notes: notes
        })
      });

      const decision = await res.json();
      state.currentPlan.review_status = status;
      updateReviewGateUI(status);
      await refreshAuditCount();
      alert(`Decision Recorded: ${actionDesc} logged in maintenance audit trail.`);
    } catch (err) {
      console.error("Failed to submit review decision:", err);
      alert("Error submitting decision to review gate.");
    }
  }

  btnApproveCheck.addEventListener("click", () => {
    handleReviewDecision("APPROVED_EXECUTED", "Technician executed and verified Check 1 per approved manual.");
  });

  btnMarkInconclusive.addEventListener("click", () => {
    handleReviewDecision("INCONCLUSIVE", "Check 1 completed but anomaly persists. Technician advancing to Step 2.");
  });

  btnEscalateOem.addEventListener("click", () => {
    handleReviewDecision("ESCALATED_OEM", "Fault symptoms exceed standard maintenance scope; escalated to OEM Technical Support.");
  });

  btnResolveFault.addEventListener("click", () => {
    handleReviewDecision("RESOLVED", "Root cause rectified, machine cleared for production, downtime resolved.");
  });

  // ==========================================
  // PILOT BENCHMARK MODAL (SLIDE 6 VERIFICATION)
  // ==========================================
  btnOpenBenchmark.addEventListener("click", async () => {
    modalBenchmark.classList.remove("hidden");
    await runBenchmarkInModal();
  });

  btnCloseBenchmark.addEventListener("click", () => modalBenchmark.classList.add("hidden"));
  btnDismissBenchmark.addEventListener("click", () => modalBenchmark.classList.add("hidden"));
  btnRerunBenchmark.addEventListener("click", runBenchmarkInModal);

  async function runBenchmarkInModal() {
    const tbody = document.getElementById("benchmark-tbody");
    tbody.innerHTML = "<tr><td colspan='6' style='text-align:center;padding:24px;'>Running automated verification across simulated scenarios...</td></tr>";

    try {
      const res = await fetch("/api/benchmark");
      const bench = await res.json();

      document.getElementById("stat-citations").textContent = `${bench.summary.citation_support_pct}%`;
      document.getElementById("stat-retrieval").textContent = `${bench.summary.retrieval_correctness_pct}%`;
      document.getElementById("stat-time").textContent = `${bench.summary.estimated_minutes_saved_per_fault}m`;
      document.getElementById("stat-escalation").textContent = `${bench.summary.escalation_safety_catch_pct}%`;

      tbody.innerHTML = "";
      bench.detailed_results.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><code>${row.scenario_id}</code></td>
          <td><strong>${row.machine}</strong><br><small style="color:var(--text-muted);">${row.title}</small></td>
          <td><span class="${row.retrieval_correct ? 'text-green' : 'text-yellow'}">● ${row.retrieval_correct ? 'PASS' : 'WARN'}</span></td>
          <td>${row.citation_count} passages</td>
          <td>${row.safety_blocked ? '<span class="text-green">BLOCKED (Safe)</span>' : '<span style="color:var(--text-muted);">Normal</span>'}</td>
          <td><code>${row.elapsed_seconds}s</code></td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error("Benchmark failed:", err);
      tbody.innerHTML = "<tr><td colspan='6' style='text-align:center;color:var(--rose-danger);'>Failed to run benchmark.</td></tr>";
    }
  }

  // ==========================================
  // APPROVED MANUALS BROWSER MODAL
  // ==========================================
  btnOpenManuals.addEventListener("click", async () => {
    modalManuals.classList.remove("hidden");
    await renderManualsBrowser();
  });

  btnCloseManuals.addEventListener("click", () => modalManuals.classList.add("hidden"));
  btnDismissManuals.addEventListener("click", () => modalManuals.classList.add("hidden"));

  async function renderManualsBrowser() {
    const tree = document.getElementById("manuals-tree");
    const viewer = document.getElementById("manual-content-view");
    tree.innerHTML = "<div style='color:var(--text-muted);'>Loading manuals...</div>";

    try {
      const res = await fetch("/api/manuals");
      const manuals = await res.json();
      tree.innerHTML = "";

      manuals.forEach(m => {
        const group = document.createElement("div");
        group.className = "manual-group";
        group.innerHTML = `
          <div class="manual-item-header">📖 ${m.title}</div>
          <div class="manual-sections-sub">
            ${m.sections.map(s => `<a class="manual-sec-link" data-manual="${m.manual_id}" data-sec="${s.section_id}">${s.section_id} · ${s.title} (p.${s.page})</a>`).join("")}
          </div>
        `;
        tree.appendChild(group);
      });

      // Click handler for sections
      const links = tree.querySelectorAll(".manual-sec-link");
      links.forEach(l => {
        l.addEventListener("click", async () => {
          links.forEach(other => other.classList.remove("active"));
          l.classList.add("active");
          const mId = l.getAttribute("data-manual");
          const sId = l.getAttribute("data-sec");
          await loadSectionDetail(mId, sId);
        });
      });

      if (manuals.length > 0 && manuals[0].sections.length > 0) {
        await loadSectionDetail(manuals[0].manual_id, manuals[0].sections[0].section_id);
      }
    } catch (err) {
      console.error("Failed to load manuals:", err);
    }
  }

  async function loadSectionDetail(manualId, sectionId) {
    const viewer = document.getElementById("manual-content-view");
    viewer.innerHTML = "<div>Loading section...</div>";

    try {
      const res = await fetch(`/api/manuals/${manualId}`);
      const manual = await res.json();
      const sec = manual.sections.find(s => s.section_id === sectionId);

      if (!sec) {
        viewer.innerHTML = "<div>Section not found.</div>";
        return;
      }

      viewer.innerHTML = `
        <div class="manual-content-view-sec">
          <div class="cit-card-header">${manual.title} · Version ${manual.version} · Approved ${manual.approval_date}</div>
          <h3 class="manual-sec-heading">${sec.section_id} · ${sec.title} (Page ${sec.page_number})</h3>
          <p class="manual-sec-text">${sec.content}</p>
          <h4 style="font-size:13px;font-weight:700;margin:16px 0 8px 0;color:#93c5fd;">Indexed Passages & Citations:</h4>
          ${sec.passages.map(p => `
            <div class="manual-passage-box">
              <div style="font-size:11px;font-weight:700;color:var(--blue-primary);margin-bottom:4px;">ID: ${p.passage_id}</div>
              <div>${p.content}</div>
              ${p.safety_warnings.length > 0 ? `<div style="color:var(--amber-warn);font-size:11px;margin-top:6px;">⚠️ ${p.safety_warnings.join(" | ")}</div>` : ''}
            </div>
          `).join("")}
        </div>
      `;
    } catch (err) {
      console.error("Error loading section detail:", err);
    }
  }

  // ==========================================
  // AUDIT TRAIL MODAL
  // ==========================================
  btnOpenAudit.addEventListener("click", async () => {
    modalAudit.classList.remove("hidden");
    await renderAuditModal();
  });

  btnCloseAudit.addEventListener("click", () => modalAudit.classList.add("hidden"));
  btnDismissAudit.addEventListener("click", () => modalAudit.classList.add("hidden"));

  async function renderAuditModal() {
    const statsRow = document.getElementById("audit-stats-summary");
    const listEl = document.getElementById("audit-list-container");
    listEl.innerHTML = "<div>Loading audit trail...</div>";

    try {
      const res = await fetch("/api/audit-log");
      const data = await res.json();

      statsRow.innerHTML = `
        <div class="audit-stat-card"><div class="audit-stat-num text-blue">${data.stats.total_decisions}</div><div class="audit-stat-label">Total Decisions</div></div>
        <div class="audit-stat-card"><div class="audit-stat-num text-green">${data.stats.approved_count}</div><div class="audit-stat-label">Executed & Verified</div></div>
        <div class="audit-stat-card"><div class="audit-stat-num text-purple">${data.stats.resolved_count}</div><div class="audit-stat-label">Resolved</div></div>
        <div class="audit-stat-card"><div class="audit-stat-num text-yellow">${data.stats.escalated_count}</div><div class="audit-stat-label">Escalated OEM</div></div>
        <div class="audit-stat-card"><div class="audit-stat-num text-blue">${data.stats.avg_time_to_decision_sec}s</div><div class="audit-stat-label">Avg Review Time</div></div>
      `;

      listEl.innerHTML = "";
      if (!data.audit_trail || data.audit_trail.length === 0) {
        listEl.innerHTML = "<div style='color:var(--text-muted);text-align:center;padding:20px;'>No decisions recorded yet. Test a scenario and submit a review decision!</div>";
        return;
      }

      data.audit_trail.forEach(d => {
        const item = document.createElement("div");
        item.className = "audit-item";
        const dateStr = new Date(d.timestamp * 1000).toLocaleTimeString();
        item.innerHTML = `
          <div class="audit-item-info">
            <div class="audit-action-title">${d.action_taken}</div>
            <div class="audit-meta-text">By ${d.technician_id} · Plan: <code>${d.plan_id}</code> · Notes: "${d.notes || 'None'}"</div>
          </div>
          <div style="text-align:right;">
            <span class="badge-mini" style="font-weight:700;">${d.status}</span>
            <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">${dateStr} (${d.resolution_time_seconds}s)</div>
          </div>
        `;
        listEl.appendChild(item);
      });
    } catch (err) {
      console.error("Failed to load audit trail:", err);
    }
  }

  // Boot the app
  init();
});
