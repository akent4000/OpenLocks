document.addEventListener('DOMContentLoaded', function() {
    var btn   = document.getElementById('toggle-instructions-btn'),
        block = document.getElementById('instructions-block');
    if (!btn || !block) return;
    btn.addEventListener('click', function() {
      block.style.display = (block.style.display === 'none') ? 'block' : 'none';
    });
  });
  