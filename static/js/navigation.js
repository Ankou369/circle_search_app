// --- 画面遷移＆ナビゲーション制御 ---
function switchScreen(targetName) {
    // 全画面非表示
    document.querySelectorAll('.screen-content').forEach(el => el.classList.add('hidden'));
    
    // 対象画面表示
    const targetEl = document.getElementById(`screen-${targetName}`);
    if (targetEl) targetEl.classList.remove('hidden');

    // ボトムナビの表示・非表示とハイライト切り替え
    const navS = document.getElementById('nav-student');
    const navL = document.getElementById('nav-leader');
    
    if (targetName === 'auth' || targetName === 'diagnostic') {
        navS.classList.add('hidden');
        navL.classList.add('hidden');
    } else if (targetName.startsWith('student-')) {
        navS.classList.remove('hidden');
        navL.classList.add('hidden');
        updateNavHighlight('student', targetName);
    } else if (targetName.startsWith('leader-')) {
        navL.classList.remove('hidden');
        navS.classList.add('hidden');
        updateNavHighlight('leader', targetName);
    }
}
