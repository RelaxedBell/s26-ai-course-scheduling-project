// UVA Course Scheduler Frontend

const API = '';
let currentScheduleId = null;
let chatSessionId = 'session-' + Date.now();

// --- Difficulty slider label ---
const diffSlider = document.getElementById('difficulty');
const diffLabel = document.getElementById('difficulty-label');
const diffLabels = {1: 'Easy', 2: 'Moderate-Easy', 3: 'Moderate', 4: 'Challenging', 5: 'Very Challenging'};

if (diffSlider) {
    diffSlider.addEventListener('input', () => {
        diffLabel.textContent = diffLabels[diffSlider.value];
    });
}

// Rating slider
const ratingSlider = document.getElementById('rating-slider');
const ratingValue = document.getElementById('rating-value');
if (ratingSlider) {
    ratingSlider.addEventListener('input', () => {
        ratingValue.textContent = ratingSlider.value;
    });
}

// --- Tab switching ---
function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById(tab + '-tab').classList.add('active');
    event.target.classList.add('active');
}

// --- Transcript submission ---
async function submitTranscript() {
    const checkboxes = document.querySelectorAll('.course-checkbox:checked');
    const completed = Array.from(checkboxes).map(cb => cb.value);

    const res = await fetch(API + '/api/transcript', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({completed_courses: completed}),
    });
    const data = await res.json();

    const resultDiv = document.getElementById('audit-result');
    resultDiv.innerHTML = `
        <strong>Degree Audit</strong><br>
        Credits completed: ${data.credits_completed}<br>
        Remaining prerequisites: ${data.remaining_prerequisites.length > 0 ? data.remaining_prerequisites.join(', ') : 'None'}<br>
        Remaining required: ${data.remaining_required.length > 0 ? data.remaining_required.join(', ') : 'None'}<br>
        Restricted elective credits needed: ${Math.max(0, data.restricted_elective_credits_needed)}<br>
        Integration elective credits needed: ${Math.max(0, data.integration_elective_credits_needed)}<br>
        ${data.is_complete ? '<strong style="color: green;">Degree requirements complete!</strong>' : ''}
    `;
}

// --- Schedule generation ---
async function generateSchedules() {
    const checkboxes = document.querySelectorAll('.course-checkbox:checked');
    const completed = Array.from(checkboxes).map(cb => cb.value);

    const topicCheckboxes = document.querySelectorAll('.topic-chips input:checked');
    const topics = Array.from(topicCheckboxes).map(cb => cb.value);

    const prefs = {
        difficulty_preference: parseInt(document.getElementById('difficulty').value),
        min_credits: parseInt(document.getElementById('min-credits').value),
        max_credits: parseInt(document.getElementById('max-credits').value),
        preferred_topics: topics,
        prefer_morning: document.getElementById('prefer-morning').checked ? true : null,
        liked_courses: [],
        disliked_courses: [],
        time_blocks_unavailable: [],
        instructor_preferences: {},
    };

    const container = document.getElementById('schedules-container');
    container.innerHTML = '<p>Generating schedules...</p>';

    const res = await fetch(API + '/api/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            completed_courses: completed,
            preferences: prefs,
            max_schedules: 5,
        }),
    });
    const data = await res.json();
    renderSchedules(data.schedules, prefs, completed);
}

// --- Render schedules ---
const COURSE_COLORS = [
    '#4a90d9', '#e57200', '#27ae60', '#8e44ad', '#c0392b',
    '#16a085', '#d35400', '#2980b9', '#f39c12', '#1abc9c',
];

function renderSchedules(schedules, prefs, completed) {
    const container = document.getElementById('schedules-container');
    if (!schedules || schedules.length === 0) {
        container.innerHTML = '<p class="placeholder">No valid schedules found. Try adjusting your preferences.</p>';
        return;
    }

    container.innerHTML = '';
    schedules.forEach((sched, idx) => {
        const card = document.createElement('div');
        card.className = 'schedule-card';
        card.onclick = () => selectSchedule(idx, prefs, completed);

        const dayMap = {'M': 'Mon', 'T': 'Tue', 'W': 'Wed', 'R': 'Thu', 'F': 'Fri'};

        let sectionsHtml = '<div class="section-list">';
        sched.sections.forEach((sec, i) => {
            const color = COURSE_COLORS[i % COURSE_COLORS.length];
            const days = sec.days.map(d => dayMap[d] || d).join('/');
            sectionsHtml += `
                <div class="section-item">
                    <span class="code" style="color:${color}">${sec.course_code}</span>
                    <span class="name">${sec.course_name}</span>
                    <span class="time">${days} ${sec.start_time}-${sec.end_time}</span>
                    <span class="score-pill">${(sec.bayes_score * 100).toFixed(0)}%</span>
                </div>
            `;
        });
        sectionsHtml += '</div>';

        card.innerHTML = `
            <div class="schedule-header">
                <strong>Schedule ${idx + 1}</strong>
                <span>${sched.total_credits} credits</span>
                <span class="score-badge">Score: ${(sched.score * 100).toFixed(0)}%</span>
            </div>
            ${sectionsHtml}
        `;
        container.appendChild(card);
    });
}

// --- Select schedule for explanation/rating ---
async function selectSchedule(idx, prefs, completed) {
    document.querySelectorAll('.schedule-card').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('.schedule-card')[idx].classList.add('selected');
    currentScheduleId = idx;

    // Show explanation
    const explainDiv = document.getElementById('explanation-container');
    const explainText = document.getElementById('explanation-text');
    explainDiv.style.display = 'block';
    explainText.innerHTML = 'Loading explanation...';

    const res = await fetch(API + '/api/explain', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            schedule_id: idx,
            completed_courses: completed || [],
            preferences: prefs || {difficulty_preference: 3, max_credits: 15, min_credits: 12,
                                    preferred_topics: [], liked_courses: [], disliked_courses: [],
                                    time_blocks_unavailable: [], instructor_preferences: {}},
        }),
    });
    const data = await res.json();
    explainText.innerHTML = data.explanation.replace(/\n/g, '<br>');

    // Show rating
    document.getElementById('rating-container').style.display = 'block';
}

// --- Submit rating ---
async function submitRating() {
    if (currentScheduleId === null) return;
    const rating = parseInt(document.getElementById('rating-slider').value);

    await fetch(API + '/api/rate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({schedule_id: currentScheduleId, rating: rating}),
    });

    alert(`Rating of ${rating}/10 submitted! Thank you.`);
}

// --- Chat ---
function addChatMessage(text, isUser) {
    const div = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = 'chat-msg ' + (isUser ? 'user' : 'bot');
    msg.textContent = text;
    div.appendChild(msg);
    div.scrollTop = div.scrollHeight;
}

async function sendChat() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    addChatMessage(message, true);
    input.value = '';

    const res = await fetch(API + '/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: message, session_id: chatSessionId}),
    });
    const data = await res.json();

    addChatMessage(data.reply, false);

    if (data.schedules && data.schedules.length > 0) {
        renderSchedules(data.schedules, data.preferences_parsed, []);
    }
}

// Initialize chat with greeting
window.addEventListener('DOMContentLoaded', () => {
    sendChat_init();
});

async function sendChat_init() {
    const res = await fetch(API + '/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: 'hello', session_id: chatSessionId}),
    });
    const data = await res.json();
    addChatMessage(data.reply, false);
}
