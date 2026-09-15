/**
 * Promise Ledger Dashboard Application Logic
 * B2B Receivables Recovery & Risk Management
 */

// Application state
const appState = {
    portfolio: null,
    experiment: null,
    opportunities: [],
    selectedPromiseId: null,
    selectedOpportunity: null,
    evaluationsByPromiseId: {},
    isLoading: false,
    error: null,
    refreshInterval: null
};

/**
 * Initialize the application
 */
async function initApp() {
    console.log('Initializing Promise Ledger Dashboard...');

    // Initialize API client
    initializeAPIClient();

    // Check backend health
    await checkHealth();

    // Load initial data
    await loadPortfolioData();

    // Set up event listeners
    setupEventListeners();

    // Auto-refresh data every 30 seconds
    appState.refreshInterval = setInterval(loadPortfolioData, 30000);
}

/**
 * Check backend health status
 */
async function checkHealth() {
    const healthIndicator = document.getElementById('healthIndicator');
    const statusDot = document.getElementById('statusDot');
    const healthStatus = document.getElementById('healthStatus');

    try {
        const api = getAPIClient();
        const health = await api.getHealth();

        if (health.status === 'ok') {
            statusDot.classList.remove('error');
            statusDot.classList.add('healthy');
            healthStatus.textContent = 'Backend Connected';
            appState.error = null;
        } else {
            throw new Error('Backend returned non-ok status');
        }
    } catch (error) {
        console.error('Health check failed:', error);
        statusDot.classList.remove('healthy');
        statusDot.classList.add('error');
        healthStatus.textContent = 'Backend Offline';
        appState.error = 'Cannot connect to backend. Please ensure the API server is running.';
        showError(appState.error);
    }
}

/**
 * Load portfolio data, experiment metrics, and opportunities
 */
async function loadPortfolioData() {
    appState.isLoading = true;

    try {
        const api = getAPIClient();

        // Fetch portfolio summary, opportunities, and experiment in parallel
        const [summary, opportunities, experiment] = await Promise.all([
            api.getPortfolioSummary(),
            api.getOpportunities(),
            api.getEvaluationExperiment().catch((err) => {
                console.warn('Experiment endpoint call fallback:', err);
                return null;
            })
        ]);

        appState.portfolio = summary;
        appState.opportunities = opportunities;
        appState.experiment = experiment || summary.experiment || null;
        appState.error = null;

        // Render all sections
        renderPortfolioMetrics();
        renderPriorityDistribution();
        renderExperimentMetrics();
        renderOpportunitiesTable();

        // On initial load, select rank 1 opportunity without auto-evaluating
        if (appState.selectedPromiseId) {
            selectOpportunity(appState.selectedPromiseId);
        } else if (opportunities && opportunities.length > 0) {
            selectOpportunity(opportunities[0].promise_id);
        }

    } catch (error) {
        console.error('Error loading portfolio data:', error);
        const statusDot = document.getElementById('statusDot');
        const healthStatus = document.getElementById('healthStatus');
        if (statusDot) {
            statusDot.classList.remove('healthy');
            statusDot.classList.add('error');
        }
        if (healthStatus) {
            healthStatus.textContent = 'Backend Unavailable';
        }
        appState.error = error.message;
        showError(`Failed to load data: ${error.message}`);
    } finally {
        appState.isLoading = false;
    }
}

/**
 * Render portfolio overview metrics
 */
