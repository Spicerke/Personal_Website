const tabLinks = document.querySelectorAll('.tab-link');

function updateActiveTab() {
  const offset = window.scrollY + 120;
  let activeId = 'about';

  document.querySelectorAll('.content-section, .hero').forEach((section) => {
    if (section.offsetTop <= offset) {
      activeId = section.id;
    }
  });

  tabLinks.forEach((link) => {
    const target = link.getAttribute('href').slice(1);
    if (target === activeId) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });
}

window.addEventListener('scroll', updateActiveTab);
window.addEventListener('load', updateActiveTab);

tabLinks.forEach((link) => {
  link.addEventListener('click', () => {
    setTimeout(updateActiveTab, 200);
  });
});
