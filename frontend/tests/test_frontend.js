/**
 * Frontend Validation Tests for Promise Ledger Dashboard
 * Run in Node.js environment with: node tests/test_frontend.js
 */

// Mock utilities for testing
function mockDOM() {
    global.document = {
        getElementById: function(id) {
            return { textContent: '', innerHTML: '', classList: { add: () => {}, remove: () => {} } };
        },
        querySelectorAll: function() { return []; },
        querySelector: function() { return null; },
        addEventListener: function() {}
    };
    global.window = { addEventListener: function() {} };
    global.fetch = function() {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    };
}

// Test suite
const tests = [];
let passCount = 0;
let failCount = 0;

function test(name, fn) {
    tests.push({ name, fn });
}

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function assertEqual(actual, expected, message) {
    if (actual !== expected) {
        throw new Error(message || `Expected ${expected}, got ${actual}`);
    }
}

function assertTrue(value, message) {
    assert(value === true, message || `Expected true, got ${value}`);
}

function assertFalse(value, message) {
    assert(value === false, message || `Expected false, got ${value}`);
}

// ============== UTILITY FUNCTION TESTS ==============

test('formatCurrency - formats numbers as Indian Rupees', () => {
    const utils = require('./js/utils.js');
    assertEqual(utils.formatCurrency(1000), '₹ 1,000.00', 'Should format 1000 as ₹ 1,000.00');
    assertEqual(utils.formatCurrency(1000000), '₹ 10,00,000.00', 'Should use Indian number format');
    assertEqual(utils.formatCurrency(0), '₹ 0.00', 'Should format zero');
});

test('formatCurrency - handles null/undefined', () => {
    const utils = require('./js/utils.js');
    assertEqual(utils.formatCurrency(null), '₹ --', 'Should return ₹ -- for null');
    assertEqual(utils.formatCurrency(undefined), '₹ --', 'Should return ₹ -- for undefined');
});

test('formatPercentage - formats decimals as percentages', () => {
    const utils = require('./js/utils.js');
    assertEqual(utils.formatPercentage(0.5), '50.0%', 'Should format 0.5 as 50.0%');
    assertEqual(utils.formatPercentage(0.333), '33.3%', 'Should round correctly');
    assertEqual(utils.formatPercentage(1), '100.0%', 'Should format 1 as 100.0%');
});

test('formatScore - formats decimals as 0-100 scores', () => {
    const utils = require('./js/utils.js');
    assertEqual(utils.formatScore(0.75), '75', 'Should format 0.75 as 75');
    assertEqual(utils.formatScore(0.5), '50', 'Should format 0.5 as 50');
    assertEqual(utils.formatScore(0.999), '100', 'Should round up 0.999 to 100');
});

test('getRiskClass - returns correct risk CSS class', () => {
    const utils = require('./js/utils.js');
    assertEqual(utils.getRiskClass(0.75), 'risk-high', 'Should classify 0.75 as high');
    assertEqual(utils.getRiskClass(0.5), 'risk-medium', 'Should classify 0.5 as medium');
    assertEqual(utils.getRiskClass(0.2), 'risk-low', 'Should classify 0.2 as low');
});

test('getRiskLabel - returns human-readable risk label', () => {
    const utils = require('./js/utils.js');
    assertEqual(utils.getRiskLabel(0.75), 'High', 'Should label 0.75 as High');
    assertEqual(utils.getRiskLabel(0.5), 'Medium', 'Should label 0.5 as Medium');
    assertEqual(utils.getRiskLabel(0.2), 'Low', 'Should label 0.2 as Low');
});

test('getCredibilityClass - returns correct credibility CSS class', () => {
    const utils = require('./js/utils.js');
    assertEqual(utils.getCredibilityClass(80), 'credibility-high', 'Should classify 80 as high');
    assertEqual(utils.getCredibilityClass(50), 'credibility-medium', 'Should classify 50 as medium');
    assertEqual(utils.getCredibilityClass(20), 'credibility-low', 'Should classify 20 as low');
});

test('getPriorityClass - returns priority badge class', () => {
    const utils = require('./js/utils.js');
    assertEqual(utils.getPriorityClass('HIGH'), 'priority-badge high', 'Should format HIGH priority');
    assertEqual(utils.getPriorityClass('MEDIUM'), 'priority-badge medium', 'Should format MEDIUM priority');
    assertEqual(utils.getPriorityClass('LOW'), 'priority-badge low', 'Should format LOW priority');
});

