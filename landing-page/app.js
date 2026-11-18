/**
 * JM Vertex AI Companion — Landing Page Application Script
 * Features:
 * - FAQ Accordion Toggle
 * - 1-Click Installer Download Notification Toast
 */

document.addEventListener('DOMContentLoaded', () => {
  initFaqAccordion();
  initDownloadHandlers();
});

/* -------------------------------------------------------------
 * 1. FAQ Accordion Toggle
 * ----------------------------------------------------------- */
function initFaqAccordion() {
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    if (!question) return;

    question.addEventListener('click', () => {
      const isActive = item.classList.contains('active');
      faqItems.forEach(i => i.classList.remove('active'));
      if (!isActive) {
        item.classList.add('active');
      }
    });
  });
}

/* -------------------------------------------------------------
 * 2. Download Notification Toast & Verification
 * ----------------------------------------------------------- */
function initDownloadHandlers() {
  const downloadBtns = [
    document.getElementById('mainDownloadBtn'),
    document.getElementById('secondaryDownloadBtn'),
    ...document.querySelectorAll('.btn-full')
  ];

  downloadBtns.forEach(btn => {
    if (!btn) return;
    btn.addEventListener('click', () => {
      showToast('🚀 Downloading JM-Vertex-AI-Companion-Setup.exe...');
    });
  });
}

function showToast(message) {
  let toast = document.getElementById('toastNotification');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toastNotification';
    toast.style.position = 'fixed';
    toast.style.bottom = '24px';
    toast.style.right = '24px';
    toast.style.background = '#111C28';
    toast.style.color = '#00E676';
    toast.style.border = '1px solid #00E676';
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = '10px';
    toast.style.boxShadow = '0 10px 25px rgba(0,0,0,0.6)';
    toast.style.fontFamily = 'var(--font-mono, monospace)';
    toast.style.fontSize = '0.85rem';
    toast.style.zIndex = '9999';
    toast.style.transition = 'all 0.3s ease';
    document.body.appendChild(toast);
  }

  toast.textContent = message;
  toast.style.opacity = '1';
  toast.style.transform = 'translateY(0)';

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
  }, 4000);
}
