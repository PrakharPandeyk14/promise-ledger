/**
 * Utility functions for the Promise Ledger dashboard
 */

/**
 * Format a number as Indian Rupees
 * @param {number} amount - The amount to format
 * @returns {string} Formatted rupee string
 */
function formatCurrency(amount, showSign = false) {
    if (amount === null || amount === undefined) {
        return '₹ --';
    }
    const isNegative = amount < 0;
    const absVal = Math.abs(amount);
    const formatted = absVal.toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
    if (isNegative) {
        return '-₹ ' + formatted;
    }
    if (showSign && amount > 0) {
        return '+₹ ' + formatted;
    }
    return '₹ ' + formatted;
}

/**
 * Format a percentage
 * @param {number} value - The value (0-100)
 * @returns {string} Formatted percentage string
 */
function formatPercentage(value) {
    if (value === null || value === undefined) {
        return '--';
    }
    return (Math.round(value * 10000) / 100).toFixed(1) + '%';
}

/**
 * Format a decimal as a score (0-100)
 * @param {number} value - The value (0-1)
 * @returns {string} Formatted score
 */
function formatScore(value) {
    if (value === null || value === undefined) {
        return '--';
    }
    return Math.round(value * 100).toString();
}

/**
 * Get risk level class for a break probability (0-1)
 * @param {number} breakProbability - Break probability (0-1)
 * @returns {string} CSS class for risk level
 */
function getRiskClass(breakProbability) {
    if (breakProbability >= 0.67) {
        return 'risk-high';
    } else if (breakProbability >= 0.33) {
        return 'risk-medium';
    } else {
        return 'risk-low';
    }
}

/**
 * Get risk label for a break probability
 * @param {number} breakProbability - Break probability (0-1)
 * @returns {string} Risk label
 */
function getRiskLabel(breakProbability) {
    if (breakProbability >= 0.67) {
        return 'High';
    } else if (breakProbability >= 0.33) {
        return 'Medium';
    } else {
        return 'Low';
    }
}

/**
 * Get credibility level class for a credibility score (0-100)
 * @param {number} credibility - Credibility score (0-100)
 * @returns {string} CSS class for credibility level
 */
function getCredibilityClass(credibility) {
    if (credibility >= 67) {
        return 'credibility-high';
    } else if (credibility >= 33) {
        return 'credibility-medium';
    } else {
        return 'credibility-low';
    }
}

/**
 * Get credibility label for a credibility score
 * @param {number} credibility - Credibility score (0-100)
 * @returns {string} Credibility label
 */
function getCredibilityLabel(credibility) {
    if (credibility >= 67) {
        return 'High';
    } else if (credibility >= 33) {
        return 'Medium';
    } else {
        return 'Low';
    }
}

/**
 * Get priority badge class
 * @param {string} tier - Priority tier (HIGH, MEDIUM, LOW)
 * @returns {string} CSS class for priority badge
 */
function getPriorityClass(tier) {
    const tierLower = tier.toLowerCase();
    return 'priority-badge ' + tierLower;
}

/**
 * Format a date string (ISO to readable format)
 * @param {string} dateStr - ISO date string
 * @returns {string} Formatted date
 */
function formatDate(dateStr) {
    if (!dateStr) return '--';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-IN', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    } catch (e) {
        return dateStr;
    }
}

/**
 * Debounce a function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Deep clone an object
 * @param {Object} obj - Object to clone
 * @returns {Object} Cloned object
 */
function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * Validate Promise ID (should be a positive integer)
 * @param {any} promiseId - Value to validate
 * @returns {boolean} True if valid
 */
function isValidPromiseId(promiseId) {
    return Number.isInteger(promiseId) && promiseId > 0;
}

/**
 * Get action recommendation label
 * @param {string} action - Action code
 * @returns {string} Human-readable action
 */
function getActionLabel(action) {
    const labels = {
        'STOP': 'Stop - No Action',
        'HUMAN_REVIEW': 'Human Review Required',
        'ESCALATE': 'Escalate Immediately',
        'PAYMENT_PLAN': 'Offer Payment Plan',
        'FIRM_REMINDER': 'Firm Reminder',
        'SOFT_REMINDER': 'Soft Reminder'
    };
    return labels[action] || action;
}

/**
 * Get guardrail status badge class
 * @param {string} status - ALLOW, BLOCK, or OVERRIDE
 * @returns {string} CSS class
 */
function getGuardrailBadgeClass(status) {
    if (!status) return 'guardrail-badge';
    const s = status.toLowerCase();
    return `guardrail-badge ${s}`;
}

/**
 * Format a signed percentage change (e.g. -28.6% or +12.4%)
 * @param {number} value - Percentage value (e.g. -28.6)
 * @returns {string} Signed percentage string
 */
function formatSignedPercentage(value) {
    if (value === null || value === undefined) return '--';
    const sign = value > 0 ? '+' : '';
    return `${sign}${value.toFixed(1)}%`;
}

/**
 * Export functions for testing
 */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatCurrency,
        formatPercentage,
        formatScore,
        getRiskClass,
        getRiskLabel,
        getCredibilityClass,
        getCredibilityLabel,
        getPriorityClass,
        formatDate,
        debounce,
        deepClone,
        isValidPromiseId,
        getActionLabel,
        getGuardrailBadgeClass,
        formatSignedPercentage
    };
}