function renderPortfolioMetrics() {
    if (!appState.portfolio) return;

    const p = appState.portfolio;

    // Update metric cards
    const totalOut = document.getElementById('totalOutstanding');
    if (totalOut) {
        totalOut.textContent = formatCurrency(p.total_outstanding_amount);
    }

    const expRec = document.getElementById('expectedRecovery');
    if (expRec) {
        expRec.textContent = formatCurrency(p.total_expected_recovery);
    }

    const atRisk = document.getElementById('atRiskCount');
    if (atRisk) {
        atRisk.textContent = p.evaluation_count.toLocaleString('en-IN');
    }

    const recoveryRate = p.total_outstanding_amount > 0
        ? p.total_expected_recovery / p.total_outstanding_amount
        : 0;
    const recRateEl = document.getElementById('recoveryRate');
    if (recRateEl) {
        recRateEl.textContent = formatPercentage(recoveryRate);
    }

    const yieldBar = document.getElementById('recoveryYieldBar');
    if (yieldBar) {
        const pct = Math.min(100, Math.max(0, Math.round(recoveryRate * 100)));
        yieldBar.style.width = `${pct}%`;
    }
    const yieldText = document.getElementById('recoveryYieldText');
    if (yieldText) {
        yieldText.textContent = `${formatPercentage(recoveryRate)} of total portfolio risk`;
    }
}

/**
 * Render priority tier distribution
 */
function renderPriorityDistribution() {
    if (!appState.portfolio) return;

    const tiers = appState.portfolio.priority_tiers || {};

    const highEl = document.getElementById('tierHigh');
    if (highEl) highEl.textContent = (tiers.HIGH || 0).toString();

    const medEl = document.getElementById('tierMedium');
    if (medEl) medEl.textContent = (tiers.MEDIUM || 0).toString();

    const lowEl = document.getElementById('tierLow');
    if (lowEl) lowEl.textContent = (tiers.LOW || 0).toString();
}

/**
 * Render Control vs AI Treatment evaluation experiment metrics
 */
function renderExperimentMetrics() {
    const exp = appState.experiment || (appState.portfolio && appState.portfolio.experiment);
    if (!exp) return;

    // Financials
    const ctrlAmt = document.getElementById('controlRecoveredAmount');
    if (ctrlAmt) ctrlAmt.textContent = formatCurrency(exp.control_recovered_amount);

    const ctrlRate = document.getElementById('controlRecoveryRate');
    if (ctrlRate) ctrlRate.textContent = formatPercentage(exp.control_recovery_rate);

    const treatAmt = document.getElementById('treatmentRecoveredAmount');
    if (treatAmt) treatAmt.textContent = formatCurrency(exp.treatment_recovered_amount);

    const treatRate = document.getElementById('treatmentRecoveryRate');
    if (treatRate) treatRate.textContent = formatPercentage(exp.treatment_recovery_rate);

    const incAmt = document.getElementById('incrementalRecoveryAmount');
    if (incAmt) {
        incAmt.textContent = formatCurrency(exp.incremental_recovery_amount, true);
        if (exp.incremental_recovery_amount < 0) {
            incAmt.classList.add('negative');
            incAmt.classList.remove('positive');
        } else {
            incAmt.classList.add('positive');
            incAmt.classList.remove('negative');
        }
    }

    const treatImp = document.getElementById('treatmentImprovementPercent');
    if (treatImp) {
        treatImp.textContent = formatSignedPercentage(exp.treatment_improvement_percent);
        if (exp.treatment_improvement_percent < 0) {
            treatImp.classList.add('negative-tag');
            treatImp.classList.remove('positive-tag');
        } else {
            treatImp.classList.add('positive-tag');
            treatImp.classList.remove('negative-tag');
        }
    }

    // Rates
    const autoRate = document.getElementById('automationRate');
    if (autoRate) autoRate.textContent = `${exp.automation_rate.toFixed(1)}%`;

    const humanRate = document.getElementById('humanReviewRate');
    if (humanRate) humanRate.textContent = `${exp.human_review_rate.toFixed(1)}%`;

    const stopRate = document.getElementById('stoppedRate');
    if (stopRate) stopRate.textContent = `${exp.stopped_rate.toFixed(1)}%`;

    const expDate = document.getElementById('experimentDate');
    if (expDate && exp.evaluation_date) {
        expDate.textContent = `Simulation Date: ${exp.evaluation_date}`;
    }
}

