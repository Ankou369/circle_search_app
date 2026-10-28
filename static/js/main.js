// --- 状態管理 ---
let currentAuthMode = 'login'; // 'login' or 'register'
let currentRole = 'student'; // 'student' or 'leader'

function handleAuthSubmit(role) {
    if (role === 'student') {
        if (currentAuthMode === 'register') {
            // 学生の新規登録時は診断画面へ
            switchScreen('diagnostic');
        } else {
            // 学生のログイン時はホームへ
            switchScreen('student-home');
        }
    } else {
        // 幹部の場合は登録もログインも管理ダッシュボードへ
        switchScreen('leader-home');
    }
}

function logout() {
    // 全てのナビを隠す
    document.getElementById('nav-student').classList.add('hidden');
    document.getElementById('nav-leader').classList.add('hidden');
    // 初期状態に戻す
    currentAuthMode = 'login';
    toggleAuthMode(); // リセット用 (1回トグルして戻す)
    toggleAuthMode();
    switchScreen('auth');
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

// 初期ロード時
window.onload = () => {
    switchScreen('auth');
}