test('formatDate - converts ISO dates to readable format', () => {
    const utils = require('./js/utils.js');
    const result = utils.formatDate('2024-09-04');
    assertTrue(result.includes('2024') || result.includes('Sep'), 'Should contain year or month');
    assertEqual(utils.formatDate(null), '--', 'Should return -- for null');
    assertEqual(utils.formatDate(''), '--', 'Should return -- for empty string');
});

test('isValidPromiseId - validates promise IDs', () => {
    const utils = require('./js/utils.js');
    assertTrue(utils.isValidPromiseId(1), 'Should accept positive integer');
    assertTrue(utils.isValidPromiseId(100), 'Should accept larger integers');
    assertFalse(utils.isValidPromiseId(0), 'Should reject zero');
    assertFalse(utils.isValidPromiseId(-1), 'Should reject negative integers');
    assertFalse(utils.isValidPromiseId(1.5), 'Should reject decimals');
    assertFalse(utils.isValidPromiseId('1'), 'Should reject strings');
});

test('getActionLabel - converts action codes to labels', () => {
    const utils = require('./js/utils.js');
    assertEqual(utils.getActionLabel('STOP'), 'Stop - No Action', 'Should label STOP');
    assertEqual(utils.getActionLabel('ESCALATE'), 'Escalate Immediately', 'Should label ESCALATE');
    assertEqual(utils.getActionLabel('PAYMENT_PLAN'), 'Offer Payment Plan', 'Should label PAYMENT_PLAN');
});

test('debounce - debounces function calls', (done) => {
    const utils = require('./js/utils.js');
    let callCount = 0;
    
    const fn = () => { callCount++; };
    const debounced = utils.debounce(fn, 50);
    
    debounced();
    debounced();
    debounced();
    
    assertEqual(callCount, 0, 'Should not call immediately');
    
    setTimeout(() => {
        assertEqual(callCount, 1, 'Should call once after debounce period');
        done();
    }, 100);
});

test('deepClone - creates independent copy of object', () => {
    const utils = require('./js/utils.js');
    const original = { a: 1, b: { c: 2 } };
    const clone = utils.deepClone(original);
    
    clone.a = 99;
    clone.b.c = 99;
    
    assertEqual(original.a, 1, 'Original should not be modified');
    assertEqual(original.b.c, 2, 'Original nested should not be modified');
});

// ============== API CLIENT TESTS ==============

test('PromiseLedgerAPI - initializes with base URL', () => {
    const { PromiseLedgerAPI } = require('./js/api-client.js');
    const api = new PromiseLedgerAPI('http://example.com');
    assertEqual(api.baseUrl, 'http://example.com', 'Should set base URL');
});

test('PromiseLedgerAPI - validates promise ID in getOpportunityDetail', () => {
    const { PromiseLedgerAPI } = require('./js/api-client.js');
    const api = new PromiseLedgerAPI();
    
    try {
        api.getOpportunityDetail(-1);
        assert(false, 'Should throw error for invalid ID');
    } catch (e) {
        assertTrue(e.message.includes('Invalid'), 'Should throw Invalid promise ID error');
    }
});

test('PromiseLedgerAPI - validates promise ID in evaluateOpportunity', () => {
    const { PromiseLedgerAPI } = require('./js/api-client.js');
    const api = new PromiseLedgerAPI();
    
    try {
        api.evaluateOpportunity('abc');
        assert(false, 'Should throw error for invalid ID');
    } catch (e) {
        assertTrue(e.message.includes('Invalid'), 'Should throw Invalid promise ID error');
    }
});

test('initializeAPIClient - creates singleton instance', () => {
    const { initializeAPIClient, getAPIClient } = require('./js/api-client.js');
    
    // Reset global state
    global.promiseLedgerAPI = null;
    
    const api1 = initializeAPIClient('http://test.com');
    const api2 = getAPIClient();
    
    assertEqual(api1, api2, 'Should return same instance');
    assertEqual(api1.baseUrl, 'http://test.com', 'Should preserve URL');
});

// ============== INTEGRATION TESTS ==============

test('Frontend files exist and are valid', () => {
    const fs = require('fs');
    const path = require('path');
    
    const files = [
        'frontend/index.html',
        'frontend/css/dashboard.css',
        'frontend/js/utils.js',
        'frontend/js/api-client.js',
        'frontend/js/app.js'
    ];
    
    for (const file of files) {
        const fullPath = path.join(__dirname, '..', file);
        assertTrue(fs.existsSync(fullPath), `File should exist: ${file}`);
        
        const content = fs.readFileSync(fullPath, 'utf-8');
        assertTrue(content.length > 0, `File should not be empty: ${file}`);
    }
});

