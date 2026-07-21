// fragments/article.js — 29 篇文章共用 scroll handler
// 滚动超过 8px 时给 .topbar 加 .scrolled class,加深阴影
const bar = document.querySelector('.topbar');
if (bar) {
  addEventListener('scroll', () => bar.classList.toggle('scrolled', scrollY > 8), { passive: true });
}