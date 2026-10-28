// --- 学生向け：いいね（グッド）トグル ---
function toggleGood(btn) {
    const icon = btn.querySelector('i');
    const span = btn.querySelector('.count');
    let count = parseInt(span.innerText);
    
    if (icon.classList.contains('fa-regular')) {
        icon.classList.replace('fa-regular', 'fa-solid');
        btn.classList.add('text-brand-600');
        span.innerText = count + 1;
    } else {
        icon.classList.replace('fa-solid', 'fa-regular');
        btn.classList.remove('text-brand-600');
        span.innerText = count - 1;
    }
}