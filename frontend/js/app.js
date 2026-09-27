/**
 * Promise Ledger Dashboard Application Logic
 * B2B Receivables Recovery & Risk Management
 */

// Application state
const appState = {
    portfolio: null,
    experiment: null,
    opportunities: [],
    financial: {
        summary: null,
        recurring: null,
        anomalies: null,
        budgets: null,
        goals: null,
        transactions: [],
        activeFilter: 'ALL',
        forecast: null,
        recommendations: null,
        scenario: null
    },
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
 * Load portfolio data, experiment metrics, opportunities, and financial intelligence
 */
async function loadPortfolioData() {
    appState.isLoading = true;

    try {
        const api = getAPIClient();

        // Fetch portfolio summary, opportunities, experiment, and financial data in parallel
        const [
            summary,
            opportunities,
            experiment,
            finSummary,
            finRecurring,
            finAnomalies,
            finBudgets,
            finGoals,
            finTxns,
            finForecast,
            finRecs,
            finScenario
        ] = await Promise.all([
            api.getPortfolioSummary(),
            api.getOpportunities(),
            api.getEvaluationExperiment().catch((err) => {
                console.warn('Experiment endpoint call fallback:', err);
                return null;
            }),
            api.getFinancialSummary().catch((err) => {
                console.warn('Financial summary fallback:', err);
                return null;
            }),
            api.getFinancialRecurringExpenses().catch((err) => {
                console.warn('Financial recurring fallback:', err);
                return null;
            }),
            api.getFinancialAnomalies().catch((err) => {
                console.warn('Financial anomalies fallback:', err);
                return null;
            }),
            api.getFinancialBudgets().catch((err) => {
                console.warn('Financial budgets fallback:', err);
                return null;
            }),
            api.getFinancialGoals().catch((err) => {
                console.warn('Financial goals fallback:', err);
                return null;
            }),
            api.getFinancialTransactions({ limit: 100 }).catch((err) => {
                console.warn('Financial transactions fallback:', err);
                return [];
            }),
            api.getFinancialForecast().catch((err) => {
                console.warn('Financial forecast fallback:', err);
                return null;
            }),
            api.getFinancialRecommendations().catch((err) => {
                console.warn('Financial recommendations fallback:', err);
                return null;
            }),
            api.simulateFinancialScenario({
                receivable_delay_days: 15,
                expense_change_percent: 10,
                additional_monthly_expense: 20000
            }).catch((err) => {
                console.warn('Financial scenario fallback:', err);
                return null;
            })
        ]);

        appState.portfolio = summary;
        appState.opportunities = opportunities;
        appState.experiment = experiment || summary.experiment || null;
        appState.financial.summary = finSummary;
        appState.financial.recurring = finRecurring;
        appState.financial.anomalies = finAnomalies;
        appState.financial.budgets = finBudgets;
        appState.financial.goals = finGoals;
        appState.financial.transactions = finTxns || [];
        appState.financial.forecast = finForecast;
        appState.financial.recommendations = finRecs;
        appState.financial.scenario = finScenario;
        appState.error = null;

        // Render all portfolio sections
        renderPortfolioMetrics();
        renderPriorityDistribution();
        renderExperimentMetrics();
        renderOpportunitiesTable();

        // Render Financial Intelligence Layer
        renderFinancialHealth();
        renderFinancialBridge();
        renderRecommendations(finRecs);
        renderForecast(finForecast);
        if (finScenario) renderScenarioResults(finScenario);
        renderRecurringExpenses();
        renderBudgets();
        renderAnomalies();
        renderFinancialGoals();
        renderFinancialTransactions(appState.financial.activeFilter || 'ALL');

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
 * Render Financial Health KPIs
 */
function renderFinancialHealth() {
    const f = appState.financial.summary;
    if (!f) return;

    const cashEl = document.getElementById('finCashBalance');
    if (cashEl) cashEl.textContent = formatCurrency(f.current_cash_balance);

    const incEl = document.getElementById('finMonthlyIncome');
    if (incEl) incEl.textContent = formatCurrency(f.monthly_income);

    const expEl = document.getElementById('finMonthlyExpenses');
    if (expEl) expEl.textContent = formatCurrency(f.monthly_expenses);

    const netEl = document.getElementById('finNetCashFlow');
    if (netEl) {
        netEl.textContent = formatCurrency(f.net_cash_flow, true);
        netEl.style.color = f.net_cash_flow >= 0 ? 'var(--success)' : 'var(--danger)';
    }

    const recEl = document.getElementById('finTotalReceivables');
    if (recEl) recEl.textContent = formatCurrency(f.total_receivables);

    const riskEl = document.getElementById('finRiskLevel');
    if (riskEl) {
        const riskLevel = f.financial_risk_level || 'MEDIUM';
        riskEl.innerHTML = `<span class="fin-risk-pill ${riskLevel.toLowerCase()}">${riskLevel}</span>`;
    }

    const scoreSub = document.getElementById('finRiskScoreSub');
    if (scoreSub) {
        scoreSub.textContent = `Score: ${Math.round(f.financial_risk_score || 50)} / 100`;
    }
}

/**
 * Render Financial Risk Contributors and Promise Ledger Bridge
 */
function renderFinancialBridge() {
    const f = appState.financial.summary;
    if (!f) return;

    const listEl = document.getElementById('finRiskContributorsList');
    if (listEl && f.risk_contributors) {
        listEl.innerHTML = f.risk_contributors.map(c => `<li>${escapeHtml(c)}</li>`).join('');
    }

    const insightEl = document.getElementById('finReceivablesRiskInsight');
    if (insightEl && f.receivables_risk_insight) {
        insightEl.textContent = f.receivables_risk_insight;
    }
}

/**
 * Render Recurring Expenses Intelligence
 */
function renderRecurringExpenses() {
    const r = appState.financial.recurring;
    if (!r) return;

    const badge = document.getElementById('finTotalRecurringBadge');
    if (badge) badge.textContent = `${formatCurrency(r.total_monthly_recurring)} / mo`;

    const tbody = document.getElementById('finRecurringTableBody');
    if (!tbody) return;

    if (!r.recurring_expenses || r.recurring_expenses.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="fin-loading">No recurring expenses detected.</td></tr>';
        return;
    }

    tbody.innerHTML = r.recurring_expenses.map(item => `
        <tr>
            <td><strong>${escapeHtml(item.merchant)}</strong></td>
            <td><span class="code-pill">${escapeHtml(item.category)}</span></td>
            <td>${escapeHtml(item.periodicity)} (${item.occurrences} mo)</td>
            <td class="fin-amount-cell">${formatCurrency(item.amount)}</td>
        </tr>
    `).join('');
}

/**
 * Render Merchant Budget Tracking
 */
function renderBudgets() {
    const b = appState.financial.budgets;
    if (!b) return;

    const badge = document.getElementById('finOverallBudgetBadge');
    if (badge) badge.textContent = `${b.overall_utilization_pct}% Spent`;

    const container = document.getElementById('finBudgetsList');
    if (!container) return;

    if (!b.categories || b.categories.length === 0) {
        container.innerHTML = '<div class="fin-loading">No budget categories defined.</div>';
        return;
    }

    container.innerHTML = b.categories.map(cat => {
        const utilCapped = Math.min(100, Math.max(0, cat.utilization_pct));
        const statusClass = cat.status.toLowerCase().replace('_', '-');
        const statusLabel = cat.status.replace('_', ' ');
        return `
            <div class="fin-budget-item">
                <div class="fin-budget-row-top">
                    <span class="fin-budget-name">${escapeHtml(cat.category)}</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="fin-budget-amounts">${formatCurrency(cat.spent)} / ${formatCurrency(cat.budget)} (${cat.utilization_pct}%)</span>
                        <span class="status-pill ${statusClass}">${statusLabel}</span>
                    </div>
                </div>
                <div class="fin-budget-track">
                    <div class="fin-budget-fill ${statusClass}" style="width: ${utilCapped}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render Financial Anomalies
 */
function renderAnomalies() {
    const a = appState.financial.anomalies;
    if (!a) return;

    const badge = document.getElementById('finAnomaliesCountBadge');
    if (badge) badge.textContent = `${a.total_anomalies} Flagged (${a.high_severity_count} High)`;

    const container = document.getElementById('finAnomaliesList');
    if (!container) return;

    if (!a.anomalies || a.anomalies.length === 0) {
        container.innerHTML = '<div class="fin-loading">No anomalies detected in recent cycle.</div>';
        return;
    }

    container.innerHTML = a.anomalies.map(anm => {
        const isHigh = anm.severity === 'HIGH';
        const sevClass = isHigh ? 'high-sev' : 'med-sev';
        const pillClass = isHigh ? 'high' : 'medium';
        return `
            <div class="fin-anomaly-card ${sevClass}">
                <div class="fin-anomaly-top">
                    <span class="fin-anomaly-desc">${escapeHtml(anm.description)}</span>
                    <span class="fin-anomaly-amt">${formatCurrency(anm.amount)}</span>
                </div>
                <div class="fin-anomaly-meta">
                    <span class="fin-risk-pill ${pillClass}">${anm.severity} RISK</span>
                    <span>Category: ${escapeHtml(anm.category)}</span>
                    <span>Date: ${anm.date}</span>
                    ${anm.deviation_percentage > 0 ? `<span style="color: var(--danger); font-weight: 700;">+${anm.deviation_percentage}% dev</span>` : ''}
                </div>
                <div class="fin-anomaly-reason">${escapeHtml(anm.reason)}</div>
            </div>
        `;
    }).join('');
}

/**
 * Render Financial Goals
 */
function renderFinancialGoals() {
    const g = appState.financial.goals;
    if (!g) return;

    const badge = document.getElementById('finGoalsSavedBadge');
    if (badge) badge.textContent = `${formatCurrency(g.total_saved)} Saved`;

    const container = document.getElementById('finGoalsList');
    if (!container) return;

    if (!g.goals || g.goals.length === 0) {
        container.innerHTML = '<div class="fin-loading">No financial goals configured.</div>';
        return;
    }

    container.innerHTML = g.goals.map(goal => {
        const pctCapped = Math.min(100, Math.max(0, goal.progress_pct));
        return `
            <div class="fin-goal-item">
                <div class="fin-goal-top">
                    <span class="fin-goal-name">${escapeHtml(goal.name)}</span>
                    <span class="fin-goal-amounts">${formatCurrency(goal.current_amount)} / ${formatCurrency(goal.target_amount)}</span>
                </div>
                <div class="fin-goal-track">
                    <div class="fin-goal-fill" style="width: ${pctCapped}%"></div>
                </div>
                <div class="fin-goal-meta">
                    <span>Target Date: ${goal.target_date}</span>
                    <span style="font-weight: 700; color: var(--brand-primary);">${goal.progress_pct}% Funded</span>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Filter and Render Financial Transactions
 */
function filterFinancialTransactions(type) {
    appState.financial.activeFilter = type;
    ['btnFilterAll', 'btnFilterIncome', 'btnFilterExpense'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.classList.remove('active');
    });

    const activeBtn = document.getElementById(
        type === 'INCOME' ? 'btnFilterIncome' : type === 'EXPENSE' ? 'btnFilterExpense' : 'btnFilterAll'
    );
    if (activeBtn) activeBtn.classList.add('active');

    renderFinancialTransactions(type);
}

function renderFinancialTransactions(type = 'ALL') {
    const tbody = document.getElementById('finTransactionsTableBody');
    if (!tbody) return;

    let txns = appState.financial.transactions || [];
    if (type !== 'ALL') {
        txns = txns.filter(t => t.transaction_type === type);
    }

    if (txns.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="fin-loading">No transactions found for filter.</td></tr>';
        return;
    }

    tbody.innerHTML = txns.slice(0, 50).map(t => {
        const isIncome = t.transaction_type === 'INCOME';
        const badgeClass = isIncome ? 'income' : 'expense';
        const amtSign = isIncome ? '+' : '-';
        const amtColor = isIncome ? 'var(--success)' : 'var(--text-primary)';
        return `
            <tr>
                <td style="white-space: nowrap; font-family: var(--font-mono, monospace); font-size: 12px;">${t.date}</td>
                <td><strong>${escapeHtml(t.description)}</strong></td>
                <td><span class="code-pill">${escapeHtml(t.category)}</span></td>
                <td><span class="txn-type-badge ${badgeClass}">${t.transaction_type}</span></td>
                <td class="fin-amount-cell" style="color: ${amtColor}; white-space: nowrap;">${amtSign}${formatCurrency(t.amount)}</td>
            </tr>
        `;
    }).join('');
}

/**
 * ==============================================================================
 * Phase 2: Cash Flow Forecast, Scenario Simulation & AI Recommendations Handlers
 * ==============================================================================
 */

/**
 * Render 3-Month Forward Cash Flow Forecast
 * @param {Object} forecast - Forecast response object
 */
function renderForecast(forecast) {
    if (!forecast) return;

    const startEl = document.getElementById('fcStartingCash');
    if (startEl) startEl.textContent = formatCurrency(forecast.starting_cash_balance);

    const incEl = document.getElementById('fcTotalIncome');
    if (incEl) incEl.textContent = `+${formatCurrency(forecast.total_projected_income)}`;

    const expEl = document.getElementById('fcTotalExpense');
    if (expEl) expEl.textContent = `-${formatCurrency(forecast.total_projected_expenses)}`;

    const netEl = document.getElementById('fcTotalNet');
    if (netEl) {
        netEl.textContent = formatCurrency(forecast.total_projected_net_flow, true);
        netEl.className = `forecast-stat-val ${forecast.total_projected_net_flow >= 0 ? 'positive' : 'negative'}`;
    }

    const endEl = document.getElementById('fcEndingCash');
    if (endEl) endEl.textContent = formatCurrency(forecast.projected_final_cash);

    const confBadge = document.getElementById('forecastConfidenceBadge');
    if (confBadge) confBadge.textContent = `Confidence: ${forecast.confidence}`;

    const methEl = document.getElementById('fcMethodologyText');
    if (methEl && forecast.receivables_integration_note) {
        methEl.textContent = forecast.receivables_integration_note;
    }

    const grid = document.getElementById('forecastMonthsGrid');
    if (!grid || !forecast.months) return;

    grid.innerHTML = forecast.months.map(m => {
        const total = m.projected_income + m.projected_expenses;
        const incPct = total > 0 ? Math.round((m.projected_income / total) * 100) : 50;
        const expPct = 100 - incPct;
        const isNetPos = m.projected_net_cash_flow >= 0;

        return `
            <div class="forecast-month-card">
                <div class="forecast-month-header">
                    <span class="forecast-month-title">${escapeHtml(m.month_name)}</span>
                    <span class="forecast-tag">Forecast</span>
                </div>
                <div class="forecast-metrics-list">
                    <div class="forecast-metric-row">
                        <span class="forecast-metric-name">Projected Income</span>
                        <span class="forecast-metric-num income">+${formatCurrency(m.projected_income)}</span>
                    </div>
                    <div class="forecast-metric-row" style="font-size: 11px; padding-left: 8px;">
                        <span class="forecast-metric-name">↳ Receivables Realization</span>
                        <span class="forecast-metric-num" style="color: var(--brand-primary);">${formatCurrency(m.receivables_contribution)}</span>
                    </div>
                    <div class="forecast-metric-row">
                        <span class="forecast-metric-name">Projected Expenses</span>
                        <span class="forecast-metric-num expense">-${formatCurrency(m.projected_expenses)}</span>
                    </div>
                    <div class="forecast-metric-row" style="font-size: 11px; padding-left: 8px;">
                        <span class="forecast-metric-name">↳ Recurring Commitment Floor</span>
                        <span class="forecast-metric-num" style="color: var(--text-muted);">${formatCurrency(m.recurring_expense_baseline)}</span>
                    </div>
                    <div class="forecast-bar-wrap">
                        <div class="forecast-bar-track" title="Income ${incPct}% vs Expense ${expPct}%">
                            <div class="forecast-bar-inc" style="width: ${incPct}%;"></div>
                            <div class="forecast-bar-exp" style="width: ${expPct}%;"></div>
                        </div>
                    </div>
                    <div class="forecast-metric-row" style="margin-top: 4px;">
                        <span class="forecast-metric-name">Projected Net Flow</span>
                        <span class="forecast-metric-num ${isNetPos ? 'net-pos' : 'net-neg'}">${formatCurrency(m.projected_net_cash_flow, true)}</span>
                    </div>
                </div>
                <div class="forecast-ending-box">
                    <span class="forecast-ending-label">Ending Cash</span>
                    <span class="forecast-ending-val">${formatCurrency(m.projected_ending_cash)}</span>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render AI Financial Recommendations
 * @param {Object} data - Recommendations response object
 */
function renderRecommendations(data) {
    if (!data) return;

    const pendingBadge = document.getElementById('recPendingBadge');
    if (pendingBadge) {
        pendingBadge.textContent = `${data.pending_human_approval_count} Pending Approval`;
    }

    const grid = document.getElementById('recommendationsGrid');
    if (!grid || !data.recommendations) return;

    if (data.recommendations.length === 0) {
        grid.innerHTML = '<div class="fin-loading">No active financial recommendations at this time.</div>';
        return;
    }

    grid.innerHTML = data.recommendations.map(r => {
        const priClass = r.priority ? r.priority.toLowerCase() : 'medium';
        const statusClass = (r.status || 'NEW').toLowerCase();
        const isPending = r.status === 'NEW' || r.status === 'REVIEWED';

        return `
            <div class="rec-card priority-${priClass}" id="rec-card-${r.id}">
                <div class="rec-header">
                    <div class="rec-tags">
                        <span class="rec-priority-badge ${priClass}">${r.priority} PRIORITY</span>
                        <span class="rec-cat-badge">${escapeHtml(r.category)}</span>
                    </div>
                    ${r.human_approval_required ? '<span class="rec-human-badge">🔒 HUMAN APPROVAL REQUIRED</span>' : ''}
                </div>
                <h4 class="rec-title">${escapeHtml(r.recommendation)}</h4>
                <p class="rec-reason">${escapeHtml(r.reason)}</p>
                <div class="rec-evidence-box">
                    <span class="rec-evidence-header">Supporting Evidence</span>
                    <ul class="rec-evidence-list">
                        ${r.supporting_evidence.map(e => `<li>${escapeHtml(e)}</li>`).join('')}
                    </ul>
                    <div class="rec-impact-row">
                        <span class="rec-impact-label">Estimated Impact:</span>
                        <span class="rec-impact-val">${escapeHtml(r.financial_impact_estimate)}</span>
                    </div>
                </div>
                <div class="rec-action-callout">
                    <strong>Suggested Action:</strong> ${escapeHtml(r.suggested_action)}
                </div>
                <div class="rec-footer">
                    <span class="rec-status-indicator status-${statusClass}" id="rec-status-${r.id}">
                        Status: ${r.status}${r.reviewed_at ? ' (Reviewed)' : ''}
                    </span>
                    <div class="rec-btn-group" id="rec-actions-${r.id}">
                        ${isPending ? `
                            <button class="rec-btn-approve" onclick="handleRecommendationReview('${r.id}', 'APPROVE')">✓ Approve</button>
                            <button class="rec-btn-reject" onclick="handleRecommendationReview('${r.id}', 'REJECT')">✕ Reject</button>
                        ` : `
                            <span style="font-size: 11px; color: var(--text-muted); font-style: italic;">Decision Recorded</span>
                        `}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Handle Merchant Review/Approval of an AI Recommendation
 * @param {string} recId - Recommendation ID
 * @param {string} action - REVIEW, APPROVE, or REJECT
 */
async function handleRecommendationReview(recId, action) {
    try {
        const api = getAPIClient();
        const updated = await api.reviewFinancialRecommendation(recId, {
            action: action,
            reviewer_notes: `Explicit human decision executed by merchant dashboard operator: ${action}`
        });

        // Update card status visually
        const statusEl = document.getElementById(`rec-status-${recId}`);
        if (statusEl && updated) {
            const statusClass = updated.status.toLowerCase();
            statusEl.className = `rec-status-indicator status-${statusClass}`;
            statusEl.textContent = `Status: ${updated.status} (Reviewed)`;
        }

        const actionsEl = document.getElementById(`rec-actions-${recId}`);
        if (actionsEl) {
            actionsEl.innerHTML = `<span style="font-size: 11px; color: var(--text-muted); font-style: italic;">Decision: ${action} Recorded</span>`;
        }

        // Refresh recommendations summary
        const refreshed = await api.getFinancialRecommendations();
        appState.financial.recommendations = refreshed;
        const pendingBadge = document.getElementById('recPendingBadge');
        if (pendingBadge) {
            pendingBadge.textContent = `${refreshed.pending_human_approval_count} Pending Approval`;
        }

    } catch (err) {
        console.error('Error reviewing recommendation:', err);
        alert(`Failed to update recommendation: ${err.message}`);
    }
}

/**
 * Update What-If Scenario Input Previews as Sliders are Moved
 */
function updateScenarioPreview() {
    const delay = document.getElementById('inputDelayDays')?.value || '0';
    const expense = document.getElementById('inputExpensePct')?.value || '0';
    const extra = document.getElementById('inputExtraExpense')?.value || '0';

    const pDelay = document.getElementById('previewDelayDays');
    if (pDelay) pDelay.textContent = `${delay} days`;

    const pExp = document.getElementById('previewExpensePct');
    if (pExp) {
        const val = parseFloat(expense);
        pExp.textContent = `${val >= 0 ? '+' : ''}${val.toFixed(1)}%`;
    }

    const pExtra = document.getElementById('previewExtraExpense');
    if (pExtra) pExtra.textContent = formatCurrency(parseFloat(extra));
}

/**
 * Execute What-If Scenario Simulation
 */
async function runScenarioSimulation() {
    const btn = document.getElementById('btnRunScenario');
    if (btn) {
        btn.textContent = 'Simulating…';
        btn.disabled = true;
    }

    try {
        const delay = parseInt(document.getElementById('inputDelayDays')?.value || '0', 10);
        const expensePct = parseFloat(document.getElementById('inputExpensePct')?.value || '0');
        const extraExpense = parseFloat(document.getElementById('inputExtraExpense')?.value || '0');

        const api = getAPIClient();
        const res = await api.simulateFinancialScenario({
            receivable_delay_days: delay,
            expense_change_percent: expensePct,
            additional_monthly_expense: extraExpense
        });

        appState.financial.scenario = res;
        renderScenarioResults(res);

    } catch (err) {
        console.error('Error simulating scenario:', err);
        alert(`Simulation error: ${err.message}`);
    } finally {
        if (btn) {
            btn.textContent = 'Simulate Scenario';
            btn.disabled = false;
        }
    }
}

/**
 * Reset Scenario Form to Default Base Values
 */
function resetScenarioForm() {
    const inDelay = document.getElementById('inputDelayDays');
    if (inDelay) inDelay.value = '0';

    const inExp = document.getElementById('inputExpensePct');
    if (inExp) inExp.value = '0';

    const inExtra = document.getElementById('inputExtraExpense');
    if (inExtra) inExtra.value = '0';

    updateScenarioPreview();
    runScenarioSimulation();
}

/**
 * Render What-If Scenario Comparison Table and Explanation
 * @param {Object} res - Scenario simulation response
 */
function renderScenarioResults(res) {
    if (!res || !res.base_case || !res.scenario_case) return;

    const base = res.base_case;
    const scen = res.scenario_case;
    const delta = res.delta || {};

    // 1. Ending Cash
    const baseCash = document.getElementById('scenBaseEndingCash');
    if (baseCash) baseCash.textContent = formatCurrency(base.projected_ending_cash);

    const simCash = document.getElementById('scenSimEndingCash');
    if (simCash) simCash.textContent = formatCurrency(scen.projected_ending_cash);

    const deltaCash = document.getElementById('scenDeltaEndingCash');
    if (deltaCash) {
        const d = delta.projected_ending_cash || 0;
        deltaCash.textContent = `${d >= 0 ? '+' : ''}${formatCurrency(d)}`;
        deltaCash.className = `col-delta ${d < 0 ? 'delta-neg' : d > 0 ? 'delta-pos' : 'delta-neutral'}`;
    }

    // 2. Net Cash Flow
    const baseNet = document.getElementById('scenBaseNetFlow');
    if (baseNet) baseNet.textContent = formatCurrency(base.total_net_cash_flow, true);

    const simNet = document.getElementById('scenSimNetFlow');
    if (simNet) simNet.textContent = formatCurrency(scen.total_net_cash_flow, true);

    const deltaNet = document.getElementById('scenDeltaNetFlow');
    if (deltaNet) {
        const d = delta.total_net_cash_flow || 0;
        deltaNet.textContent = `${d >= 0 ? '+' : ''}${formatCurrency(d)}`;
        deltaNet.className = `col-delta ${d < 0 ? 'delta-neg' : d > 0 ? 'delta-pos' : 'delta-neutral'}`;
    }

    // 3. Cash Runway
    const baseRun = document.getElementById('scenBaseRunway');
    if (baseRun) baseRun.textContent = `${base.cash_runway_months} mo`;

    const simRun = document.getElementById('scenSimRunway');
    if (simRun) simRun.textContent = `${scen.cash_runway_months} mo`;

    const deltaRun = document.getElementById('scenDeltaRunway');
    if (deltaRun) {
        const d = delta.cash_runway_months || 0;
        deltaRun.textContent = `${d >= 0 ? '+' : ''}${d.toFixed(1)} mo`;
        deltaRun.className = `col-delta ${d < 0 ? 'delta-neg' : d > 0 ? 'delta-pos' : 'delta-neutral'}`;
    }

    // 4. Financial Risk Level
    const baseRisk = document.getElementById('scenBaseRisk');
    if (baseRisk) baseRisk.textContent = `${base.financial_risk_level} (${Math.round(base.risk_score)}/100)`;

    const simRisk = document.getElementById('scenSimRisk');
    if (simRisk) simRisk.textContent = `${scen.financial_risk_level} (${Math.round(scen.risk_score)}/100)`;

    const deltaRisk = document.getElementById('scenDeltaRisk');
    if (deltaRisk) {
        const d = delta.risk_score || 0;
        deltaRisk.textContent = `${d > 0 ? '+' : ''}${Math.round(d)} pts`;
        deltaRisk.className = `col-delta ${d > 0 ? 'delta-neg' : d < 0 ? 'delta-pos' : 'delta-neutral'}`;
    }

    // Risk delta badge
    const riskBadge = document.getElementById('scenarioRiskDeltaBadge');
    if (riskBadge) {
        riskBadge.textContent = `Risk: ${base.financial_risk_level} → ${scen.financial_risk_level}`;
    }

    // Explanation callout
    const expText = document.getElementById('scenarioExplanationText');
    if (expText && res.explanation) {
        expText.textContent = res.explanation;
    }
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

    // Sidebar navigation active state handler
    const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');
        });
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
