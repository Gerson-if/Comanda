/*
 * JS compartilhado do painel (lojista + Super Admin). Registrado com
 * `defer` em base.html, antes do Alpine, para que estas funções já
 * existam no momento em que o Alpine processa os `x-data` que as usam.
 */

/**
 * Estado do "app shell" (sidebar) usado em layouts/lojista_panel.html e
 * layouts/admin_panel.html. `collapsed` persiste em localStorage — sem
 * isso, cada navegação (app multi-página, sem hx-boost) recriava o
 * x-data do zero e o recolhimento da sidebar nunca "durava".
 */
function sidebarShell() {
  return {
    sidebarOpen: false,
    collapsed: localStorage.getItem('comandaSidebarCollapsed') === '1',
    toggleCollapsed() {
      this.collapsed = !this.collapsed;
      localStorage.setItem('comandaSidebarCollapsed', this.collapsed ? '1' : '0');
    },
  };
}

/*
 * Modal de confirmação genérico (markup em base.html, #confirmModal) —
 * substitui o confirm() nativo do navegador em toda a aplicação:
 *
 * - hx-confirm="..." (HTMX): interceptado via o evento htmx:confirm, o
 *   hook oficial do HTMX pra customizar a confirmação. Nenhum template
 *   que já usa hx-confirm precisa mudar.
 * - onsubmit="return confirm(...)" nativo: trocado por
 *   data-confirm-message="..." no <form>, interceptado aqui via o evento
 *   submit.
 *
 * `defer` garante que o DOM (incluindo #confirmModal) já existe quando
 * este script roda.
 */
(function () {
  const modalEl = document.getElementById('confirmModal');
  if (!modalEl) return;

  const messageEl = document.getElementById('confirmModalMessage');
  const confirmBtn = document.getElementById('confirmModalConfirmBtn');
  const modal = new bootstrap.Modal(modalEl);
  let pendingAction = null;

  function askConfirmation(message, onConfirm) {
    messageEl.textContent = message;
    pendingAction = onConfirm;
    modal.show();
  }

  confirmBtn.addEventListener('click', () => {
    const action = pendingAction;
    pendingAction = null;
    modal.hide();
    if (action) action();
  });

  document.body.addEventListener('htmx:confirm', (evt) => {
    if (!evt.detail.question) return;
    evt.preventDefault();
    askConfirmation(evt.detail.question, () => evt.detail.issueRequest(true));
  });

  document.addEventListener('submit', (evt) => {
    const form = evt.target;
    if (!(form instanceof HTMLFormElement)) return;
    const message = form.getAttribute('data-confirm-message');
    if (!message || form.dataset.confirmBypass === '1') return;
    evt.preventDefault();
    askConfirmation(message, () => {
      form.dataset.confirmBypass = '1';
      form.requestSubmit();
    });
  });
})();

/*
 * "+ Novo produto" cria o rascunho assim que o lojista clica, pra já
 * abrir a edição completa (fotos/complementos disponíveis desde o
 * início — ver lojista.products_create_draft). Se ele fechar a barra
 * lateral sem preencher nada, isso deixaria um card "Novo produto"
 * vazio parado no cardápio. Ao fechar o drawer, avisa o servidor pra
 * apagar o rascunho — mas só apaga se ele ainda estiver intocado
 * (Product.is_untouched_draft); qualquer dado salvo, foto ou
 * complemento cancela a limpeza.
 */
(function () {
  const drawer = document.getElementById('editDrawer');
  if (!drawer) return;

  drawer.addEventListener('hidden.bs.offcanvas', () => {
    const marker = document.getElementById('drawer-product-id');
    if (!marker) return;
    htmx.ajax('POST', marker.dataset.discardUrl, { swap: 'none' }).then(() => {
      document.body.dispatchEvent(new Event('productSaved'));
    });
  });
})();