/**
 * Render opportunities table
 */
function renderOpportunitiesTable() {
    const tbody = document.getElementById('opportunitiesTableBody');
    if (!tbody) return;

    if (!appState.opportunities || appState.opportunities.length === 0) {
        tbody.innerHTML = '<tr class="loading"><td colspan="11">No at-risk opportunities found</td></tr>';
        return;
    }

    // Sort by priority rank
    const sorted = [...appState.opportunities].sort((a, b) =>
        a.priority_rank - b.priority_rank
    );

    tbody.innerHTML = sorted.map(opp => {
        const credibilityScore = Math.round(opp.promise_credibility_score);
        const breakProbability = opp.break_probability;
        const riskClass = getRiskClass(breakProbability);
        const credibilityClass = getCredibilityClass(credibilityScore);
        const isSelected = opp.promise_id === appState.selectedPromiseId;
        const hasEval = Boolean(appState.evaluationsByPromiseId[opp.promise_id]);
        const evalAction = hasEval ? appState.evaluationsByPromiseId[opp.promise_id].final_action : null;

        return `
            <tr class="${isSelected ? 'active' : ''}" data-promise-id="${opp.promise_id}">
                <td class="rank-col">#${opp.priority_rank}</td>
                <td class="promise-id">#${opp.promise_id}</td>
                <td class="cust-id">Cust #${opp.customer_id}</td>
                <td class="inv-id">Inv #${opp.invoice_id}</td>
                <td class="outstanding-amount">${formatCurrency(opp.outstanding_amount)}</td>
                <td class="recovery-amount">${formatCurrency(opp.expected_recovery)}</td>
                <td class="${riskClass}">
                    <div class="prob-cell">
                        <span class="prob-val">${formatPercentage(breakProbability)}</span>
                        <div class="mini-bar-track"><div class="mini-bar-fill ${riskClass}" style="width: ${Math.min(100, Math.round(breakProbability * 100))}%"></div></div>
                    </div>
                </td>
                <td class="${credibilityClass}">
                    <span class="cred-pill ${credibilityClass}">${credibilityScore}</span>
                </td>
                <td><span class="${getPriorityClass(opp.priority_tier)}">${opp.priority_tier}</span></td>
                <td>
                    <span class="status-pill ${hasEval ? 'paid' : 'pending'}" id="table-status-${opp.promise_id}">
                        ${hasEval ? getActionLabel(evalAction) : 'Ready to Evaluate'}
                    </span>
                </td>
                <td><button class="action-button" onclick="selectOpportunity(${opp.promise_id})">Inspect</button></td>
            </tr>
        `;
    }).join('');

    // Add click handlers to rows
    document.querySelectorAll('#opportunitiesTableBody tr').forEach(row => {
        row.addEventListener('click', (e) => {
            if (e.target.tagName !== 'BUTTON') {
                const promiseId = parseInt(row.dataset.promiseId);
                if (promiseId) {
                    selectOpportunity(promiseId);
                }
            }
        });
    });
}

/**
 * Select an opportunity and show basic risk and invoice/promise information.
 * Does NOT automatically run or present completed evaluation results.
 * @param {number} promiseId - Promise ID to select
 */
async function selectOpportunity(promiseId) {
    appState.selectedPromiseId = promiseId;

    // Update table highlighting
    document.querySelectorAll('#opportunitiesTableBody tr').forEach(row => {
        if (parseInt(row.dataset.promiseId) === promiseId) {
            row.classList.add('active');
        } else {
            row.classList.remove('active');
        }
    });

    // Load opportunity details only (do NOT auto-evaluate)
    try {
        const api = getAPIClient();
        const detail = await api.getOpportunityDetail(promiseId);
        appState.selectedOpportunity = detail;

        // Check if user already evaluated this promise in this session
        const existingEvaluation = appState.evaluationsByPromiseId[promiseId] || null;
        renderDetailPanel(detail, existingEvaluation);
    } catch (error) {
        console.error('Error loading opportunity detail:', error);
        showDetailError(`Failed to load details: ${error.message}`);
    }
}

