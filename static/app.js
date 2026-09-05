/**
 * FortressFi - Adaptive Risk-Guardrail Portfolio Engine
 * Minimalist Institutional FinTech Control Center
 * Modern Vanilla JavaScript (ES6+) Implementation
 */

// ─── 1. Global State & Architecture Constants ──────────────────────────────

let ws = null;
let navChart = null;
let allocationChart = null;
let isRunning = false;
let allDecisions = [];
let navData = {
    labels: [0],
    values: [100000000],
    events: {}
};

let lastKnownState = {
    day: 0,
    regime: 'NORMAL',
    portfolio: null,
    risk_metrics: null,
    guardrail: null,
    latest_decisions: []
};

const ASSET_NAMES = [
    'US Equity',
    'Intl Equity',
    'Govt Bonds',
    'Corp Bonds',
    'Commodities',
    'Cash'
];

const BASE_WEIGHTS = [0.30, 0.15, 0.25, 0.10, 0.10, 0.10];

const ASSET_COLORS = [
    '#3B82F6', // US Equity: Blue
    '#8B5CF6', // Intl Equity: Purple
    '#10B981', // Govt Bonds: Emerald
    '#06B6D4', // Corp Bonds: Cyan
    '#F59E0B', // Commodities: Amber
    '#64748B', // Cash: Slate Gray
];

const PRESET_SHOCKS = {
    normal: {
        'US Equity': 2,
        'Intl Equity': 1,
        'Govt Bonds': 1,
        'Corp Bonds': 1,
        'Commodities': 0,
        'Cash': 0
    },
    crash: {
        'US Equity': -25,
        'Intl Equity': -30,
        'Govt Bonds': 5,
        'Corp Bonds': -8,
        'Commodities': -15,
        'Cash': 0
    },
    rates: {
        'US Equity': -5,
        'Intl Equity': -3,
        'Govt Bonds': -12,
        'Corp Bonds': -10,
        'Commodities': 3,
        'Cash': 0
    },
    recovery: {
        'US Equity': 18,
        'Intl Equity': 15,
        'Govt Bonds': -4,
        'Corp Bonds': 5,
        'Commodities': 10,
        'Cash': 0
    }
};

const $ = (id) => document.getElementById(id);

// ─── 2. Application Bootstrap ──────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    buildInitialAllocationList();
    bindSimulationControls();
    connectWebSocket();
    loadInitialState();
});

