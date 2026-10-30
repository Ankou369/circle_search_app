// --- 状態管理 ---
let currentAuthMode = 'login'; // 'login' or 'register'
let currentRole = 'student'; // 'student' or 'leader'

function logout() {
    // サーバー側のログアウト（Flask-Login）を実行する
    window.location.href = '/logout';
}

function updateNavHighlight(role, activeTarget) {
    const tabs = {
        student: ['student-home', 'student-discover', 'student-list', 'student-dm', 'student-profile'],
        leader: ['leader-home', 'leader-dm', 'leader-settings']
    };
    
    const activeColor = role === 'student' ? 'text-brand-600' : 'text-leader-600';
    const inactiveColor = 'text-slate-400 hover:text-slate-700';

    tabs[role].forEach(tab => {
        const btn = document.getElementById(`tab-${tab}`);
        if (!btn) return;
        // reset colors
        btn.className = btn.className.replace(activeColor, '').replace(inactiveColor, '').trim();
        
        if (tab === activeTarget) {
            btn.className += ` ${activeColor}`;
        } else {
            btn.className += ` ${inactiveColor}`;
        }
    });
}

// --- 学生向け：診断完了 ---
function finishDiagnostic() {
    switchScreen('student-home');
}

// 初期ロード時: サーバーから渡された状態（window.CAMPUS）を復元してから初期画面を開く
window.onload = () => {
    const state = window.CAMPUS || {};
    if (state.authRole === 'leader') {
        setAuthRole('leader');
    }
    if (state.authMode === 'register') {
        toggleAuthMode();
    }
    switchScreen(state.initialScreen || 'auth');
}