/**
 * Render the detail panel for a selected opportunity
 * Displays basic risk, invoice, and promise information, with a primary CTA to evaluate.
 * @param {Object} detail - Opportunity detail data
 * @param {Object|null} evaluation - Existing evaluation result if previously evaluated by user
 */
function renderDetailPanel(detail, evaluation = null) {
    const panel = document.getElementById('detailPanel');
    if (!panel) return;

    const credibilityScore = Math.round(detail.promise_credibility_score);
    const breakProbability = detail.break_probability;
    const recoveryProbability = detail.recovery_probability;
    const credibilityClass = getCredibilityClass(credibilityScore);
    const riskClass = getRiskClass(breakProbability);

    let html = `
        <div class="detail-header">
            <div class="detail-title-block">
                <span class="detail-eyebrow">OPPORTUNITY AUDIT INSPECTOR</span>
                <h3>Opportunity Details</h3>
                <div class="promise-id-display">Promise ID #${detail.promise_id} • Customer #${detail.customer_id}</div>
            </div>
            <span class="${getPriorityClass(detail.priority_tier)}">${detail.priority_tier} PRIORITY</span>
        </div>

        <!-- Primary Action Callout Card -->
        <div class="evaluate-cta-card">
            <div class="cta-header">
                <span class="cta-badge">AI DECISION & REVENUE RECOVERY AGENT</span>
                <span class="cta-status-pill">${evaluation ? 'Evaluated' : 'Ready to Evaluate'}</span>
            </div>
            <p class="cta-desc">
                Execute Promise Ledger's Decision Engine and Guardrails on this promise to determine the optimal recovery action and compliance checks.
            </p>
            <button class="evaluate-button primary-cta" id="evaluateButton" onclick="evaluateOpportunity(${detail.promise_id}, event)">
                ⚡ EVALUATE & GET RECOMMENDATION
            </button>
        </div>

        <div id="evaluationResultContainer"></div>

        <!-- Key Metrics Section -->
        <div class="detail-section">
            <div class="detail-section-title">Key Metrics</div>
            <div class="detail-field">
                <span class="detail-field-label">Outstanding Amount</span>
                <span class="detail-field-value currency">${formatCurrency(detail.outstanding_amount)}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Expected Recovery</span>
                <span class="detail-field-value currency">${formatCurrency(detail.expected_recovery)}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Promise Credibility Score</span>
                <span class="detail-field-value ${credibilityClass}">${credibilityScore} / 100</span>
            </div>
            <div class="risk-progress-wrap">
                <div class="risk-progress-track">
                    <div class="risk-progress-fill ${credibilityClass}" style="width: ${Math.min(100, credibilityScore)}%"></div>
                </div>
            </div>
        </div>

        <!-- Risk Metrics Section -->
        <div class="detail-section">
            <div class="detail-section-title">Risk Assessment (probabilities)</div>
            <div class="detail-field">
                <span class="detail-field-label">Break Probability</span>
                <span class="detail-field-value ${riskClass}">${formatPercentage(breakProbability)}</span>
            </div>
            <div class="risk-progress-wrap">
                <div class="risk-progress-track">
                    <div class="risk-progress-fill ${riskClass}" style="width: ${Math.min(100, Math.round(breakProbability * 100))}%"></div>
                </div>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Recovery Probability</span>
                <span class="detail-field-value">${formatPercentage(recoveryProbability)}</span>
            </div>
            <div class="risk-progress-wrap">
                <div class="risk-progress-track">
                    <div class="risk-progress-fill recovery" style="width: ${Math.min(100, Math.round(recoveryProbability * 100))}%"></div>
                </div>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Priority Tier</span>
                <span class="detail-field-value">${detail.priority_tier}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Priority Rank</span>
                <span class="detail-field-value">#${detail.priority_rank} in portfolio</span>
            </div>
        </div>

        <!-- Promise Details Section -->
        <div class="detail-section">
            <div class="detail-section-title">Promise Information</div>
            <div class="detail-field">
                <span class="detail-field-label">Created Date</span>
                <span class="detail-field-value">${formatDate(detail.promise_created_date)}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Promise Due Date</span>
                <span class="detail-field-value">${formatDate(detail.promised_payment_date)}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Promised Amount</span>
                <span class="detail-field-value currency">${formatCurrency(detail.promised_amount)}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Outcome Status</span>
                <span class="detail-field-value status-pill ${detail.outcome ? detail.outcome.toLowerCase() : 'pending'}">${detail.outcome || 'PENDING'}</span>
            </div>
        </div>

        <!-- Invoice Details Section -->
        <div class="detail-section">
            <div class="detail-section-title">Invoice Information</div>
            <div class="detail-field">
                <span class="detail-field-label">Invoice ID</span>
                <span class="detail-field-value">#${detail.invoice_id}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Invoice Amount</span>
                <span class="detail-field-value currency">${formatCurrency(detail.invoice_amount)}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Invoice Status</span>
                <span class="detail-field-value">${detail.invoice_status}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Paid Amount</span>
                <span class="detail-field-value currency">${formatCurrency(detail.paid_amount)}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Current Outstanding</span>
                <span class="detail-field-value currency">${formatCurrency(detail.current_outstanding_amount)}</span>
            </div>
        </div>

        <!-- Explanation Section -->
        <div class="detail-explanation">
            <h4>📊 Risk Analysis Summary</h4>
            <ul class="explanation-list">
                ${detail.explanation ? detail.explanation.map(item => `<li>${item}</li>`).join('') : '<li>Statistical risk evaluation based on promise age, past broken promises, and outstanding balance.</li>'}
            </ul>
        </div>
    `;

    panel.innerHTML = html;

    // If this promise was evaluated previously in this session, show the result
    if (evaluation) {
        showEvaluationResult(evaluation);
    }
}

