// --- サークル一覧の検索（入力に合わせてその場で絞り込む） ---
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('circle-search-input');
    if (!input) return;

    const filter = () => {
        // 「#音楽系」でも「音楽系」でもヒットするよう、#は取り除いて比べる
        const keyword = input.value.trim().toLowerCase().replace(/#/g, '');
        let visible = 0;

        document.querySelectorAll('.circle-card').forEach(card => {
            const name = (card.dataset.name || '').toLowerCase();
            const show = name.includes(keyword);
            card.classList.toggle('hidden', !show);
            if (show) visible++;
        });

        const noResult = document.getElementById('circle-search-empty');
        if (noResult) {
            noResult.classList.toggle('hidden', visible !== 0);
        }
    };

    input.addEventListener('input', filter);

    // 詳細ページのハッシュタグから来たとき（/list?q=音楽系）は最初から絞り込む
    const q = new URLSearchParams(window.location.search).get('q');
    if (q) {
        input.value = q;
        filter();
    }
});
