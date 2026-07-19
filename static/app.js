// ── DOM References ─────────────────────────────────────────
const contrastToggle   = document.getElementById('contrastToggle');
const queryInput       = document.getElementById('queryInput');
const matchPhaseSelect = document.getElementById('matchPhase');
const accessSelect     = document.getElementById('accessibility');
const executeBtn       = document.getElementById('executeBtn');
const btnIcon          = document.getElementById('btnIcon');
const btnText          = document.getElementById('btnText');
const btnSpinner       = document.getElementById('btnSpinner');
const charCount        = document.getElementById('charCount');
const footerPhase      = document.getElementById('footerPhase');
const statusDot        = document.getElementById('statusDot');
const statusText       = document.getElementById('statusText');
const defaultState     = document.getElementById('defaultState');
const loadingState     = document.getElementById('loadingState');
const responseState    = document.getElementById('responseState');
const errorState       = document.getElementById('errorState');
const responseText     = document.getElementById('responseText');
const echoText         = document.getElementById('echoText');
const responseTimestamp = document.getElementById('responseTimestamp');
const errorText        = document.getElementById('errorText');
const languageSim      = document.getElementById('languageSim');

// ── Live Telemetry Simulation ──────────────────────────────
const liveCrowdDensity = document.getElementById('liveCrowdDensity');
const liveGate = document.getElementById('liveGate');
const liveWeather = document.getElementById('liveWeather');

const crowdDensities = ['LOW', 'MODERATE', 'HIGH', 'CRITICAL'];
const gateStatuses = ['NORMAL', 'HIGH', 'MAX CAPACITY', 'DIVERTING'];
const weathers = ['CLEAR', 'CLOUDY', 'LIGHT RAIN', 'HEAVY RAIN'];

setInterval(() => {
    const crowd = crowdDensities[Math.floor(Math.random() * crowdDensities.length)];
    const gate = gateStatuses[Math.floor(Math.random() * gateStatuses.length)];
    const weather = weathers[Math.floor(Math.random() * weathers.length)];
    
    if (liveCrowdDensity) liveCrowdDensity.textContent = `Crowd Density: ${crowd}`;
    if (liveGate) liveGate.textContent = `Gate 4: ${gate}`;
    if (liveWeather) liveWeather.textContent = `Weather: ${weather}`;
}, 5000);

// ── UI Toggles ─────────────────────────────────────────────
contrastToggle.addEventListener('click', () => {
    document.body.classList.toggle('high-contrast-mode');
});

// ── Character Counter ──────────────────────────────────────
queryInput.addEventListener('input', () => {
    charCount.textContent = `${queryInput.value.length} / 1000`;
});

// ── Phase Footer Sync ──────────────────────────────────────
matchPhaseSelect.addEventListener('change', () => {
    footerPhase.textContent = `Phase: ${matchPhaseSelect.value}`;
});

// ── Quick Query Helper ─────────────────────────────────────
function setQuery(text) {
    queryInput.value = text;
    charCount.textContent = `${text.length} / 1000`;
    queryInput.focus();
}

// ── UI State Machine ───────────────────────────────────────
function showState(state) {
    defaultState.classList.add('hidden');
    loadingState.classList.add('hidden');
    responseState.classList.add('hidden');
    errorState.classList.add('hidden');

    if (state === 'default')  defaultState.classList.remove('hidden');
    if (state === 'loading')  loadingState.classList.remove('hidden');
    if (state === 'response') responseState.classList.remove('hidden');
    if (state === 'error')    errorState.classList.remove('hidden');
}

function setStatus(type, text) {
    statusText.textContent = text;
    statusDot.className = 'w-2 h-2 rounded-full';
    if (type === 'idle')    statusDot.classList.add('bg-gray-600');
    if (type === 'loading') { statusDot.classList.add('bg-cyber-amber', 'animate-pulse'); }
    if (type === 'success') statusDot.classList.add('bg-arena-500');
    if (type === 'error')   statusDot.classList.add('bg-cyber-red');
}

function setButtonLoading(isLoading) {
    executeBtn.disabled = isLoading;
    if (isLoading) {
        btnIcon.classList.add('hidden');
        btnSpinner.classList.remove('hidden');
        btnText.textContent = 'Processing...';
    } else {
        btnIcon.classList.remove('hidden');
        btnSpinner.classList.add('hidden');
        btnText.textContent = 'Execute Query';
    }
}

// ── Core: Execute Query ────────────────────────────────────
async function executeQuery(event) {
    // Prevent any form submission / page reload
    if (event) { event.preventDefault(); event.stopPropagation(); }

    const query = queryInput.value.trim();

    // Client-side validation
    if (query.length < 2) {
        showState('error');
        errorText.textContent = 'Query must be at least 2 characters long.';
        setStatus('error', 'Validation Failed');
        return;
    }

    // Build payload matching the API schema exactly
    const selectedLanguage = languageSim ? languageSim.value : 'English';
    const payload = {
        query: `${query} (Please respond in ${selectedLanguage})`,
        context: {
            match_phase:          matchPhaseSelect.value,
            sector_id:            "100",
            gates:                { "GATE_4": "NORMAL", "GATE_7": "LOW" },
            facilities:           { "RESTROOM_B": "OPERATIONAL", "FIRST_AID_2": "STAFFED" },
            accessibility_required: accessSelect.value === 'true',
            user_role:            "STAFF"
        }
    };

    // Transition to loading state
    showState('loading');
    setStatus('loading', 'Processing Telemetry');
    setButtonLoading(true);

    try {
        const response = await fetch('/api/v1/operations/stream', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Stadium-Auth': 'wc2026-ops-token'
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            const detail  = errData.detail || `HTTP ${response.status}: ${response.statusText}`;
            throw new Error(detail);
        }

        // Render success state immediately for streaming
        echoText.textContent = query;
        responseTimestamp.textContent = `· ${new Date().toLocaleTimeString()}`;
        responseText.textContent = ''; // Clear text for typing effect

        showState('response');
        setStatus('success', 'Receiving Stream...');

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.substring(6);
                    if (dataStr === '[DONE]') {
                        break;
                    }
                    if (dataStr.startsWith('[ERROR]')) {
                        responseText.textContent += '\n\n' + dataStr;
                        setStatus('error', 'Stream Error');
                        break;
                    }
                    responseText.textContent += dataStr;
                }
            }
        }

        setStatus('success', 'Response Completed');

    } catch (err) {
        // Render error
        errorText.textContent = err.message || 'An unknown network error occurred.';
        showState('error');
        setStatus('error', 'Request Failed');

    } finally {
        setButtonLoading(false);
    }
}

// ── Keyboard shortcut: Ctrl+Enter to execute ───────────────
queryInput.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        executeQuery();
    }
});