/**
 * Evaluate an opportunity and display the complete decision chain.
 * Shows visible "AI evaluating…" loading state without artificial delays.
 * @param {number} promiseId - Promise ID to evaluate
 */
async function evaluateOpportunity(promiseId, event) {
    const button = event ? event.currentTarget : document.getElementById('evaluateButton');
    const originalText = button ? button.innerHTML : '⚡ EVALUATE & GET RECOMMENDATION';

    try {
        if (button) {
            button.classList.add('loading');
            button.textContent = 'AI evaluating…';
            button.disabled = true;
        }

        const api = getAPIClient();
        const evaluation = await api.evaluateOpportunity(promiseId);
        appState.evaluationsByPromiseId[promiseId] = evaluation;

        // Show evaluation result with decision chain
        showEvaluationResult(evaluation);

        // Update table row status
        const statusEl = document.getElementById(`table-status-${promiseId}`);
        if (statusEl) {
            statusEl.textContent = getActionLabel(evaluation.final_action);
            statusEl.className = 'status-pill paid';
        }

    } catch (error) {
        console.error('Error evaluating opportunity:', error);
        showDetailError(`Evaluation failed: ${error.message}`);
    } finally {
        if (button) {
            button.classList.remove('loading');
            button.innerHTML = '⚡ EVALUATE & GET RECOMMENDATION';
            button.disabled = false;
        }
    }
}

/**
 * Show evaluation result in the detail panel
 * Displays the full decision chain:
 * AI Recommendation → Guardrail Outcome → Final Action → Simulated Execution → Audit ID
 * Preserves exact test labels for tests/test_frontend.js and tests/test_frontend_validation.py
 * @param {Object} evaluation - Evaluation response
 */
