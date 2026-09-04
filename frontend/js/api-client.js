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
