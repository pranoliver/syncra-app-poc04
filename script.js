// ---------------------------------------------
// SYNCŔA INTERACTIONS (Lazy Initialization)
// ---------------------------------------------

// Utility: debounce reinitialization
function debounce(fn, delay = 300) {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn(...args), delay);
  };
}

// --- Core: Attach Sorting + Reasoning once per render ---
function initializeSyncraInteractions() {
  // Avoid double init
  if (window._syncraInitialized) return;
  window._syncraInitialized = true;

  console.log("🔁 Syncra JS initialized");

  // ---------- TABLE SORTING ----------
  const getCellValue = (tr, idx) =>
    tr.children[idx].innerText || tr.children[idx].textContent;

  const comparer = (idx, asc) => (a, b) => ((v1, v2) =>
    v1 !== '' && v2 !== '' && !isNaN(v1) && !isNaN(v2)
      ? v1 - v2
      : v1.toString().localeCompare(v2)
  )(getCellValue(asc ? a : b, idx), getCellValue(asc ? b : a, idx));

  document.querySelectorAll('.syncra-table th').forEach(th =>
    th.addEventListener('click', function() {
      const table = th.closest('table');
      const idx = Array.from(th.parentNode.children).indexOf(th);
      const asc = !th.classList.contains('asc');

      table.querySelectorAll('th').forEach(header => {
        header.classList.remove('asc', 'desc');
      });

      th.classList.toggle('asc', asc);
      th.classList.toggle('desc', !asc);

      Array.from(table.querySelectorAll('tr:nth-child(n+2)'))
        .sort(comparer(idx, asc))
        .forEach(tr => table.appendChild(tr));
    })
  );

  // ---------- REASONING EXPAND/COLLAPSE ----------
  document.querySelectorAll('.toggle-link').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      const cell = link.closest('.reasoning-cell');
      const preview = cell.querySelector('.preview');
      const full = cell.querySelector('.full-text');
      const isExpanded = full.style.display === 'inline';
      full.style.display = isExpanded ? 'none' : 'inline';
      preview.style.display = isExpanded ? 'inline' : 'none';
      link.textContent = isExpanded ? 'Show more' : 'Show less';
    });
  });
}

// --- Lazy Init via MutationObserver ---
const observeAppRoot = debounce(() => {
  const targetNode = document.body;
  if (!targetNode) return;

  const observer = new MutationObserver(() => {
    window._syncraInitialized = false; // reset flag
    initializeSyncraInteractions();
  });

  observer.observe(targetNode, { childList: true, subtree: true });
  initializeSyncraInteractions();
}, 500);

// Initialize once DOM ready
document.addEventListener('DOMContentLoaded', observeAppRoot);