function showEvaluationResult(evaluation) {
    const panel = document.getElementById('detailPanel');
    if (!panel) return;

    const credibilityScore = evaluation.promise_credibility === null || evaluation.promise_credibility === undefined
        ? '--'
        : Math.round(evaluation.promise_credibility);
    const guardrailBadgeClass = getGuardrailBadgeClass(evaluation.guardrail_status);
    const isSimulated = evaluation.audit && evaluation.audit.simulated ? 'Yes' : 'No';
    const executionStatus = (evaluation.audit && evaluation.audit.execution_status) || '--';
    const auditId = (evaluation.audit && evaluation.audit.audit_id) || '--';

    const resultHtml = `
        <div class="evaluation-result">
            <div class="result-header">
                <h4>✅ Evaluation Complete</h4>
                <span class="simulated-tag">SIMULATED EXECUTION</span>
            </div>

            <!-- Decision Chain: AI Recommendation → Guardrail Outcome → Final Action → Simulated Execution → Audit ID -->
            <div class="decision-chain-container">
                <div class="decision-chain-title">Decision Chain: AI Recommendation → Guardrail Outcome → Final Action → Simulated Execution → Audit ID</div>
                <div class="decision-chain">
                    <div class="chain-node">
                        <div class="chain-node-left">
                            <span class="chain-node-num">1</span>
                            <span class="chain-node-label">AI Recommendation</span>
                        </div>
                        <span class="chain-node-val rec">${getActionLabel(evaluation.recommended_action)}</span>
                    </div>
                    <div class="chain-arrow">↓</div>
                    <div class="chain-node">
                        <div class="chain-node-left">
                            <span class="chain-node-num">2</span>
                            <span class="chain-node-label">Guardrail Outcome</span>
                        </div>
                        <span class="${guardrailBadgeClass}">${evaluation.guardrail_status}</span>
                    </div>
                    <div class="chain-arrow">↓</div>
                    <div class="chain-node">
                        <div class="chain-node-left">
                            <span class="chain-node-num">3</span>
                            <span class="chain-node-label">Final Action</span>
                        </div>
                        <span class="chain-node-val final">${getActionLabel(evaluation.final_action)}</span>
                    </div>
                    <div class="chain-arrow">↓</div>
                    <div class="chain-node">
                        <div class="chain-node-left">
                            <span class="chain-node-num">4</span>
                            <span class="chain-node-label">Simulated Execution</span>
                        </div>
                        <span class="chain-node-val sim">${executionStatus}</span>
                    </div>
                    <div class="chain-arrow">↓</div>
                    <div class="chain-node">
                        <div class="chain-node-left">
                            <span class="chain-node-num">5</span>
                            <span class="chain-node-label">Audit ID</span>
                        </div>
                        <span class="chain-node-val audit">${auditId}</span>
                    </div>
                </div>
            </div>

            <div class="result-section-title">Recommendation</div>
            <div class="result-field">
                <span class="result-label">Recommended Action</span>
                <span class="result-value highlighted">${getActionLabel(evaluation.recommended_action)}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Expected Recovery</span>
                <span class="result-value currency">${formatCurrency(evaluation.expected_recovery)}</span>
            </div>

            <div class="result-section-title">Risk Snapshot</div>
            <div class="result-field">
                <span class="result-label">Promise Credibility Score</span>
                <span class="result-value">${credibilityScore} / 100</span>
            </div>
            <div class="risk-progress-wrap">
                <div class="risk-progress-track">
                    <div class="risk-progress-fill ${typeof credibilityScore === 'number' ? getCredibilityClass(credibilityScore) : 'credibility-medium'}" style="width: ${typeof credibilityScore === 'number' ? Math.min(100, credibilityScore) : 50}%"></div>
                </div>
            </div>
            <div class="result-field">
                <span class="result-label">Break Probability</span>
                <span class="result-value">${formatPercentage(evaluation.break_probability)}</span>
            </div>
            <div class="risk-progress-wrap">
                <div class="risk-progress-track">
                    <div class="risk-progress-fill ${getRiskClass(evaluation.break_probability)}" style="width: ${Math.min(100, Math.round(evaluation.break_probability * 100))}%"></div>
                </div>
            </div>
            <div class="result-field">
                <span class="result-label">Recovery Probability</span>
                <span class="result-value">${formatPercentage(evaluation.recovery_probability)}</span>
            </div>
            <div class="risk-progress-wrap">
                <div class="risk-progress-track">
                    <div class="risk-progress-fill recovery" style="width: ${Math.min(100, Math.round(evaluation.recovery_probability * 100))}%"></div>
                </div>
            </div>
            <div class="result-field">
                <span class="result-label">Priority Tier</span>
                <span class="result-value">${evaluation.priority_tier}</span>
            </div>

            <div class="result-section-title">Guardrail Decision</div>
            <div class="result-field">
                <span class="result-label">Guardrail Status</span>
                <span class="result-value"><span class="${guardrailBadgeClass}">${evaluation.guardrail_status}</span></span>
            </div>
            <div class="result-field">
                <span class="result-label">Final Action</span>
                <span class="result-value highlighted">${getActionLabel(evaluation.final_action)}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Reason Code</span>
                <span class="result-value code-pill">${evaluation.reason_code}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Guardrail Reason</span>
                <span class="result-value guardrail-reason-text">${evaluation.explanation}</span>
            </div>

            <div class="result-section-title">Simulated Execution</div>
            <div class="result-field">
                <span class="result-label">Execution Status</span>
                <span class="result-value status-badge">${executionStatus}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Simulated</span>
                <span class="result-value">${isSimulated}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Audit ID</span>
                <span class="result-value audit-id-text">${auditId}</span>
            </div>
        </div>
    `;

    const container = document.getElementById('evaluationResultContainer');
    if (container) {
        container.innerHTML = resultHtml;
    } else {
        const existing = panel.querySelector('.evaluation-result');
        if (existing) {
            existing.outerHTML = resultHtml;
        } else {
            const ctaCard = panel.querySelector('.evaluate-cta-card');
            if (ctaCard) {
                ctaCard.insertAdjacentHTML('afterend', resultHtml);
            } else {
                panel.insertAdjacentHTML('beforeend', resultHtml);
            }
        }
    }
}

