// --- サークル一覧の検索（入力に合わせてその場で絞り込む） ---
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('circle-search');
    if (!input) return;

    input.addEventListener('input', () => {
        const keyword = input.value.trim().toLowerCase();
        let visible = 0;

        document.querySelectorAll('.circle-card').forEach(card => {
            const name = (card.dataset.name || '').toLowerCase();
            const show = name.includes(keyword);
            card.classList.toggle('hidden', !show);
            if (show) visible++;
        });

        const noResult = document.getElementById('circle-no-result');
        if (noResult) {
            noResult.classList.toggle('hidden', visible !== 0);
        }
    });
});