test('HTML contains required dashboard sections', () => {
    const fs = require('fs');
    const path = require('path');
    const html = fs.readFileSync(path.join(__dirname, '..', 'frontend/index.html'), 'utf-8');
    
    assertTrue(html.includes('portfolio-overview'), 'Should contain portfolio overview section');
    assertTrue(html.includes('opportunities-table'), 'Should contain opportunities table');
    assertTrue(html.includes('detail-panel'), 'Should contain detail panel');
    assertTrue(html.includes('healthIndicator'), 'Should contain health indicator');
    assertTrue(html.includes('id="totalOutstanding"'), 'Should have total outstanding metric');
    assertTrue(html.includes('id="expectedRecovery"'), 'Should have expected recovery metric');
    assertTrue(html.includes('id="atRiskCount"'), 'Should have at-risk count metric');
    assertTrue(html.includes('Money at Risk (Outstanding)'), 'Should label portfolio exposure as money at risk');
    assertTrue(html.includes('Expected Recovery Rate'), 'Should label the recovery ratio explicitly');
    assertTrue(html.includes('Break Probability'), 'Should label break probability explicitly');
    assertTrue(html.includes('Credibility Score / 100'), 'Should label credibility score units');
});

test('CSS contains required styling classes', () => {
    const fs = require('fs');
    const path = require('path');
    const css = fs.readFileSync(path.join(__dirname, '..', 'frontend/css/dashboard.css'), 'utf-8');
    
    assertTrue(css.includes('.metrics-grid'), 'Should style metrics grid');
    assertTrue(css.includes('.opportunities-table'), 'Should style table');
    assertTrue(css.includes('.detail-panel'), 'Should style detail panel');
    assertTrue(css.includes('.risk-high'), 'Should have high risk styling');
    assertTrue(css.includes('.priority-badge'), 'Should have priority badge styling');
    assertTrue(css.includes('₹'), 'Should mention rupee symbol in CSS');
});

test('JavaScript files have no syntax errors', () => {
    const fs = require('fs');
    const path = require('path');
    
    const jsFiles = [
        'frontend/js/utils.js',
        'frontend/js/api-client.js'
    ];
    
    for (const file of jsFiles) {
        const fullPath = path.join(__dirname, '..', file);
        const content = fs.readFileSync(fullPath, 'utf-8');
        
        try {
            new Function(content);
            assertTrue(true, `${file} is valid JavaScript`);
        } catch (e) {
            throw new Error(`${file} has syntax error: ${e.message}`);
        }
    }
});

test('Dashboard evaluation displays the complete demo result', () => {
    const fs = require('fs');
    const path = require('path');
    const app = fs.readFileSync(path.join(__dirname, '..', 'frontend/js/app.js'), 'utf-8');

    assertTrue(app.includes('Recommended Action'), 'Should display the recommendation');
    assertTrue(app.includes('Promise Credibility Score'), 'Should display promise credibility');
    assertTrue(app.includes('formatPercentage(evaluation.break_probability)'), 'Should display break probability');
    assertTrue(app.includes('formatPercentage(evaluation.recovery_probability)'), 'Should display recovery probability');
    assertTrue(app.includes('Guardrail Status'), 'Should display guardrail status');
    assertTrue(app.includes('Guardrail Reason'), 'Should display guardrail reason');
    assertTrue(app.includes('Execution Status'), 'Should display execution status');
    assertTrue(app.includes('Audit ID'), 'Should display deterministic audit ID');
    assertTrue(app.includes('formatCurrency(evaluation.expected_recovery)'), 'Should display expected recovery in rupees');
});

// ============== RUN TESTS ==============

async function runTests() {
    console.log('🧪 Running Promise Ledger Frontend Validation Tests\n');
    console.log('=' .repeat(60));
    
    for (const { name, fn } of tests) {
        try {
            await Promise.resolve(fn());
            console.log(`✅ ${name}`);
            passCount++;
        } catch (error) {
            console.log(`❌ ${name}`);
            console.log(`   Error: ${error.message}\n`);
            failCount++;
        }
    }
    
    console.log('=' .repeat(60));
    console.log(`\n📊 Test Results: ${passCount} passed, ${failCount} failed (Total: ${tests.length})\n`);
    
    if (failCount === 0) {
        console.log('🎉 All frontend validation tests passed!\n');
    } else {
        console.log(`⚠️  ${failCount} test(s) failed.\n`);
        process.exit(1);
    }
}

// Run if executed as main module
if (require.main === module) {
    runTests().catch(err => {
        console.error('Test runner error:', err);
        process.exit(1);
    });
}

module.exports = { test, assert, assertEqual, assertTrue, assertFalse };
