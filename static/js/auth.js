// --- 認証画面ロジック ---
function setAuthRole(role) {
    currentRole = role;
    const btnS = document.getElementById('auth-tab-student');
    const btnL = document.getElementById('auth-tab-leader');
    const formS = document.getElementById('form-student');
    const formL = document.getElementById('form-leader');

    if (role === 'student') {
        btnS.className = "w-1/2 py-2.5 rounded-lg bg-white text-brand-600 shadow-sm transition font-bold";
        btnL.className = "w-1/2 py-2.5 rounded-lg text-slate-500 hover:text-slate-700 transition font-bold";
        formS.classList.remove('hidden'); formL.classList.add('hidden');
    } else {
        btnL.className = "w-1/2 py-2.5 rounded-lg bg-white text-leader-600 shadow-sm transition font-bold";
        btnS.className = "w-1/2 py-2.5 rounded-lg text-slate-500 hover:text-slate-700 transition font-bold";
        formL.classList.remove('hidden'); formS.classList.add('hidden');
    }
}

function toggleAuthMode() {
    currentAuthMode = currentAuthMode === 'login' ? 'register' : 'login';
    const isReg = currentAuthMode === 'register';
    
    document.getElementById('auth-title').innerText = isReg ? "新規登録" : "ログイン";
    document.getElementById('auth-switch-text').innerText = isReg ? "すでにアカウントをお持ちですか？" : "アカウントをお持ちでないですか？";
    document.getElementById('auth-switch-btn').innerText = isReg ? "ログインはこちら" : "新規登録はこちら";
    
    document.getElementById('student-reg-fields').classList.toggle('hidden', !isReg);
    document.getElementById('leader-reg-fields').classList.toggle('hidden', !isReg);

    document.getElementById('btn-text-student').innerText = isReg ? "登録する" : "ログインして開始";
    document.getElementById('btn-text-leader').innerText = isReg ? "幹部として登録" : "幹部としてログイン";

    // フォームの送信先もモードに合わせて切り替える（ログイン / 新規登録）
    document.getElementById('form-student').action = isReg ? '/signup' : '/login';
    document.getElementById('form-leader').action = isReg ? '/circle_signup' : '/circle_login';
}