// ─── 3. WebSocket Network Stream ───────────────────────────────────────────

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/live`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        updateConnectionStatus(true);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (err) {
            console.error('[WS] Parse error:', err);
        }
    };

    ws.onclose = () => {
        updateConnectionStatus(false);
        setTimeout(connectWebSocket, 2000);
    };

    ws.onerror = () => {
        updateConnectionStatus(false);
    };
}

function updateConnectionStatus(connected) {
    const pulse = $('connection-pulse');
    const text = $('connection-text');

    if (connected) {
        if (pulse) {
            pulse.style.background = '#10B981';
            pulse.style.boxShadow = '0 0 8px #10B981';
        }
        if (text) {
            text.textContent = 'LIVE';
            text.style.color = '#10B981';
        }
    } else {
        if (pulse) {
            pulse.style.background = '#F59E0B';
            pulse.style.boxShadow = '0 0 8px #F59E0B';
        }
        if (text) {
            text.textContent = 'CONNECTING';
            text.style.color = '#F59E0B';
        }
    }
}

// ─── 4. Message Dispatcher & Tick Processing ───────────────────────────────

function handleMessage(data) {
    switch (data.type) {
        case 'connected':
            if (data.portfolio) {
                lastKnownState.portfolio = data.portfolio;
                updatePortfolio(data.portfolio, null);
            }
            break;

        case 'tick':
            handleTick(data);
            break;

        case 'simulation_complete':
            isRunning = false;
            updateControlButtons();
            setAlertAction(`Simulation completed at Day ${data.day}. Reset scenario or stress-test via What-If Lab.`);
            break;

        case 'reset':
            handleReset(data);
            break;

        default:
            break;
    }
}

function handleTick(data) {
    lastKnownState = data;

    if (data.latest_decisions && data.latest_decisions.length > 0) {
        data.latest_decisions.forEach(d => {
            if (!allDecisions.some(existing => existing.day === d.day && existing.action_type === d.action_type)) {
                allDecisions.unshift(d);
            }
        });
    }

    const level = data.guardrail ? data.guardrail.level : 'MONITOR';

    // 1. Header indicators
    updateHeaderStatus(data.day, data.regime, level);

    // 2. Portfolio overview + Status bar
    updatePortfolio(data.portfolio, data.guardrail);

    // 3. Risk Guardrail Status Pipeline
    updateGuardrailPipeline(data.guardrail);

    // 4. Live NAV Chart & Event points
    updateNAVChart(data.day, data.portfolio.nav, level, data.latest_decisions);

    // 5. Allocation Donut & List
    updateAllocationDisplay(data.portfolio.weights, data.portfolio.nav);

    // 6. Unified Risk Overview
    updateRiskOverview(data.risk_metrics, data.guardrail);

    // 7. System Decision Engine (5-Stage Autonomous Risk Flow)
    updateDecisionEngine(allDecisions, data.guardrail, data.portfolio, data.day, data.latest_decisions);

    // 8. Recent Actions (Max 3 Items)
    updateRecentActions(allDecisions);
}

function handleReset(data) {
    navData = {
        labels: [0],
        values: [data.portfolio.nav || 100000000],
        events: {}
    };
    allDecisions = [];
    lastKnownState = {
        day: 0,
        regime: 'NORMAL',
        portfolio: data.portfolio,
        risk_metrics: null,
        guardrail: null,
        latest_decisions: []
    };

    updateHeaderStatus(0, 'NORMAL', 'MONITOR');
    updatePortfolio(data.portfolio, null);
    resetCharts();
    resetGuardrailPipeline();
    updateAllocationDisplay(data.portfolio.weights, data.portfolio.nav);
    updateRiskOverview(null, null);
    updateSystemDecision([], null, data.portfolio, 0);
    updateRecentActions([]);

    setAlertAction('All risk metrics operating within configured limits. Dynamic drift optimization active.');
    isRunning = false;
    updateControlButtons();
}

// ─── 5. Top Navigation Header ──────────────────────────────────────────────

function updateHeaderStatus(day, regime, level) {
    const dayEl = $('header-day');
    if (dayEl) dayEl.textContent = day;

    const regimeEl = $('regime-badge');
    if (regimeEl) {
        regimeEl.textContent = regime;
        regimeEl.className = `regime-badge ${regime}`;
    }

    const guardrailEl = $('header-guardrail-level');
    if (guardrailEl) {
        guardrailEl.textContent = level === 'CIRCUIT_BREAK' ? 'CIRCUIT BREAK' : level;
        guardrailEl.className = `guardrail-badge ${level}`;
    }
}

// ─── 6. Portfolio Overview & Elegant Status ────────────────────────────────

function updatePortfolio(portfolio, guardrail) {
    if (!portfolio) return;

    // Primary NAV Headline
    const navEl = $('header-nav');
    if (navEl) {
        navEl.textContent = formatCurrency(portfolio.nav);
    }

    // Donut Center NAV Label
    const donutNav = $('donut-center-nav');
    if (donutNav) {
        donutNav.textContent = formatCompactCurrency(portfolio.nav);
    }

    // Daily P&L
    const pnlEl = $('header-pnl');
    if (pnlEl) {
        const isPos = portfolio.daily_pnl >= 0;
        const sign = isPos ? '+' : '';
        pnlEl.textContent = `${sign}${formatCurrency(portfolio.daily_pnl)}`;
        pnlEl.className = `sub-val tabular-nums ${isPos ? 'positive' : 'negative'}`;
    }

    // Cumulative Return
    const cumEl = $('header-cumulative');
    if (cumEl) {
        const isPos = portfolio.cumulative_return >= 0;
        const sign = isPos ? '+' : '';
        cumEl.textContent = `${sign}${portfolio.cumulative_return.toFixed(2)}%`;
        cumEl.className = `sub-val tabular-nums ${isPos ? 'positive' : 'negative'}`;
    }

    // Risk-Adjusted: Sharpe & Sortino
    const sharpeEl = $('perf-sharpe');
    if (sharpeEl) sharpeEl.textContent = (portfolio.sharpe_ratio || 0).toFixed(2);

    const sortinoEl = $('perf-sortino');
    if (sortinoEl) sortinoEl.textContent = (portfolio.sortino_ratio || 0).toFixed(2);

    // Text-based Portfolio Status Bar
    updatePortfolioStatusBar(guardrail, portfolio);
}

function updatePortfolioStatusBar(guardrail, portfolio) {
    const container = $('portfolio-status-container');
    const dot = $('status-dot');
    const headline = $('status-headline');
    const desc = $('status-desc');

    if (!container || !dot || !headline) return;

    const level = guardrail ? guardrail.level : 'MONITOR';

    if (level === 'CIRCUIT_BREAK') {
        container.className = 'status-indicator-wrap';
        dot.className = 'status-indicator-dot danger';
        headline.textContent = 'CIRCUIT BREAK';
        headline.className = 'status-headline danger';
        if (desc) desc.textContent = 'Portfolio locked in defensive asset floor.';
    } else if (level === 'ACT') {
        container.className = 'status-indicator-wrap';
        dot.className = 'status-indicator-dot danger';
        headline.textContent = 'DEFENSIVE ACT';
        headline.className = 'status-headline danger';
        if (desc) desc.textContent = 'Tail risk escalation detected. Scaled down equity 30%.';
    } else if (level === 'WARN') {
        container.className = 'status-indicator-wrap';
        dot.className = 'status-indicator-dot warn';
        headline.textContent = 'ALERT WARN';
        headline.className = 'status-headline warn';
        if (desc) desc.textContent = 'Portfolio approaching risk threshold.';
    } else {
        container.className = 'status-indicator-wrap';
        dot.className = 'status-indicator-dot safe';
        headline.textContent = 'STABLE';
        headline.className = 'status-headline';
        if (desc) desc.textContent = 'All risk metrics operating within configured limits.';
    }
}

// ─── 7. Risk Guardrail Status Pipeline ─────────────────────────────────────

function updateGuardrailPipeline(guardrail) {
    const level = guardrail ? guardrail.level : 'MONITOR';

    const stages = [
        { id: 'node-monitor', key: 'MONITOR' },
        { id: 'node-warn', key: 'WARN' },
        { id: 'node-act', key: 'ACT' },
        { id: 'node-circuit', key: 'CIRCUIT_BREAK' },
    ];

    stages.forEach(st => {
        const el = $(st.id);
        if (el) {
            if (st.key === level) {
                el.classList.add('active');
            } else {
                el.classList.remove('active');
            }
        }
    });

    if (guardrail && guardrail.explanation) {
        setAlertAction(formatExecutiveExplanation(guardrail.explanation, level, level));
    }
}

function resetGuardrailPipeline() {
    const stages = ['node-monitor', 'node-warn', 'node-act', 'node-circuit'];
    stages.forEach(id => {
        const el = $(id);
        if (el) el.classList.remove('active');
    });

    const monitorStage = $('node-monitor');
    if (monitorStage) monitorStage.classList.add('active');
}

function setAlertAction(msg) {
    const textEl = $('alert-text');
    if (textEl) textEl.textContent = msg;
}

// ─── 8. Live Portfolio Performance Chart ───────────────────────────────────

function initCharts() {
    Chart.defaults.color = '#94A3B8';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.04)';
    Chart.defaults.font.family = "'JetBrains Mono', monospace";
    Chart.defaults.font.size = 11;

    initNavChart();
    initAllocationDonut();
}

function initNavChart() {
    const canvas = $('nav-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const gradient = ctx.createLinearGradient(0, 0, 0, 240);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.22)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0.00)');

    navData = {
        labels: [0],
        values: [100000000],
        events: {}
    };

    navChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: navData.labels,
            datasets: [{
                label: 'Portfolio NAV',
                data: navData.values,
                borderColor: '#3B82F6',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                pointRadius: (ctx) => {
                    const idx = ctx.dataIndex;
                    const day = navData.labels[idx];
                    return navData.events[day] ? 6 : 0;
                },
                pointHoverRadius: 8,
                pointBackgroundColor: (ctx) => {
                    const idx = ctx.dataIndex;
                    const day = navData.labels[idx];
                    const ev = navData.events[day];
                    if (!ev) return '#3B82F6';
                    if (ev.type === 'CIRCUIT_BREAK' || ev.type === 'GUARDRAIL_CIRCUIT_BREAK') return '#DC2626';
                    if (ev.type === 'GUARDRAIL_ACT') return '#EF4444';
                    if (ev.type === 'GUARDRAIL_WARN') return '#F59E0B';
                    return '#10B981';
                },
                pointBorderColor: '#FFFFFF',
                pointBorderWidth: 1.5,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            layout: {
                padding: { bottom: 6, top: 8, left: 4, right: 8 }
            },
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#0D1522',
                    titleColor: '#F8FAFC',
                    bodyColor: '#94A3B8',
                    borderColor: 'rgba(59, 130, 246, 0.3)',
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: 6,
                    displayColors: false,
                    callbacks: {
                        title: (items) => `TRADING DAY ${items[0].label}`,
                        label: (ctx) => {
                            const val = ctx.parsed.y;
                            const init = navData.values[0] || 100000000;
                            const ret = ((val - init) / init) * 100;
                            const day = navData.labels[ctx.dataIndex];
                            const lines = [
                                `NAV: ${formatCurrency(val)} (${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%)`,
                            ];
                            const ev = navData.events[day];
                            if (ev) {
                                lines.push(`EVENT: ${ev.icon} ${ev.title}`);
                                lines.push(`ACTION: ${ev.action}`);
                            }
                            return lines;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.03)',
                        borderDash: [4, 4],
                    },
                    ticks: {
                        color: '#64748B',
                        maxTicksLimit: 12,
                        maxRotation: 0,
                    }
                },
                y: {
                    position: 'left',
                    grid: {
                        color: 'rgba(255, 255, 255, 0.03)',
                        borderDash: [4, 4],
                    },
                    ticks: {
                        color: '#64748B',
                        callback: (v) => `$${(v / 1e6).toFixed(1)}M`,
                    }
                }
            }
        }
    });
}

function updateNAVChart(day, nav, level, decisions) {
    if (!navChart) return;

    navData.labels.push(day);
    navData.values.push(nav);

    // Register rich audit events on chart
    if (decisions && decisions.length > 0) {
        decisions.forEach(d => {
            if (d.day === day) {
                if (d.action_type === 'REBALANCE') {
                    navData.events[day] = {
                        icon: '🔄',
                        title: 'Automatic Rebalance',
                        action: 'Portfolio allocation optimized to offset drift.',
                        type: 'REBALANCE'
                    };
                } else if (d.action_type === 'GUARDRAIL_WARN') {
                    navData.events[day] = {
                        icon: '⚠',
                        title: 'Guardrail Warning',
                        action: 'Volatility buffer alert triggered; solver sensitivity increased.',
                        type: 'GUARDRAIL_WARN'
                    };
                } else if (d.action_type === 'GUARDRAIL_ACT') {
                    navData.events[day] = {
                        icon: '⚡',
                        title: 'Defensive De-Risking',
                        action: 'Forced equity exposure reduction (-30%) into bonds and cash.',
                        type: 'GUARDRAIL_ACT'
                    };
                } else if (d.action_type === 'CIRCUIT_BREAK' || d.action_type === 'GUARDRAIL_CIRCUIT_BREAK') {
                    navData.events[day] = {
                        icon: '🛑',
                        title: 'Circuit Breaker Lock',
                        action: 'Emergency capital floor enforced (60% Govt Bonds, 40% Cash).',
                        type: 'CIRCUIT_BREAK'
                    };
                }
            }
        });
    }

    if (navData.labels.length > 300) {
        const droppedDay = navData.labels.shift();
        navData.values.shift();
        delete navData.events[droppedDay];
    }

    navChart.data.labels = navData.labels;
    navChart.data.datasets[0].data = navData.values;

    // Dynamic line stroke color
    if (level === 'CIRCUIT_BREAK') {
        navChart.data.datasets[0].borderColor = '#EF4444';
    } else if (level === 'ACT') {
        navChart.data.datasets[0].borderColor = '#F97316';
    } else if (level === 'WARN') {
        navChart.data.datasets[0].borderColor = '#F59E0B';
    } else {
        navChart.data.datasets[0].borderColor = '#3B82F6';
    }

    navChart.update('none');
}

function resetCharts() {
    navData = {
        labels: [0],
        values: [100000000],
        events: {}
    };
    if (navChart) {
        navChart.data.labels = navData.labels;
        navChart.data.datasets[0].data = navData.values;
        navChart.data.datasets[0].borderColor = '#3B82F6';
        navChart.update();
    }

    if (allocationChart) {
        allocationChart.data.datasets[0].data = BASE_WEIGHTS.map(w => w * 100);
        allocationChart.update();
    }

    $('header-nav').textContent = '$100.00M';
    $('header-pnl').textContent = '+$0';
    $('header-pnl').className = 'item-val tabular-nums positive';
    $('header-cumulative').textContent = '+0.00%';
    $('header-cumulative').className = 'item-val tabular-nums positive';
    $('header-day').textContent = '0';
    $('perf-sharpe').textContent = '0.00';
    $('perf-sortino').textContent = '0.00';
}

// ─── 9. Portfolio Allocation (Donut + Clean List) ──────────────────────────

function initAllocationDonut() {
    const canvas = $('allocation-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    allocationChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ASSET_NAMES,
            datasets: [{
                data: BASE_WEIGHTS.map(w => w * 100),
                backgroundColor: ASSET_COLORS,
                borderColor: '#111A29',
                borderWidth: 2,
                hoverOffset: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '74%',
            animation: { duration: 200 },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#111A29',
                    titleColor: '#F8FAFC',
                    bodyColor: '#94A3B8',
                    borderColor: 'rgba(255, 255, 255, 0.12)',
                    borderWidth: 1,
                    padding: 8,
                    cornerRadius: 4,
                    callbacks: {
                        label: (ctx) => ` ${ctx.label}: ${parseFloat(ctx.parsed).toFixed(1)}%`
                    }
                }
            }
        }
    });
}

function buildInitialAllocationList() {
    const container = $('allocation-list');
    if (!container) return;

    container.innerHTML = ASSET_NAMES.map((name, i) => {
        const basePct = (BASE_WEIGHTS[i] * 100).toFixed(1);
        return `
            <div class="alloc-row" id="alloc-row-${i}">
                <div class="alloc-name">
                    <span class="asset-swatch" style="background: ${ASSET_COLORS[i]};"></span>
                    <span title="${name}">${name}</span>
                </div>
                <div class="alloc-bar-track">
                    <div class="alloc-bar-fill" id="alloc-bar-${i}" style="background: ${ASSET_COLORS[i]}; width: ${basePct}%;"></div>
                </div>
                <div class="alloc-pct tabular-nums" id="alloc-pct-${i}">${basePct}%</div>
                <div class="alloc-drift tabular-nums flat" id="alloc-delta-${i}">0.0%</div>
            </div>
        `;
    }).join('');
}

function updateAllocationDisplay(weights, nav) {
    if (!weights || weights.length === 0) return;

    // 1. Donut Update
    if (allocationChart) {
        allocationChart.data.datasets[0].data = weights.map(w => +(w * 100).toFixed(1));
        allocationChart.update('none');
    }

    // 2. Rows Update
    weights.forEach((w, i) => {
        const pct = w * 100;
        const delta = (w - BASE_WEIGHTS[i]) * 100;

        const bar = $(`alloc-bar-${i}`);
        const pctEl = $(`alloc-pct-${i}`);
        const deltaEl = $(`alloc-delta-${i}`);

        if (bar) bar.style.width = `${Math.min(pct, 100)}%`;
        if (pctEl) pctEl.textContent = `${pct.toFixed(1)}%`;

        if (deltaEl) {
            if (delta > 0.3) {
                deltaEl.textContent = `↑ ${delta.toFixed(1)}%`;
                deltaEl.className = 'alloc-drift tabular-nums up';
            } else if (delta < -0.3) {
                deltaEl.textContent = `↓ ${Math.abs(delta).toFixed(1)}%`;
                deltaEl.className = 'alloc-drift tabular-nums down';
            } else {
                deltaEl.textContent = '0.0%';
                deltaEl.className = 'alloc-drift tabular-nums flat';
            }
        }
    });
}

// ─── 10. Unified Risk Overview (Gauges + Governance Telemetry) ─────────────

function updateRiskOverview(metrics, guardrail) {
    const thresholds = (guardrail && guardrail.thresholds) ? guardrail.thresholds : {
        var_95: 1.80,
        cvar_95: 2.80,
        max_drawdown: 12.00,
        concentration_hhi: 35.00
    };

    const varVal = metrics ? (metrics.var_95 || 0) : 0;
    const cvarVal = metrics ? (metrics.cvar_95 || 0) : 0;
    const ddVal = metrics ? (metrics.current_drawdown || 0) : 0;
    const hhiVal = metrics ? (metrics.concentration_hhi || 0) : 0;

    renderRiskBar('var', varVal, thresholds.var_95, '%');
    renderRiskBar('cvar', cvarVal, thresholds.cvar_95, '%');
    renderRiskBar('dd', ddVal, thresholds.max_drawdown, '%');
    renderRiskBar('hhi', hhiVal, thresholds.concentration_hhi, '');

    // Overall Status Pill
    const level = guardrail ? guardrail.level : 'MONITOR';
    const statusPill = $('risk-gate-status');
    const summarySentence = $('risk-summary-sentence');

    if (statusPill) {
        if (level === 'CIRCUIT_BREAK') {
            statusPill.textContent = 'CRITICAL ●';
            statusPill.className = 'status-pill-safe danger';
        } else if (level === 'ACT') {
            statusPill.textContent = 'DEFENSIVE ●';
            statusPill.className = 'status-pill-safe danger';
        } else if (level === 'WARN') {
            statusPill.textContent = 'WARNING ●';
            statusPill.className = 'status-pill-safe warn';
        } else {
            statusPill.textContent = 'SAFE ●';
            statusPill.className = 'status-pill-safe';
        }
    }

    if (summarySentence) {
        if (level === 'CIRCUIT_BREAK') {
            summarySentence.textContent = 'Drawdown ceiling reached. Emergency circuit breaker active.';
        } else if (level === 'ACT') {
            summarySentence.textContent = 'Tail risk (CVaR) exceeded guardrail limit. Automatic de-risking in effect.';
        } else if (level === 'WARN') {
            summarySentence.textContent = 'Risk metrics approaching upper thresholds. Solver sensitivity increased.';
        } else {
            summarySentence.textContent = 'All metrics operating within conservative risk boundaries.';
        }
    }
}

function renderRiskBar(key, value, limit, suffix) {
    const valEl = $(`val-${key}`);
    const subEl = $(`sub-${key}`);
    const barEl = $(`bar-${key}`);
    const valAlt = $(`val-${key}-alt`);
    const barAlt = $(`bar-${key}-alt`);

    const ratio = limit > 0 ? (value / limit) : 0;
    const pctOfLimit = Math.round(ratio * 100);

    if (valEl) valEl.textContent = `${value.toFixed(2)}${suffix}`;
    if (valAlt) valAlt.textContent = `${value.toFixed(2)}${suffix}`;
    if (subEl) subEl.textContent = `${pctOfLimit}% of ${limit.toFixed(2)}${suffix} limit`;

    const applyBar = (el) => {
        if (!el) return;
        el.style.width = `${Math.min(pctOfLimit, 100)}%`;
        if (ratio >= 1.0) {
            el.className = el.className.includes('gauge-fill') ? 'gauge-fill danger' : 'mini-bar-fill danger';
        } else if (ratio >= 0.8) {
            el.className = el.className.includes('gauge-fill') ? 'gauge-fill warn' : 'mini-bar-fill warn';
        } else {
            el.className = el.className.includes('gauge-fill') ? 'gauge-fill safe' : 'mini-bar-fill safe';
        }
    };
    applyBar(barEl);
    applyBar(barAlt);
}

// ─── 11. 🧠 ARGPE DECISION ENGINE (Signature Autonomous Risk System) ─────────

let activeDecisionForReceipt = null;

function updateDecisionEngine(decisions, guardrail, portfolio, day, latestDecisions) {
    const valid = decisions ? decisions.filter(d => d.day > 0 || d.action_type === 'INIT') : [];
    const latest = valid.length > 0 ? valid[0] : null;
    activeDecisionForReceipt = latest;

    // Spotlight Elements (Integrated UI)
    const dayEl = $('intel-day');
    const typeEl = $('intel-action-type');
    const summaryEl = $('intel-explanation');
    const whyEl = $('intel-why');
    const actionEl = $('intel-action');
    const resultEl = $('intel-result');

    if (dayEl) dayEl.textContent = `DAY ${latest ? latest.day : (day || 0)}`;

    const lastBadge = $('engine-last-decision');
    const statusPill = $('engine-status-pill');
    const statusDot = $('engine-status-dot');
    const statusText = $('engine-status-text');

    // Stage elements
    const sigMetric = $('signal-metric');
    const sigText = $('signal-text');
    const anaStatus = $('analysis-status');
    const anaText = $('analysis-text');
    const decChip = $('decision-type-chip');
    const decText = $('decision-text');
    const actTarget = $('action-target');
    const actText = $('action-text');
    const valTag = $('validation-tag');
    const valText = $('validation-text');
    const whyList = $('why-points-list');

    // Determine if an action took place on this tick
    const hasTickAction = latestDecisions && latestDecisions.length > 0;

    // 1. Header & Live Status Pill
    if (statusPill && statusDot && statusText) {
        if (hasTickAction) {
            statusPill.className = 'engine-live-status-pill processing';
            statusDot.textContent = '●';
            statusText.textContent = 'PROCESSING';
            const flowCards = document.querySelectorAll('.flow-card');
            flowCards.forEach(fc => fc.classList.add('is-calculating'));
            setTimeout(() => {
                flowCards.forEach(fc => fc.classList.remove('is-calculating'));
            }, 600);
            setTimeout(() => {
                if (statusPill && statusPill.className.includes('processing')) {
                    statusPill.className = 'engine-live-status-pill';
                    statusDot.textContent = '●';
                    statusText.textContent = 'DECISION COMPLETE';
                }
            }, 1200);
        } else if (isRunning) {
            statusPill.className = 'engine-live-status-pill monitoring';
            statusDot.textContent = '●';
            statusText.textContent = 'MONITORING';
        } else {
            statusPill.className = 'engine-live-status-pill';
            statusDot.textContent = '●';
            statusText.textContent = 'DECISION COMPLETE';
        }
    }

    if (lastBadge) {
        if (!latest) {
            lastBadge.textContent = 'LAST: Initial Baseline (Day 0)';
        } else {
            const title = formatActionTitleShort(latest.action_type);
            lastBadge.textContent = `LAST: ${title} (Day ${latest.day})`;
        }
    }

    // Calculate current max drift
    let maxDrift = 0;
    if (portfolio && portfolio.weights) {
        portfolio.weights.forEach((w, i) => {
            const d = Math.abs(w - BASE_WEIGHTS[i]);
            if (d > maxDrift) maxDrift = d;
        });
    }
    const maxDriftPct = (maxDrift * 100).toFixed(1);

    const level = guardrail ? guardrail.level : (latest ? latest.guardrail_level : 'MONITOR');
    const regime = lastKnownState.regime || 'NORMAL';

    if (!latest) {
        // Day 0 / Baseline State
        if (typeEl) typeEl.textContent = 'PORTFOLIO INITIALIZED';
        if (summaryEl) summaryEl.textContent = 'Portfolio initialized with baseline balanced allocation. Optimization engine actively monitoring drift and regime transitions.';
        if (whyEl) whyEl.textContent = 'Initial capital deployment across multi-asset spectrum.';
        if (actionEl) actionEl.textContent = 'Baseline allocation set to target weights.';
        if (resultEl) resultEl.textContent = 'Balanced risk exposure established.';

        if (sigMetric) sigMetric.textContent = 'Drift < 5.0%';
        if (sigText) sigText.textContent = 'Portfolio initialized with baseline balanced weights. Real-time drift tracking active.';
        if (anaStatus) anaStatus.textContent = 'MONITOR TIER';
        if (anaText) anaText.textContent = 'Risk guardrails evaluated. Portfolio metrics remain within actionable limits.';
        if (decChip) decChip.textContent = 'INITIALIZE';
        if (decText) decText.textContent = 'BASELINE CAPITAL ALLOCATION';
        if (actTarget) actTarget.textContent = 'Multi-Asset';
        if (actText) actText.textContent = 'Target baseline weights established across 6 institutional asset classes.';
        if (valTag) {
            valTag.textContent = 'GUARDRAILS PASSED';
            valTag.className = 'flow-sub valid-check';
        }
        if (valText) valText.textContent = 'Initial allocation passed configured Rockafellar-Uryasev guardrail checks.';

        if (whyList) {
            whyList.innerHTML = `
                <li>Baseline multi-asset allocation deployed to seed portfolio ($100.00M).</li>
                <li>Current market regime (NORMAL) allows unconstrained optimization.</li>
                <li>4-tier guardrail safety boundaries evaluated across all metrics.</li>
                <li>Mean-CVaR optimizer generated compliant risk-adjusted weights.</li>
            `;
        }
        return;
    }

    // Dynamic Binding based on latest decision
    if (typeEl) {
        if (latest.action_type === 'REBALANCE') {
            typeEl.textContent = 'AUTOMATIC REBALANCE';
        } else if (latest.action_type === 'GUARDRAIL_WARN') {
            typeEl.textContent = 'RISK THRESHOLD WARNING';
        } else if (latest.action_type === 'GUARDRAIL_ACT') {
            typeEl.textContent = 'DEFENSIVE ALLOCATION ACT';
        } else if (latest.action_type === 'CIRCUIT_BREAK' || latest.action_type === 'GUARDRAIL_CIRCUIT_BREAK') {
            typeEl.textContent = 'CIRCUIT BREAKER LOCK';
        } else {
            typeEl.textContent = 'SYSTEM OPTIMIZATION';
        }
    }

    if (summaryEl) {
        summaryEl.textContent = formatExecutiveExplanation(latest.explanation, latest.action_type, latest.guardrail_level);
    }

    if (whyEl) {
        if (latest.guardrail_level === 'CIRCUIT_BREAK' || latest.action_type === 'CIRCUIT_BREAK') {
            whyEl.textContent = 'Cumulative drawdown touched emergency limit. Capital floor triggered.';
        } else if (latest.guardrail_level === 'ACT' || latest.action_type === 'GUARDRAIL_ACT') {
            whyEl.textContent = 'CVaR (95%) tail risk breached safety threshold during market volatility.';
        } else if (latest.action_type === 'REBALANCE') {
            whyEl.textContent = `Asset price drift crossed configured tolerance threshold (${maxDriftPct}%).`;
        } else {
            whyEl.textContent = 'Market volatility shifted asset balance away from target Sharpe ratio.';
        }
    }

    // Calculate weight shift deltas
    let actionParts = [];
    if (latest.weights_before && latest.weights_after) {
        let deltas = [];
        latest.weights_after.forEach((w, i) => {
            const diff = (w - latest.weights_before[i]) * 100;
            deltas.push({ name: ASSET_NAMES[i], delta: diff });
        });
        deltas.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

        const up = deltas.find(d => d.delta >= 0.2);
        const down = deltas.find(d => d.delta <= -0.2);
        if (up) actionParts.push(`↑ ${up.name} +${up.delta.toFixed(1)}%`);
        if (down) actionParts.push(`↓ ${down.name} ${down.delta.toFixed(1)}%`);
    }

    if (actionEl) {
        if (actionParts.length > 0) {
            actionEl.textContent = actionParts.join(', ');
        } else if (latest.action_type === 'CIRCUIT_BREAK') {
            actionEl.textContent = 'Enforced 60% Govt Bonds & 40% Cash defensive floor.';
        } else if (latest.action_type === 'GUARDRAIL_ACT') {
            actionEl.textContent = 'Forced equity exposure reduction (-30%) into sovereign debt.';
        } else {
            actionEl.textContent = 'Optimized capital allocation to maximize risk-adjusted return.';
        }
    }

    if (resultEl) {
        if (latest.guardrail_level === 'CIRCUIT_BREAK') {
            resultEl.textContent = 'Portfolio locked against further drawdown; liquidity guaranteed.';
        } else if (latest.guardrail_level === 'ACT') {
            resultEl.textContent = 'Tail risk reduced; downside vulnerability mitigated.';
        } else {
            resultEl.textContent = 'Expected risk reduced; target risk-adjusted return maintained.';
        }
    }

    // Dynamic Binding based on latest decision
    // Stage 1: SIGNAL
    if (sigMetric) {
        if (latest.action_type === 'REBALANCE') {
            sigMetric.textContent = `Drift ${maxDriftPct}% (Tolerance: 5.0%)`;
        } else if (latest.guardrail_level === 'CIRCUIT_BREAK' || latest.action_type === 'CIRCUIT_BREAK') {
            sigMetric.textContent = 'Drawdown > 12.0%';
        } else if (latest.guardrail_level === 'ACT' || latest.action_type === 'GUARDRAIL_ACT') {
            sigMetric.textContent = 'CVaR > 2.80%';
        } else if (latest.guardrail_level === 'WARN' || latest.action_type === 'GUARDRAIL_WARN') {
            sigMetric.textContent = 'Buffer Alert';
        } else {
            sigMetric.textContent = `Drift ${maxDriftPct}%`;
        }
    }

    if (sigText) {
        if (latest.action_type === 'REBALANCE') {
            sigText.textContent = 'Asset price drift exceeded configured 5.0% tolerance threshold.';
        } else if (latest.guardrail_level === 'CIRCUIT_BREAK' || latest.action_type === 'CIRCUIT_BREAK') {
            sigText.textContent = 'Cumulative portfolio drawdown breached emergency -12.0% risk ceiling.';
        } else if (latest.guardrail_level === 'ACT' || latest.action_type === 'GUARDRAIL_ACT') {
            sigText.textContent = 'Tail risk (95% CVaR) breached 2.80% limit during market turbulence.';
        } else if (latest.guardrail_level === 'WARN' || latest.action_type === 'GUARDRAIL_WARN') {
            sigText.textContent = 'Market volatility spike approaching upper guardrail risk limits.';
        } else {
            sigText.textContent = 'Optimization engine detected actionable variance across portfolio holdings.';
        }
    }

    // Stage 2: RISK ANALYSIS
    if (anaStatus) {
        anaStatus.textContent = `${level === 'CIRCUIT_BREAK' ? 'CIRCUIT BREAK' : level} TIER`;
    }
    if (anaText) {
        if (level === 'CIRCUIT_BREAK') {
            anaText.textContent = 'Emergency floor protocol activated. Capital defense overrides standard optimization.';
        } else if (level === 'ACT') {
            anaText.textContent = 'Convex risk solver triggered forced de-risking to protect capital against tail risk.';
        } else if (level === 'WARN') {
            anaText.textContent = 'Risk guardrails evaluated. Volatility approaching limit. Solver sensitivity heightened.';
        } else {
            anaText.textContent = 'Risk guardrails evaluated. Portfolio metrics remain within actionable limits.';
        }
    }

    // Stage 3: DECISION
    if (decChip) {
        decChip.textContent = formatActionTitleShort(latest.action_type);
    }
    if (decText) {
        if (latest.action_type === 'REBALANCE') {
            decText.textContent = 'AUTOMATIC REBALANCE';
        } else if (latest.guardrail_level === 'CIRCUIT_BREAK' || latest.action_type === 'CIRCUIT_BREAK') {
            decText.textContent = 'CIRCUIT BREAKER LOCK';
        } else if (latest.guardrail_level === 'ACT' || latest.action_type === 'GUARDRAIL_ACT') {
            decText.textContent = 'DEFENSIVE DE-RISKING ACT';
        } else if (latest.guardrail_level === 'WARN' || latest.action_type === 'GUARDRAIL_WARN') {
            decText.textContent = 'PREVENTATIVE SENSITIVITY SHIFT';
        } else {
            decText.textContent = 'PORTFOLIO REBALANCING';
        }
    }

    // Stage 4: ACTION (Calculated from real weights before and after)
    let actionSummary = '';
    if (latest.weights_before && latest.weights_after) {
        let deltas = [];
        latest.weights_after.forEach((w, i) => {
            const diff = (w - latest.weights_before[i]) * 100;
            deltas.push({ name: ASSET_NAMES[i], delta: diff });
        });
        deltas.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

        const up = deltas.find(d => d.delta >= 0.2);
        const down = deltas.find(d => d.delta <= -0.2);
        const parts = [];
        if (up) parts.push(`↑ ${up.name} +${up.delta.toFixed(1)}%`);
        if (down) parts.push(`↓ ${down.name} ${down.delta.toFixed(1)}%`);
        actionSummary = parts.length > 0 ? parts.join('   ') : 'Realigned asset weights to target bounds.';
    } else if (latest.action_type === 'CIRCUIT_BREAK') {
        actionSummary = 'Enforced 60% Govt Bonds & 40% Cash defensive floor.';
    } else if (latest.action_type === 'GUARDRAIL_ACT') {
        actionSummary = 'Forced equity exposure reduction (-30%) into sovereign debt.';
    } else {
        actionSummary = 'Optimized asset weights to restore target Sharpe ratio.';
    }

    if (actTarget) actTarget.textContent = latest.action_type === 'REBALANCE' ? 'Asset Reallocation' : 'Risk Re-weight';
    if (actText) actText.textContent = actionSummary;

    // Stage 5: VALIDATION
    if (valTag) {
        if (level === 'CIRCUIT_BREAK') {
            valTag.textContent = 'FLOOR ENFORCED';
            valTag.className = 'flow-sub valid-check';
        } else {
            valTag.textContent = 'GUARDRAILS PASSED';
            valTag.className = 'flow-sub valid-check';
        }
    }
    if (valText) {
        if (level === 'CIRCUIT_BREAK') {
            valText.textContent = 'Defensive asset floor verified; downside liquidity secured against further drawdowns.';
        } else if (level === 'ACT') {
            valText.textContent = 'De-risked allocation verified against Rockafellar-Uryasev convex guardrails.';
        } else {
            valText.textContent = 'Updated allocation passed configured Rockafellar-Uryasev guardrail checks.';
        }
    }

    // "Why ARGPE Acted" Accordion Points (Driven strictly by backend data)
    if (whyList) {
        const trigger = (latest.trigger_metrics) ? latest.trigger_metrics : {};
        const cvar = trigger.cvar_95 !== undefined ? trigger.cvar_95 : 0;
        const dd = trigger.current_drawdown !== undefined ? trigger.current_drawdown : 0;

        let pt1 = `Asset price drift crossed configured tolerance threshold (max drift: ${maxDriftPct}%).`;
        if (latest.action_type === 'CIRCUIT_BREAK' || level === 'CIRCUIT_BREAK') {
            pt1 = `Drawdown reached emergency limit (${dd.toFixed(1)}% vs 12.0% ceiling).`;
        } else if (latest.action_type === 'GUARDRAIL_ACT' || level === 'ACT') {
            pt1 = `CVaR (95%) tail risk breached safety threshold (${cvar.toFixed(2)}% vs 2.80% limit).`;
        }

        const pt2 = `Current market regime (${regime}) evaluated by automated surveillance loop.`;
        const pt3 = `All 4 guardrail tiers evaluated (CVaR: ${cvar.toFixed(2)}%, Drawdown: ${dd.toFixed(2)}%).`;
        const pt4 = level === 'CIRCUIT_BREAK' 
            ? 'Defensive floor locked capital into safe assets to guarantee solvency.'
            : 'Mean-CVaR convex optimizer generated a verified compliant allocation.';

        whyList.innerHTML = `
            <li>${escapeHtml(pt1)}</li>
            <li>${escapeHtml(pt2)}</li>
            <li>${escapeHtml(pt3)}</li>
            <li>${escapeHtml(pt4)}</li>
        `;
    }
}

// Backward-compatible alias
const updateSystemDecision = updateDecisionEngine;

function toggleWhyDecision() {
    const drawer = $('why-drawer');
    const icon = $('why-toggle-icon');
    if (!drawer) return;
    const isHidden = drawer.style.display === 'none' || !drawer.style.display;
    drawer.style.display = isHidden ? 'block' : 'none';
    if (icon) icon.textContent = isHidden ? '▴' : '▾';
}

function toggleTechDetails() {
    const drawer = $('tech-details-drawer');
    const icon = $('tech-toggle-icon');
    if (!drawer) return;
    const isHidden = drawer.style.display === 'none' || !drawer.style.display;
    drawer.style.display = isHidden ? 'flex' : 'none';
    if (icon) icon.textContent = isHidden ? '▴' : '▾';
}

function openDecisionReceipt() {
    const modal = $('decision-receipt-modal');
    if (!modal) return;

    const d = activeDecisionForReceipt;
    const p = lastKnownState.portfolio;
    const regime = lastKnownState.regime || 'NORMAL';
    const day = d ? d.day : (lastKnownState.day || 0);

    // Event
    const eventEl = $('rcpt-event');
    if (eventEl) {
        if (!d) eventEl.textContent = 'Portfolio Initialization';
        else if (d.action_type === 'REBALANCE') eventEl.textContent = 'Automatic Rebalance';
        else if (d.action_type === 'GUARDRAIL_WARN') eventEl.textContent = 'Guardrail Buffer Warning';
        else if (d.action_type === 'GUARDRAIL_ACT') eventEl.textContent = 'Defensive Allocation Act';
        else if (d.action_type === 'CIRCUIT_BREAK' || d.action_type === 'GUARDRAIL_CIRCUIT_BREAK') eventEl.textContent = 'Emergency Circuit Break';
        else eventEl.textContent = d.action_type;
    }

    // Trigger
    const trigEl = $('rcpt-trigger');
    if (trigEl) {
        if (!d) trigEl.textContent = 'Initial Capital Allocation Deployment';
        else if (d.action_type === 'REBALANCE') trigEl.textContent = 'Portfolio Drift Exceeded Configured Tolerance';
        else if (d.action_type === 'GUARDRAIL_WARN') trigEl.textContent = 'Volatility Buffer Threshold Approached';
        else if (d.action_type === 'GUARDRAIL_ACT') trigEl.textContent = 'CVaR (95%) Tail Risk Breached Safety Limit';
        else if (d.action_type === 'CIRCUIT_BREAK' || d.action_type === 'GUARDRAIL_CIRCUIT_BREAK') trigEl.textContent = 'Cumulative Drawdown Reached Emergency Ceiling';
        else trigEl.textContent = 'Market Drift Surveillance';
    }

    // Action
    const actEl = $('rcpt-action');
    if (actEl) {
        if (!d) actEl.textContent = 'Target Baseline Weights Deployed';
        else if (d.action_type === 'REBALANCE') actEl.textContent = 'Allocation Optimization Across 6 Assets';
        else if (d.action_type === 'CIRCUIT_BREAK' || d.action_type === 'GUARDRAIL_CIRCUIT_BREAK') actEl.textContent = 'Locked 60% Govt Bonds & 40% Cash Floor';
        else if (d.action_type === 'GUARDRAIL_ACT') actEl.textContent = 'De-Risked 30% Equity into Sovereign Debt';
        else actEl.textContent = 'Heightened Rebalancing Sensitivity';
    }

    // Validation
    const valEl = $('rcpt-validation');
    if (valEl) {
        valEl.textContent = (d && (d.action_type === 'CIRCUIT_BREAK' || d.guardrail_level === 'CIRCUIT_BREAK'))
            ? 'Emergency Floor Enforced'
            : 'Guardrail Checks Passed (Rockafellar-Uryasev CVaR Convex LP)';
    }

    // Day
    const dayEl = $('rcpt-day');
    if (dayEl) dayEl.textContent = `Trading Day ${day}`;

    // Regime
    const regEl = $('rcpt-regime');
    if (regEl) regEl.textContent = regime;

    // NAV
    const navEl = $('rcpt-nav');
    if (navEl) navEl.textContent = p ? formatCurrency(p.nav) : '$100.00M';

    // Guardrail tier
    const guardEl = $('rcpt-guardrail');
    if (guardEl) {
        const level = d ? (d.guardrail_level || 'MONITOR') : 'MONITOR';
        guardEl.textContent = level;
    }

    // Execution Ref Hash
    const hashEl = $('rcpt-hash');
    if (hashEl) {
        const type = d ? d.action_type : 'INIT';
        hashEl.textContent = `EXECUTION REF: FORTRESS-REC-DAY${day}-${type}`;
    }

    // Weights Deltas Grid
    const grid = $('rcpt-weights-grid');
    if (grid) {
        const before = (d && d.weights_before) ? d.weights_before : BASE_WEIGHTS;
        const after = (d && d.weights_after) ? d.weights_after : (p ? p.weights : BASE_WEIGHTS);

        grid.innerHTML = ASSET_NAMES.map((name, i) => {
            const b = (before[i] !== undefined ? before[i] : BASE_WEIGHTS[i]) * 100;
            const a = (after[i] !== undefined ? after[i] : BASE_WEIGHTS[i]) * 100;
            const diff = a - b;
            let tagClass = 'flat';
            let tagText = '0.0%';
            if (diff > 0.2) {
                tagClass = 'up';
                tagText = `↑ +${diff.toFixed(1)}%`;
            } else if (diff < -0.2) {
                tagClass = 'down';
                tagText = `↓ ${diff.toFixed(1)}%`;
            }
            return `
                <div class="rcpt-delta-item">
                    <span class="rcpt-asset-name">${name}</span>
                    <span class="rcpt-delta-tag ${tagClass}">${tagText}</span>
                </div>
            `;
        }).join('');
    }

    modal.style.display = 'flex';
}

function closeDecisionReceipt() {
    const modal = $('decision-receipt-modal');
    if (modal) modal.style.display = 'none';
}

// ─── 12. Recent System Actions (High-Density Feed + Clean Copy) ────────────

function updateRecentActions(decisions) {
    const list = $('actions-compact-list');
    if (!list) return;

    const valid = decisions ? decisions.filter(d => d.day > 0 || d.action_type === 'INIT') : [];

    if (valid.length === 0) {
        list.innerHTML = `<div class="empty-state-clean">No decisions logged yet. Start simulation to observe system actions.</div>`;
        return;
    }

    // Max 3 items
    const top3 = valid.slice(0, 3);

    list.innerHTML = top3.map(d => {
        const icon = getDecisionIcon(d.action_type);
        const title = formatActionTitleShort(d.action_type);
        const cleanText = formatExecutiveExplanation(d.explanation, d.action_type, d.guardrail_level);
        return `
            <div class="action-row">
                <span class="action-day-tag">DAY ${d.day}</span>
                <span class="action-type-pill ${d.action_type}">${icon} ${title}</span>
                <span class="action-text" title="${escapeHtml(cleanText)}">${escapeHtml(cleanText)}</span>
            </div>
        `;
    }).join('');

    // Update full audit tray
    const trayContent = $('full-audit-content');
    if (trayContent) {
        trayContent.innerHTML = valid.map(d => {
            const icon = getDecisionIcon(d.action_type);
            const title = formatActionTitleShort(d.action_type);
            const cleanText = formatExecutiveExplanation(d.explanation, d.action_type, d.guardrail_level);
            return `
                <div class="action-row">
                    <span class="action-day-tag">DAY ${d.day}</span>
                    <span class="action-type-pill ${d.action_type}">${icon} ${title}</span>
                    <span class="action-text">${escapeHtml(cleanText)}</span>
                </div>
            `;
        }).join('');
    }
}

function getDecisionIcon(type) {
    switch (type) {
        case 'INIT': return '✓';
        case 'REBALANCE': return '🔄';
        case 'GUARDRAIL_WARN': return '⚠';
        case 'GUARDRAIL_ACT': return '⚡';
        case 'GUARDRAIL_CIRCUIT_BREAK':
        case 'CIRCUIT_BREAK': return '🛑';
        case 'RECOVERY': return '🚀';
        default: return '●';
    }
}

function formatActionTitleShort(type) {
    switch (type) {
        case 'INIT': return 'INITIALIZE';
        case 'REBALANCE': return 'REBALANCE';
        case 'GUARDRAIL_WARN': return 'GUARD-WARN';
        case 'GUARDRAIL_ACT': return 'GUARD-ACT';
        case 'GUARDRAIL_CIRCUIT_BREAK':
        case 'CIRCUIT_BREAK': return 'CIRCUIT BREAK';
        case 'RECOVERY': return 'RECOVERY';
        default: return type;
    }
}

function formatExecutiveExplanation(raw, type, level) {
    if (!raw) return 'System status nominal.';

    // If already clean, return it
    if (!raw.includes('Optimizer rebalanced') && !raw.includes('Breach detected --') && !raw.includes('Approaching limits --')) {
        return raw;
    }

    if (type === 'REBALANCE' || raw.includes('Optimizer rebalanced')) {
        // Extract increased / reduced if available
        const incMatch = raw.match(/Increased:\s*([^.]+)/);
        const redMatch = raw.match(/Reduced:\s*([^.]+)/);
        if (incMatch && redMatch) {
            return `Rebalanced asset allocation to maintain target Sharpe ratio: Increased ${incMatch[1].trim()}, Reduced ${redMatch[1].trim()}.`;
        }
        return 'Rebalanced portfolio allocation to restore optimal risk-adjusted returns and offset drift.';
    }

    if (type === 'CIRCUIT_BREAK' || level === 'CIRCUIT_BREAK' || raw.includes('CIRCUIT_BREAK')) {
        return 'Maximum drawdown ceiling touched. Locked in defensive floor (60% Govt Bonds, 40% Cash) to preserve principal.';
    }

    if (type === 'GUARDRAIL_ACT' || level === 'ACT' || raw.includes('GUARDRAIL ACT')) {
        return 'Tail risk (CVaR) exceeded safety threshold. Forced de-risking: reduced equity exposure by 30% into sovereign debt and cash.';
    }

    if (type === 'GUARDRAIL_WARN' || level === 'WARN' || raw.includes('GUARDRAIL WARN')) {
        return 'Portfolio volatility or concentration approaching guardrail limits. Optimization sensitivity increased.';
    }

    if (type === 'INIT' || raw.includes('initialized with $100M')) {
        return 'Portfolio initialized with $100M baseline multi-asset allocation. Real-time risk governance active.';
    }

    return raw;
}

function toggleFullAuditLog() {
    const tray = $('full-audit-tray');
    if (!tray) return;

    if (tray.style.display === 'none' || !tray.style.display) {
        tray.style.display = 'flex';
    } else {
        tray.style.display = 'none';
    }
}

function scrollToActions(e) {
    if (e) e.preventDefault();
    const section = $('recent-actions');
    if (section) {
        section.scrollIntoView({ behavior: 'smooth' });
    }
}

function switchDeckTab(tabName) {
    const tabScenario = $('tab-scenario');
    const tabAudit = $('tab-audit');
    const btnScenario = $('tab-btn-scenario');
    const btnAudit = $('tab-btn-audit');

    if (tabName === 'scenario') {
        if (tabScenario) tabScenario.classList.add('active');
        if (tabAudit) tabAudit.classList.remove('active');
        if (btnScenario) {
            btnScenario.classList.add('active');
            btnScenario.setAttribute('aria-selected', 'true');
        }
        if (btnAudit) {
            btnAudit.classList.remove('active');
            btnAudit.setAttribute('aria-selected', 'false');
        }
    } else if (tabName === 'audit') {
        if (tabAudit) tabAudit.classList.add('active');
        if (tabScenario) tabScenario.classList.remove('active');
        if (btnAudit) {
            btnAudit.classList.add('active');
            btnAudit.setAttribute('aria-selected', 'true');
        }
        if (btnScenario) {
            btnScenario.classList.remove('active');
            btnScenario.setAttribute('aria-selected', 'false');
        }
    }
}
window.switchDeckTab = switchDeckTab;

// ─── 13. What-If Scenario Lab ──────────────────────────────────────────────

function loadPreset(preset) {
    const values = PRESET_SHOCKS[preset];
    if (!values) return;

    // Update active preset button state
    const buttons = document.querySelectorAll('.btn-preset, .preset-pill');
    buttons.forEach(btn => {
        if (btn.textContent.toLowerCase().includes(preset.toLowerCase()) ||
            (preset === 'crash' && btn.textContent.includes('CRASH')) ||
            (preset === 'rates' && btn.textContent.includes('RATE')) ||
            (preset === 'recovery' && btn.textContent.includes('RECOVERY')) ||
            (preset === 'normal' && btn.textContent.includes('NORMAL'))) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    const setSlider = (id, val) => {
        const slider = $(id);
        if (slider) {
            slider.value = val;
            updateSliderDisplay(slider);
        }
    };

    setSlider('shock-us-equity', values['US Equity']);
    setSlider('shock-intl-equity', values['Intl Equity']);
    setSlider('shock-govt-bonds', values['Govt Bonds']);
    setSlider('shock-corp-bonds', values['Corp Bonds']);
    setSlider('shock-commodities', values['Commodities']);
    setSlider('shock-cash', values['Cash']);

    // Run the stress test automatically
    runScenario();
}

function updateSliderDisplay(slider) {
    if (!slider) return;
    const label = $(`val-${slider.id}`);
    if (label) {
        const val = parseInt(slider.value, 10);
        label.textContent = `${val >= 0 ? '+' : ''}${val}%`;
        if (val < 0) {
            label.className = 'shock-val tabular-nums negative';
        } else if (val > 0) {
            label.className = 'shock-val tabular-nums positive';
        } else {
            label.className = 'shock-val tabular-nums';
        }
    }
}

function setScenarioSkeleton(isLoading) {
    const targets = [
        $('res-nav'),
        $('res-return'),
        $('res-dd'),
        $('res-level'),
        $('res-explanation'),
    ];
    targets.forEach(el => {
        if (el) {
            if (isLoading) el.classList.add('skeleton-shimmer');
            else el.classList.remove('skeleton-shimmer');
        }
    });
}

function setInitialSkeleton(isLoading) {
    const targets = [
        $('nav-value'),
        $('kpi-sharpe'),
        $('val-cvar'),
        $('val-dd'),
        $('intel-why'),
        $('intel-action'),
        $('intel-result'),
    ];
    targets.forEach(el => {
        if (el) {
            if (isLoading) el.classList.add('skeleton-shimmer');
            else el.classList.remove('skeleton-shimmer');
        }
    });
}

async function runScenario() {
    const getVal = (id) => parseFloat($(id)?.value) || 0;

    const shocks = {
        'US Equity': getVal('shock-us-equity'),
        'Intl Equity': getVal('shock-intl-equity'),
        'Govt Bonds': getVal('shock-govt-bonds'),
        'Corp Bonds': getVal('shock-corp-bonds'),
        'Commodities': getVal('shock-commodities'),
        'Cash': getVal('shock-cash'),
    };

    const runBtn = $('btn-run-scenario');
    if (runBtn) {
        runBtn.textContent = 'Evaluating Scenario...';
        runBtn.disabled = true;
    }

    setScenarioSkeleton(true);

    try {
        const [resp] = await Promise.all([
            fetch('/api/scenario', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ shocks }),
            }),
            new Promise(resolve => setTimeout(resolve, 220))
        ]);
        const result = await resp.json();
        setScenarioSkeleton(false);
        renderScenarioResults(result);
    } catch (err) {
        setScenarioSkeleton(false);
        console.error('[Scenario] Stress evaluation error:', err);
    } finally {
        if (runBtn) {
            runBtn.textContent = 'Run Quantitative Stress Test';
            runBtn.disabled = false;
        }
    }
}

function renderScenarioResults(result) {
    const navEl = $('res-nav');
    const retEl = $('res-return');
    const ddEl = $('res-dd');
    const levelEl = $('res-level');
    const expEl = $('res-explanation');
    const respBox = $('system-response-box');

    if (navEl) navEl.textContent = formatCurrency(result.projected_nav);

    if (retEl) {
        const isPos = result.projected_return_pct >= 0;
        retEl.textContent = `${isPos ? '+' : ''}${result.projected_return_pct.toFixed(2)}%`;
        retEl.className = `tile-val tabular-nums ${isPos ? 'positive' : 'negative'}`;
    }

    const dd = result.projected_metrics ? result.projected_metrics.current_drawdown : 0;
    if (ddEl) {
        ddEl.textContent = `${dd.toFixed(2)}%`;
        ddEl.className = 'tile-val tabular-nums negative';
    }

    const guardrail = result.guardrail_response || { level: 'MONITOR', explanation: '' };

    if (levelEl) {
        levelEl.textContent = guardrail.level;
        if (guardrail.level === 'CIRCUIT_BREAK') {
            levelEl.className = 'tile-val tag-warn';
            levelEl.style.color = '#EF4444';
        } else if (guardrail.level === 'ACT') {
            levelEl.className = 'tile-val tag-warn';
            levelEl.style.color = '#F97316';
        } else if (guardrail.level === 'WARN') {
            levelEl.className = 'tile-val tag-warn';
            levelEl.style.color = '#F59E0B';
        } else {
            levelEl.className = 'tile-val tag-warn';
            levelEl.style.color = '#10B981';
        }
    }

    if (expEl) {
        if (guardrail.level === 'CIRCUIT_BREAK') {
            expEl.textContent = 'Circuit breaker will lock 60% Govt Bonds and 40% Cash defensive floor to protect principal.';
        } else if (guardrail.level === 'ACT') {
            expEl.textContent = 'Dynamic de-risking will reduce equity allocation by 30% into sovereign debt to preserve capital.';
        } else if (guardrail.level === 'WARN') {
            expEl.textContent = 'Rebalancing sensitivity will increase to suppress portfolio volatility.';
        } else {
            expEl.textContent = 'All projected metrics operating within configured limits. Standard drift monitoring continues.';
        }
    }

    if (respBox) {
        if (guardrail.level === 'CIRCUIT_BREAK') {
            respBox.style.borderLeftColor = '#EF4444';
        } else if (guardrail.level === 'ACT') {
            respBox.style.borderLeftColor = '#F97316';
        } else if (guardrail.level === 'WARN') {
            respBox.style.borderLeftColor = '#F59E0B';
        } else {
            respBox.style.borderLeftColor = '#10B981';
        }
    }
}

// ─── 14. Simulation Controls & Spacebar Shortcut ───────────────────────────

function bindSimulationControls() {
    const btnStart = $('start');
    const btnStop = $('stop');
    const btnReset = $('reset');
    const speedRange = $('speed');
    const scenarioSelect = $('scenario');

    if (btnStart) btnStart.addEventListener('click', startSimulation);
    if (btnStop) btnStop.addEventListener('click', stopSimulation);
    if (btnReset) btnReset.addEventListener('click', resetSimulation);

    if (speedRange) {
        speedRange.addEventListener('input', (e) => updateSpeed(e.target.value));
    }

    // Spacebar listener for emergency pause
    window.addEventListener('keydown', (e) => {
        const activeTag = document.activeElement ? document.activeElement.tagName : '';
        if (['INPUT', 'SELECT', 'TEXTAREA'].includes(activeTag)) return;

        if (e.code === 'Space' || e.key === ' ') {
            e.preventDefault();
            if (isRunning && btnStop && !btnStop.disabled) {
                btnStop.click();
                flashEmergencyPause();
            } else if (!isRunning && btnStart && !btnStart.disabled) {
                btnStart.click();
            }
        }
    });
}

async function startSimulation() {
    try {
        const resp = await fetch('/api/simulation/start', { method: 'POST' });
        const data = await resp.json();
        if (data.status === 'started' || data.status === 'already_running') {
            isRunning = true;
            updateControlButtons();
        }
    } catch (err) {
        console.error('[Simulation] Failed to start:', err);
    }
}

async function stopSimulation() {
    try {
        await fetch('/api/simulation/stop', { method: 'POST' });
        isRunning = false;
        updateControlButtons();
    } catch (err) {
        console.error('[Simulation] Failed to stop:', err);
    }
}

async function resetSimulation() {
    try {
        setInitialSkeleton(true);
        const scenarioSelect = $('scenario');
        const speedRange = $('speed');
        const scenario = scenarioSelect ? scenarioSelect.value : 'gradual_crash';
        const speed = speedRange ? parseFloat(speedRange.value) : 1.5;

        await fetch('/api/simulation/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                scenario: scenario,
                seed: 42,
                tick_speed: speed,
                initial_nav: 100000000,
            }),
        });
        setTimeout(() => setInitialSkeleton(false), 260);
    } catch (err) {
        setInitialSkeleton(false);
        console.error('[Simulation] Failed to reset:', err);
    }
}

function updateControlButtons() {
    const btnStart = $('start');
    const btnStop = $('stop');

    if (btnStart) btnStart.disabled = isRunning;
    if (btnStop) btnStop.disabled = !isRunning;
}

function updateSpeed(val) {
    const badge = $('speed-value');
    if (badge) badge.textContent = `${val}s`;

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'set_speed', speed: parseFloat(val) }));
    }
    fetch(`/api/simulation/speed?speed=${val}`, { method: 'POST' }).catch(() => {});
}

function flashEmergencyPause() {
    const alertEl = $('alert-text');
    if (alertEl) {
        const prev = alertEl.textContent;
        alertEl.textContent = 'SIMULATION PAUSED BY USER [SPACEBAR]';
        setTimeout(() => {
            if (alertEl.textContent.includes('SIMULATION PAUSED')) {
                alertEl.textContent = prev;
            }
        }, 3000);
    }
}

// ─── 15. Initial State Fetching ────────────────────────────────────────────

async function loadInitialState() {
    try {
        setInitialSkeleton(true);
        const [portfolioResp, decisionsResp] = await Promise.all([
            fetch('/api/portfolio'),
            fetch('/api/decisions'),
        ]);

        const portfolio = await portfolioResp.json();
        const decisions = await decisionsResp.json();

        lastKnownState.portfolio = portfolio;
        updatePortfolio(portfolio, null);
        updateAllocationDisplay(portfolio.weights, portfolio.nav);

        if (decisions && decisions.length > 0) {
            allDecisions = decisions;
            updateRecentActions(decisions);
            updateSystemDecision(decisions, null, portfolio, portfolio.day);
        }
        setInitialSkeleton(false);
    } catch (err) {
        setInitialSkeleton(false);
        console.log('[Init] Telemetry bootstrap waiting for WebSocket stream.');
    }
}

// ─── 16. Formatting & Color Helpers ────────────────────────────────────────

function formatCurrency(value) {
    if (value === undefined || value === null) return '$0';
    const abs = Math.abs(value);
    const sign = value < 0 ? '-' : '';

    if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
    return `${sign}$${abs.toFixed(0)}`;
}

function formatCompactCurrency(value) {
    if (value === undefined || value === null) return '$0';
    const abs = Math.abs(value);
    const sign = value < 0 ? '-' : '';

    if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
    if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
    return `${sign}$${abs.toFixed(0)}`;
}

function getLevelColor(level) {
    switch (level) {
        case 'MONITOR': return '#10B981';
        case 'WARN': return '#F59E0B';
        case 'ACT': return '#F97316';
        case 'CIRCUIT_BREAK': return '#DC2626';
        default: return '#3B82F6';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Expose handlers globally for HTML attributes
window.loadPreset = loadPreset;
window.runScenario = runScenario;
window.updateSliderDisplay = updateSliderDisplay;
window.toggleFullAuditLog = toggleFullAuditLog;
window.scrollToActions = scrollToActions;
window.startSimulation = startSimulation;
window.stopSimulation = stopSimulation;
window.resetSimulation = resetSimulation;
window.toggleWhyDecision = toggleWhyDecision;
window.toggleTechDetails = toggleTechDetails;
window.openDecisionReceipt = openDecisionReceipt;
window.closeDecisionReceipt = closeDecisionReceipt;
