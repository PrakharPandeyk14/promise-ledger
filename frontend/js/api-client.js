/**
 * Promise Ledger API Client
 * Abstraction layer for backend communication
 */

class PromiseLedgerAPI {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    /**
     * Make a generic API request
     * @private
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Fetch options
     * @returns {Promise<Object>} Response data
     */
    async _request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            const error = new Error(`API Error: ${response.status}`);
            error.status = response.status;
            try {
                error.detail = await response.json();
            } catch (e) {
                error.detail = { message: response.statusText };
            }
            throw error;
        }

        return await response.json();
    }

    /**
     * GET /health - Check backend health status
     * @returns {Promise<Object>} Health response
     */
    async getHealth() {
        return this._request('/health');
    }

    /**
     * GET /portfolio/summary - Get portfolio overview metrics
     * @returns {Promise<Object>} Portfolio summary with metrics and distributions
     */
    async getPortfolioSummary() {
        return this._request('/portfolio/summary');
    }

    /**
     * GET /evaluation/experiment - Get control vs AI treatment evaluation metrics
     * @returns {Promise<Object>} Experiment metrics comparing control vs AI treatment
     */
    async getEvaluationExperiment() {
        return this._request('/evaluation/experiment');
    }

    /**
     * GET /opportunities - Get all at-risk opportunities
     * @returns {Promise<Array>} List of opportunities
     */
    async getOpportunities() {
        return this._request('/opportunities');
    }

    /**
     * GET /opportunities/{promise_id} - Get detailed information for an opportunity
     * @param {number} promiseId - Promise ID
     * @returns {Promise<Object>} Detailed opportunity information
     */
    async getOpportunityDetail(promiseId) {
        if (!isValidPromiseId(promiseId)) {
            throw new Error('Invalid promise ID');
        }
        return this._request(`/opportunities/${promiseId}`);
    }

    /**
     * POST /opportunities/{promise_id}/evaluate - Evaluate and get recommended action
     * @param {number} promiseId - Promise ID
     * @returns {Promise<Object>} Evaluation result with recommendation
     */
    async evaluateOpportunity(promiseId) {
        if (!isValidPromiseId(promiseId)) {
            throw new Error('Invalid promise ID');
        }
        return this._request(`/opportunities/${promiseId}/evaluate`, {
            method: 'POST'
        });
    }

    /**
     * GET /financial/summary - Get financial health overview metrics
     * @returns {Promise<Object>} Financial health summary
     */
    async getFinancialSummary() {
        return this._request('/financial/summary');
    }

    /**
     * GET /financial/transactions - Get financial transaction history
     * @param {Object} params - Query params (type, category, limit)
     * @returns {Promise<Array>} List of transactions
     */
    async getFinancialTransactions(params = {}) {
        const query = new URLSearchParams();
        if (params.type) query.set('type', params.type);
        if (params.category) query.set('category', params.category);
        if (params.limit) query.set('limit', params.limit);
        const qs = query.toString() ? `?${query.toString()}` : '';
        return this._request(`/financial/transactions${qs}`);
    }

    /**
     * GET /financial/recurring-expenses - Get recurring expense intelligence
     * @returns {Promise<Object>} Recurring expenses response
     */
    async getFinancialRecurringExpenses() {
        return this._request('/financial/recurring-expenses');
    }

    /**
     * GET /financial/anomalies - Get detected financial anomalies
     * @returns {Promise<Object>} Financial anomalies response
     */
    async getFinancialAnomalies() {
        return this._request('/financial/anomalies');
    }

    /**
     * GET /financial/budgets - Get budget tracking and utilization
     * @returns {Promise<Object>} Budgets response
     */
    async getFinancialBudgets() {
        return this._request('/financial/budgets');
    }

    /**
     * GET /financial/goals - Get financial goals progress
     * @returns {Promise<Object>} Financial goals response
     */
    async getFinancialGoals() {
        return this._request('/financial/goals');
    }

    /**
     * GET /financial/forecast - Get 3-month cash flow forecast
     * @returns {Promise<Object>} Cash flow forecast response
     */
    async getFinancialForecast() {
        return this._request('/financial/forecast');
    }

    /**
     * POST /financial/scenario - Simulate financial what-if scenario
     * @param {Object} payload - Scenario parameters (receivable_delay_days, expense_change_percent, additional_monthly_expense)
     * @returns {Promise<Object>} Scenario simulation response with base, scenario, and delta
     */
    async simulateFinancialScenario(payload) {
        return this._request('/financial/scenario', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    /**
     * GET /financial/recommendations - Get AI financial decision-support recommendations
     * @returns {Promise<Object>} Recommendations response
     */
    async getFinancialRecommendations() {
        return this._request('/financial/recommendations');
    }

    /**
     * POST /financial/recommendations/{id}/review - Review/acknowledge AI recommendation
     * @param {string} id - Recommendation ID
     * @param {Object} payload - Review action (action: REVIEW | APPROVE | REJECT, reviewer_notes)
     * @returns {Promise<Object>} Updated recommendation item
     */
    async reviewFinancialRecommendation(id, payload) {
        return this._request(`/financial/recommendations/${id}/review`, {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }
}

/**
 * Global API client instance
 */
let promiseLedgerAPI = null;

/**
 * Initialize the API client
 * @param {string} baseUrl - Base URL for the API
 * @returns {PromiseLedgerAPI} API client instance
 */
function initializeAPIClient(baseUrl = '') {
    if (!promiseLedgerAPI) {
        promiseLedgerAPI = new PromiseLedgerAPI(baseUrl);
    }
    return promiseLedgerAPI;
}

/**
 * Get the API client instance
 * @returns {PromiseLedgerAPI} API client instance
 */
function getAPIClient() {
    if (!promiseLedgerAPI) {
        promiseLedgerAPI = new PromiseLedgerAPI();
    }
    return promiseLedgerAPI;
}

/**
 * Export for testing environments
 */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        PromiseLedgerAPI,
        initializeAPIClient,
        getAPIClient
    };
}