/**
 * Show error message
 * @param {string} message - Error message
 */
function showError(message) {
    const leftPanel = document.querySelector('.left-panel');
    if (!leftPanel) return;

    if (leftPanel.querySelector('.error-message')) {
        return; // Error already shown
    }

    const errorHtml = `<div class="error-message">⚠️ ${message}</div>`;
    leftPanel.insertAdjacentHTML('afterbegin', errorHtml);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        const errorMsg = document.querySelector('.error-message');
        if (errorMsg) errorMsg.remove();
    }, 5000);
}

/**
 * Show error in detail panel
 * @param {string} message - Error message
 */
function showDetailError(message) {
    const panel = document.getElementById('detailPanel');
    if (!panel) return;
    panel.innerHTML = `
        <div class="detail-empty">
            <div class="empty-icon">❌</div>
            <h3>Error Loading Details</h3>
            <p>${message}</p>
            <button class="action-button" onclick="location.reload()" style="margin-top: 16px;">Reload Page</button>
        </div>
    `;
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Keyboard shortcut to refresh data (Ctrl+R or Cmd+R)
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            loadPortfolioData();
        }
    });
}

/**
 * Cleanup on page unload
 */
window.addEventListener('beforeunload', () => {
    if (appState.refreshInterval) {
        clearInterval(appState.refreshInterval);
    }
});

/**
 * Initialize app when DOM is ready
 */
document.addEventListener('DOMContentLoaded', initApp);
