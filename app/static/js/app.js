document.querySelectorAll('[data-dismiss]').forEach((button) => {
  button.addEventListener('click', () => button.closest('.alert').remove());
});

const menuButton = document.querySelector('[data-nav-toggle]');
const closeMenu = () => {
  document.body.classList.remove('nav-open');
  menuButton?.setAttribute('aria-expanded', 'false');
};
menuButton?.addEventListener('click', () => {
  const open = document.body.classList.toggle('nav-open');
  menuButton.setAttribute('aria-expanded', String(open));
});
document.querySelector('[data-nav-close]')?.addEventListener('click', closeMenu);
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeMenu();
});

document.querySelectorAll('[data-password-toggle]').forEach((button) => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.passwordToggle);
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    button.textContent = visible ? 'Tutup' : 'Lihat';
    button.setAttribute('aria-label', visible ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi');
  });
});

document.querySelectorAll('[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

document.querySelectorAll('[data-region-form]').forEach((form) => {
  const rwSelect = form.querySelector('[name="rw_id"]');
  const rtSelect = form.querySelector('[name="rt_id"]');
  const roleSelect = form.querySelector('[name="role"]');
  if (!rwSelect || !rtSelect) return;
  const updateRegion = () => {
    const requiresRt = !roleSelect || ['RT', 'WARGA'].includes(roleSelect.value);
    rtSelect.disabled = !requiresRt;
    rtSelect.required = requiresRt;
    [...rtSelect.options].forEach((option) => {
      if (!option.dataset.rw) return;
      const matches = option.dataset.rw === rwSelect.value;
      option.hidden = !matches;
      option.disabled = !matches;
      if (!matches && option.selected) rtSelect.value = '0';
    });
  };
  rwSelect.addEventListener('change', updateRegion);
  roleSelect?.addEventListener('change', updateRegion);
  updateRegion();
});

document.querySelectorAll('[data-upload-group]').forEach((group) => {
  const input = group.querySelector('[data-upload-input]');
  const preview = group.querySelector('[data-upload-preview]');
  const error = group.querySelector('[data-upload-error]');
  const zone = group.querySelector('.upload-zone');
  let previewUrls = [];
  const renderPreview = () => {
    previewUrls.forEach((url) => URL.revokeObjectURL(url));
    previewUrls = [];
    preview.replaceChildren();
    error.textContent = '';
    input.setCustomValidity('');
    const files = [...input.files];
    let message = '';
    if (files.length > 3) message = 'Pilih maksimal 3 foto.';
    else if (files.some((file) => file.size > 3 * 1024 * 1024)) message = 'Ukuran setiap foto maksimal 3 MB.';
    else if (files.some((file) => !['image/jpeg', 'image/png', 'image/webp'].includes(file.type))) message = 'Gunakan foto JPG, PNG, atau WebP.';
    if (message) {
      error.textContent = message;
      input.setCustomValidity(message);
      return;
    }
    files.forEach((file, index) => {
      const item = document.createElement('div');
      item.className = 'preview-item';
      const image = document.createElement('img');
      image.src = URL.createObjectURL(file);
      image.alt = file.name;
      previewUrls.push(image.src);
      const name = document.createElement('span');
      name.textContent = file.name;
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = 'x';
      remove.setAttribute('aria-label', 'Hapus foto ' + file.name);
      remove.addEventListener('click', () => {
        const transfer = new DataTransfer();
        [...input.files].filter((unusedFile, fileIndex) => fileIndex !== index).forEach((keptFile) => transfer.items.add(keptFile));
        input.files = transfer.files;
        renderPreview();
      });
      item.append(image, name, remove);
      preview.append(item);
    });
  };
  input.addEventListener('change', renderPreview);
  ['dragenter', 'dragover'].forEach((eventName) => zone.addEventListener(eventName, (event) => {
    event.preventDefault();
    zone.classList.add('drag-over');
  }));
  ['dragleave', 'drop'].forEach((eventName) => zone.addEventListener(eventName, (event) => {
    event.preventDefault();
    zone.classList.remove('drag-over');
  }));
  zone.addEventListener('drop', (event) => {
    input.files = event.dataTransfer.files;
    renderPreview();
  });
});
