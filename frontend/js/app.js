/**
 * Promise Ledger Dashboard Application Logic
 */

// Application state
const appState = {
    portfolio: null,
    opportunities: [],
    selectedPromiseId: null,
    selectedOpportunity: null,
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
 * Load portfolio data and opportunities
 */
async function loadPortfolioData() {
    appState.isLoading = true;
    
    try {
        const api = getAPIClient();
        
        // Fetch portfolio summary and opportunities in parallel
        const [summary, opportunities] = await Promise.all([
            api.getPortfolioSummary(),
            api.getOpportunities()
        ]);
        
        appState.portfolio = summary;
        appState.opportunities = opportunities;
        appState.error = null;
        
        // Render all sections
        renderPortfolioMetrics();
        renderPriorityDistribution();
        renderOpportunitiesTable();
        
    } catch (error) {
        console.error('Error loading portfolio data:', error);
        const statusDot = document.getElementById('statusDot');
        const healthStatus = document.getElementById('healthStatus');
        statusDot.classList.remove('healthy');
        statusDot.classList.add('error');
        healthStatus.textContent = 'Backend Unavailable';
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
    document.getElementById('totalOutstanding').textContent = 
        formatCurrency(p.total_outstanding_amount);
    
    document.getElementById('expectedRecovery').textContent = 
        formatCurrency(p.total_expected_recovery);
    
    document.getElementById('atRiskCount').textContent = 
        p.evaluation_count.toLocaleString('en-IN');
    
    const recoveryRate = p.total_outstanding_amount > 0
        ? p.total_expected_recovery / p.total_outstanding_amount
        : 0;
    document.getElementById('recoveryRate').textContent = 
        formatPercentage(recoveryRate);
}

/**
 * Render priority tier distribution
 */
function renderPriorityDistribution() {
    if (!appState.portfolio) return;
    
    const tiers = appState.portfolio.priority_tiers;
    
    document.getElementById('tierHigh').textContent = 
        (tiers.HIGH || 0).toString();
    document.getElementById('tierMedium').textContent = 
        (tiers.MEDIUM || 0).toString();
    document.getElementById('tierLow').textContent = 
        (tiers.LOW || 0).toString();
}

/**
 * Render opportunities table
 */
function renderOpportunitiesTable() {
    const tbody = document.getElementById('opportunitiesTableBody');
    
    if (!appState.opportunities || appState.opportunities.length === 0) {
        tbody.innerHTML = '<tr class="loading"><td colspan="9">No opportunities found</td></tr>';
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
        
        return `
            <tr class="${isSelected ? 'active' : ''}" data-promise-id="${opp.promise_id}">
                <td class="promise-id">${opp.promise_id}</td>
                <td>${opp.customer_id}</td>
                <td>${opp.invoice_id}</td>
                <td class="outstanding-amount">${formatCurrency(opp.outstanding_amount)}</td>
                <td>${formatCurrency(opp.expected_recovery)}</td>
                <td class="${riskClass}">${formatPercentage(breakProbability)}</td>
                <td class="${credibilityClass}">${credibilityScore}</td>
                <td><span class="${getPriorityClass(opp.priority_tier)}">${opp.priority_tier}</span></td>
                <td><button class="action-button" onclick="selectOpportunity(${opp.promise_id})">View</button></td>
            </tr>
        `;
    }).join('');
    
    // Add click handlers to rows
    document.querySelectorAll('#opportunitiesTableBody tr').forEach(row => {
        row.addEventListener('click', (e) => {
            if (e.target.tagName !== 'BUTTON') {
                const promiseId = parseInt(row.dataset.promiseId);
                selectOpportunity(promiseId);
            }
        });
    });
}

/**
 * Select an opportunity and load its details
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
    
    // Load opportunity details
    try {
        const api = getAPIClient();
        const detail = await api.getOpportunityDetail(promiseId);
        appState.selectedOpportunity = detail;
        renderDetailPanel(detail);
    } catch (error) {
        console.error('Error loading opportunity detail:', error);
        showDetailError(`Failed to load details: ${error.message}`);
    }
}

/**
 * Render the detail panel for a selected opportunity
 * @param {Object} detail - Opportunity detail data
 */
function renderDetailPanel(detail) {
    const panel = document.getElementById('detailPanel');
    
    const credibilityScore = Math.round(detail.promise_credibility_score);
    const breakProbability = detail.break_probability;
    const recoveryProbability = detail.recovery_probability;
    const credibilityClass = getCredibilityClass(credibilityScore);
    const riskClass = getRiskClass(breakProbability);
    
    let html = `
        <div class="detail-header">
            <h3>Opportunity Details</h3>
            <div class="promise-id-display">Promise ID #${detail.promise_id}</div>
        </div>

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
        </div>

        <!-- Risk Metrics Section -->
        <div class="detail-section">
            <div class="detail-section-title">Risk Assessment (probabilities)</div>
            <div class="detail-field">
                <span class="detail-field-label">Break Probability</span>
                <span class="detail-field-value ${riskClass}">${formatPercentage(breakProbability)}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Recovery Probability</span>
                <span class="detail-field-value">${formatPercentage(recoveryProbability)}</span>
            </div>
            <div class="detail-field">
                <span class="detail-field-label">Priority Tier</span>
                <span class="detail-field-value">${detail.priority_tier}</span>
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
        </div>

        <!-- Invoice Details Section -->
        <div class="detail-section">
            <div class="detail-section-title">Invoice Information</div>
            <div class="detail-field">
                <span class="detail-field-label">Invoice ID</span>
                <span class="detail-field-value">${detail.invoice_id}</span>
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
                <span class="detail-field-label">Current Outstanding</span>
                <span class="detail-field-value currency">${formatCurrency(detail.current_outstanding_amount)}</span>
            </div>
        </div>

        <!-- Explanation Section -->
        <div class="detail-explanation">
            <h4>📊 Risk Analysis Summary</h4>
            <ul class="explanation-list">
                ${detail.explanation.map(item => `<li>${item}</li>`).join('')}
            </ul>
        </div>

        <!-- Evaluation Button -->
        <button class="evaluate-button" onclick="evaluateOpportunity(${detail.promise_id}, event)">
            📋 Evaluate & Get Recommendation
        </button>
    `;
    
    panel.innerHTML = html;
}

/**
 * Evaluate an opportunity and show the recommended action
 * @param {number} promiseId - Promise ID to evaluate
 */
async function evaluateOpportunity(promiseId, event) {
    const button = event.currentTarget;
    const originalText = button.textContent;
    
    try {
        button.classList.add('loading');
        button.textContent = '⏳ Evaluating...';
        button.disabled = true;
        
        const api = getAPIClient();
        const evaluation = await api.evaluateOpportunity(promiseId);
        
        // Show evaluation result
        showEvaluationResult(evaluation);
        
    } catch (error) {
        console.error('Error evaluating opportunity:', error);
        showDetailError(`Evaluation failed: ${error.message}`);
    } finally {
        button.classList.remove('loading');
        button.textContent = originalText;
        button.disabled = false;
    }
}

/**
 * Show evaluation result in the detail panel
 * @param {Object} evaluation - Evaluation response
 */
function showEvaluationResult(evaluation) {
    const panel = document.getElementById('detailPanel');
    const resultHtml = `
        <div class="evaluation-result">
            <h4>✅ Evaluation Complete</h4>
            <div class="result-section-title">Recommendation</div>
            <div class="result-field">
                <span class="result-label">Recommended Action</span>
                <span class="result-value">${getActionLabel(evaluation.recommended_action)}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Expected Recovery</span>
                <span class="result-value">${formatCurrency(evaluation.expected_recovery)}</span>
            </div>
            <div class="result-section-title">Risk Snapshot</div>
            <div class="result-field">
                <span class="result-label">Promise Credibility Score</span>
                <span class="result-value">${evaluation.promise_credibility === null || evaluation.promise_credibility === undefined ? '--' : Math.round(evaluation.promise_credibility)} / 100</span>
            </div>
            <div class="result-field">
                <span class="result-label">Break Probability</span>
                <span class="result-value">${formatPercentage(evaluation.break_probability)}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Recovery Probability</span>
                <span class="result-value">${formatPercentage(evaluation.recovery_probability)}</span>
            </div>
            <div class="result-section-title">Guardrail Decision</div>
            <div class="result-field">
                <span class="result-label">Guardrail Status</span>
                <span class="result-value">${evaluation.guardrail_status}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Final Action</span>
                <span class="result-value">${getActionLabel(evaluation.final_action)}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Reason Code</span>
                <span class="result-value">${evaluation.reason_code}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Guardrail Reason</span>
                <span class="result-value" style="word-break: break-word;">${evaluation.explanation}</span>
            </div>
            <div class="result-section-title">Simulated Execution</div>
            <div class="result-field">
                <span class="result-label">Execution Status</span>
                <span class="result-value">${evaluation.audit.execution_status || '--'}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Simulated</span>
                <span class="result-value">${evaluation.audit.simulated ? 'Yes' : 'No'}</span>
            </div>
            <div class="result-field">
                <span class="result-label">Audit ID</span>
                <span class="result-value" style="word-break: break-word;">${evaluation.audit.audit_id || '--'}</span>
            </div>
        </div>
    `;
    
    // Append result to the panel
    const evaluateButton = panel.querySelector('.evaluate-button');
    if (evaluateButton && !evaluateButton.nextElementSibling?.classList.contains('evaluation-result')) {
        evaluateButton.insertAdjacentHTML('afterend', resultHtml);
    } else if (!evaluateButton) {
        panel.insertAdjacentHTML('beforeend', resultHtml);
    }
}

/**
 * Show error message
 * @param {string} message - Error message
 */
function showError(message) {
    const panel = document.getElementById('detailPanel');
    if (panel && panel.querySelector('.error-message')) {
        return; // Error already shown
    }
    
    const errorHtml = `<div class="error-message">⚠️ ${message}</div>`;
    const leftPanel = document.querySelector('.left-panel');
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
    panel.innerHTML = `
        <div class="detail-empty">
            <div class="empty-icon">❌</div>
            <p>${message}</p>
            <button class="action-button" onclick="location.reload()" style="margin-top: 16px;">Reload Page</button>
        </div>
    `;
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Refresh button (can be added to header)
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
