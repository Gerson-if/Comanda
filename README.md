# Comanda — Plataforma Multi-Tenant Completa

Stack frontend: **Bootstrap 5 + Bootstrap Icons** (identidade visual
"Comanda") + **Alpine.js** (estado reativo: carrinho de compras,
checkout, sidebar) + **HTMX** (atualizações parciais de página sem
recarregar: excluir/ativar item, upload de imagens, complementos).
Todos os assets críticos (Bootstrap, Alpine.js, HTMX, Chart.js) são
servidos localmente pelo próprio Flask — **sem dependência de CDN
externo** para a aplicação renderizar. Ver seção "Identidade visual" e
"Deploy em produção" abaixo para detalhes.

Plataforma multi-tenant de cardápio digital: Super Administrador gerencia a
plataforma e os planos; cada Lojista tem seu próprio cardápio, produtos,
pedidos e clientes, totalmente isolados dos demais.

**Fundação**: estrutura Flask, modelagem completa do banco de
dados, migrations (Alembic), SQLite pronto para desenvolvimento.

**Autenticação & Multi-tenant**: login único por e-mail/senha
para Super Admin e Lojista, contexto multi-tenant resolvido
automaticamente, autorização por papel, bloqueio de contas
suspensas/inadimplentes, CSRF e rate limiting.

**Painel do Lojista**: CRUD completo de categorias e produtos,
upload/edição/remoção de imagens, limites de plano, link compartilhável
do cardápio.

**Cardápio público**: página pública do
cardápio (Bootstrap + Alpine.js) com carrinho de compras, checkout que
**grava o pedido no banco de dados** e gera automaticamente o link do
**WhatsApp** com a mensagem do pedido pronta para envio — exatamente o
fluxo "registrar no sistema + enviar WhatsApp" definido no escopo.

O painel do Super Admin (gestão de lojistas, planos, cobrança, bloqueio)
e o painel de pedidos/vendas/financeiro do lojista entram nas próximas
fases.

## Identidade visual "Comanda"

O frontend foi completamente reconstruído a partir de modelos visuais
fornecidos pelo usuário (HTML/Bootstrap), substituindo o Tailwind CSS
por **Bootstrap 5 + Bootstrap Icons + Google Fonts** (Archivo Black,
Inter, JetBrains Mono para o tema "Comanda"; Fraunces + Plus Jakarta
Sans para o cardápio público). Alpine.js e HTMX continuam como estavam
— a mudança é só na camada visual.

**Três identidades visuais deliberadamente distintas**, todas
compartilhando os mesmos componentes (`app/static/css/comanda.css`,
classes utilitárias via `[data-bs-theme]`/CSS custom properties):

- **`.theme-chili`** (vermelho-chili `#E54A36`) — marketing (landing,
  login, cadastro, recuperação de senha) e todo o painel do lojista.
- **`.theme-blue`** (azul-índigo `#4361EE`) — painel do Super
  Administrador. A distinção de cor é proposital (evita confundir em
  qual painel você está logado) e reaproveita exatamente os mesmos
  componentes (`.panel`, `.kpi-card`, `.status-badge`, `.sidebar`) só
  trocando as variáveis CSS.
- **Cardápio público** (`store_menu.html`) — paleta âmbar/terracota
  própria (`#E8A33D`), tipografia serifada (Fraunces), pensada para
  parecer um cardápio de restaurante de verdade, não uma tela de painel
  administrativo.

**Layout**: `app/templates/layouts/lojista_panel.html` e
`admin_panel.html` implementam a mesma casca (sidebar retrátil,
colapsável em desktop, drawer em mobile) parametrizada por tema. Toda
página de painel estende um desses layouts e só preenche
`page_title`/`panel_content`.

## Funcionalidades

Esta atualização não foi só um reskin — implementei as lacunas de
lógica que os modelos visuais pressupunham e que ainda não existiam:

- **Auto-cadastro público do lojista** (`/cadastro`): qualquer pessoa
  cria sua própria loja (status `trial`) e já cai logada no painel,
  sem depender do Super Admin. Checagem de disponibilidade do
  endereço do cardápio **ao vivo**, via HTMX, enquanto digita.
- **Recuperação de senha** (`/recuperar-senha` → `/redefinir-senha/<token>`),
  que não existia antes. Token stateless via `itsdangerous` (sem
  tabela nova no banco): embute o ID do usuário e um fragmento do hash
  da senha atual, então **o token se invalida sozinho assim que a
  senha é trocada** — testado explicitamente. Como o projeto não tem
  serviço de e-mail configurado, o link é registrado no log da
  aplicação (`app/utils/mailer.py`), com um comentário claro de onde
  plugar um envio real (Flask-Mail/SendGrid/SES) em produção. A
  mensagem exibida ao usuário é sempre a mesma, exista ou não o
  e-mail — evita enumeração de contas.
- **Variações e complementos de produto** (ex: Tamanho, Molhos): o
  modelo de dados (`ComplementGroup`/`ComplementOption`) existia desde
  a Fase 1, mas nunca teve interface. Agora dá pra criar grupos
  (variação obrigatória vs. complemento opcional, escolha única ou
  múltipla) e opções com preço adicional, direto na página de edição
  do produto, atualizando só aquele bloco via HTMX.
- **Banners/carrossel promocional**: novo model (`Banner`), CRUD
  completo no painel do lojista, e exibição automática no topo do
  cardápio público (carrossel Bootstrap) quando há banners ativos.
- **Preço de custo e margem real**: campo opcional no produto; quando
  preenchido, a margem (%) e o lucro por unidade são calculados e
  mostrados ao vivo (Alpine.js) enquanto o lojista digita preço de
  venda e custo.
- **QR Code do cardápio**: gerado automaticamente na tela de
  configurações a partir da URL pública da loja.
- **Configurações da loja** organizadas em abas: dados da loja (nome,
  WhatsApp, logo), cardápio/link (slug editável, retirada/entrega),
  checkout (taxa de entrega, **entrega grátis acima de valor X** —
  testado que a taxa é isentada corretamente acima do limite e cobrada
  normalmente abaixo dele), e assinatura (plano atual + histórico de
  faturas, somente leitura).
- **Pedidos: aceitar/rejeitar rápido e reverter status**: além do
  fluxo de avanço já existente (Fase 6), agora dá pra aceitar ou
  rejeitar um pedido novo com um clique, e **voltar um passo** se o
  lojista errou ao atualizar o status (ex: marcou "em preparo" sem
  querer) — com um mapa de reversão próprio (não é só o inverso do
  fluxo de avanço; `pending` e status finais nunca têm "voltar").

## Arquitetura

```
app/
├── config.py              # Config por ambiente (Development/Testing/Production)
├── extensions.py           # db, migrate, login_manager, bcrypt, csrf, ma, limiter
├── cli.py                  # Comandos flask (seed-db, create-admin)
├── models/                  # Camada de dados (SQLAlchemy)
├── repositories/            # Acesso a dados — isolamento multi-tenant centralizado aqui
│   ├── base_repository.py    # BaseRepository / TenantScopedRepository
│   ├── user_repository.py
│   ├── category_repository.py
│   ├── product_repository.py
│   ├── product_image_repository.py
│   ├── order_repository.py     # geração de order_number sequencial por tenant
│   └── customer_repository.py  # busca/reaproveita cliente por telefone
├── services/                 # Regras de negócio
│   ├── auth_service.py
│   ├── category_service.py
│   ├── product_service.py
│   └── order_service.py       # preço sempre do servidor, regras de entrega/mínimo
├── schemas/
│   └── checkout_schema.py     # validação Marshmallow do payload de checkout
├── forms/                     # Formulários HTML com CSRF (Flask-WTF)
├── controllers/
│   ├── auth_controller.py
│   ├── admin_controller.py
│   ├── public_controller.py    # cardápio público + endpoint de checkout (JSON)
│   └── lojista/                 # painel do lojista, um blueprint em vários módulos
│       ├── dashboard.py
│       ├── categories.py
│       ├── products.py
│       └── images.py
├── utils/
│   ├── tenant_context.py     # Resolução do tenant atual (g.tenant)
│   ├── decorators.py          # @super_admin_required, @lojista_required
│   ├── slugs.py                # slug único por tenant
│   ├── uploads.py              # validação/redimensionamento de imagens (Pillow)
│   └── whatsapp.py             # monta mensagem do pedido + link wa.me
├── static/{css,uploads}/
└── templates/
    └── public/store_menu.html    # cardápio + carrinho + checkout (Alpine.js)
tests/                          # pytest — auth, multi-tenant, CRUD, checkout, WhatsApp
```

**Camadas**: Controller (rota) → Service (regra de negócio) → Repository
(query) → Model (tabela). Controllers nunca acessam o banco diretamente.

## Cardápio público e checkout

- **Página do cardápio** (`/loja/<slug>`): categorias e produtos ativos,
  organizados em seções com navegação rápida, carrinho flutuante e
  modais de carrinho/checkout — tudo em uma única página (Alpine.js),
  sem recarregar entre categorias.
- **Carrinho**: gerenciado no navegador (estado do Alpine), com
  adicionar/remover/ajustar quantidade.
- **Checkout** (`POST /loja/<slug>/pedido`, JSON): valida o payload com
  Marshmallow, cria o pedido no banco e retorna o link do WhatsApp.
  Regras de segurança e negócio aplicadas no `OrderService`:
  - **O preço nunca vem do cliente** — o carrinho envia só
    `product_id` + `quantity`; o preço usado é sempre o preço atual do
    produto no banco. Testado explicitamente enviando um preço
    manipulado no payload e confirmando que é ignorado.
  - Produto precisa pertencer ao tenant do slug acessado e estar ativo
    — um `product_id` de outra loja, ou de um produto desativado, é
    rejeitado (testado).
  - Entrega exige rua, número e bairro (reforçado tanto no schema
    quanto no `CHECK CONSTRAINT` do banco, camada dupla).
  - Respeita `Tenant.delivery_enabled` / `pickup_enabled` — se o
    lojista desabilitou entrega, o pedido de entrega é recusado mesmo
    que o cliente tente forçar via requisição direta.
  - Respeita `Tenant.min_order_cents`, quando configurado.
  - Cliente final é reconhecido pelo telefone — pedidos repetidos do
    mesmo número reaproveitam o mesmo `Customer` (histórico
    consolidado para relatórios futuros).
  - `order_number` sequencial **por loja** (não é o ID global da
    tabela), com nova tentativa automática em caso de colisão sob
    concorrência.
- **WhatsApp**: `app/utils/whatsapp.py` monta uma mensagem de texto
  formatada com itens, subtotal, taxa de entrega, endereço (se
  aplicável), forma de pagamento e observações, e gera o link
  `https://wa.me/<numero>?text=<mensagem>`. O envio final é feito pelo
  navegador do cliente (o link já abre o WhatsApp com a mensagem
  pronta) — não depende de credenciais de API externa.

## Pedidos, vendas e relatórios financeiros

- **Gestão de pedidos** (`/painel/pedidos`): listagem paginada com filtro
  por status, e página de detalhe com itens, endereço de entrega (ou
  aviso de retirada), forma de pagamento e observações do cliente.
- **Fluxo de status com transições validadas no servidor** — não é um
  simples toggle: `OrderService.update_status` valida contra um mapa de
  transições permitidas (`pending → confirmed → preparing →
  out_for_delivery/ready_for_pickup → completed`, com `canceled`
  disponível em qualquer ponto antes de `completed`). Pular etapas (ex:
  ir direto de "recebido" para "concluído") é rejeitado mesmo que
  alguém tente forçar via requisição direta — testado explicitamente.
  Os botões de ação na tela mostram sempre só as transições válidas a
  partir do status atual.
- **Vendas e relatórios** (`/painel/vendas`): receita de hoje, da
  semana, do mês e histórico total; contagem de pedidos por status;
  ranking dos produtos mais vendidos (quantidade e receita); gráfico de
  receita dos últimos 14 dias (Chart.js). **Pedidos cancelados são
  excluídos do cálculo de receita** — testado.
- Todos os números são calculados a partir do próprio tenant da sessão
  (nunca de um parâmetro de URL), mantendo o mesmo isolamento
  multi-tenant do resto da aplicação.

## Melhorias transversais desta atualização

- **Paginação real**, antes ausente: listagem de produtos do lojista,
  listagem de pedidos e listagem de lojistas do Super Admin agora
  paginam (componente reutilizável em `templates/_pagination.html`,
  preservando filtros de busca/status ao trocar de página).
- **Dashboard do lojista** ganhou um quarto card com a receita do dia,
  e atalhos diretos para Pedidos e Vendas.
- **Navbar** ganhou os links de Pedidos e Vendas (lojista).

## Painel do Super Admin

- **Gestão de lojistas**: criar (já com o usuário lojista/dono junto,
  pronto pra logar), listar com busca por nome/e-mail/slug e filtro por
  status, editar dados, excluir permanentemente (com confirmação e
  cascade real no banco — categorias, produtos, pedidos, clientes,
  faturas e o usuário lojista somem junto).
- **Transições de status da conta**, cada uma com motivo opcional
  registrado (`Tenant.blocked_reason` / `blocked_at`):
  - **Ativar** — libera o acesso.
  - **Suspender** — bloqueia manualmente (ex: revisão de cadastro).
  - **Bloquear por inadimplência** — o mesmo `TenantStatus.BLOCKED_PAYMENT`
    já usado desde a Fase 2, que impede login do lojista e derruba o
    cardápio público para 404.
  - **Cancelar** — encerramento definitivo da conta.
  - Testado explicitamente: bloquear impede login do lojista com a
    mensagem correta; ativar depois restaura o acesso imediatamente.
- **Planos**: CRUD completo (nome, preço, ciclo mensal/anual, limites de
  categorias/produtos/imagens), com ativar/desativar via clique no badge
  (HTMX, mesmo padrão da Fase 3).
- **Cobrança (faturas)**: o Super Admin lança faturas manualmente para
  um lojista (não há gateway de pagamento integrado nesta fase). Uma
  `Subscription` ativa é criada automaticamente na primeira fatura, com
  o período calculado a partir do ciclo do plano. **Marcar uma fatura
  como paga libera automaticamente um lojista que estava bloqueado por
  inadimplência** — testado de ponta a ponta: bloquear → tentar logar
  (falha) → lançar fatura → marcar como paga → tentar logar de novo
  (funciona).
- Todas as rotas protegidas por `@super_admin_required`; testado que um
  lojista tentando acessar `/admin/lojistas` ou `/admin/planos` recebe
  403.

## Estratégia multi-tenant

Banco compartilhado, schema compartilhado, isolamento por coluna
`tenant_id` (`TenantScopedMixin`). Reforçado em código por
`TenantScopedRepository` (exige `tenant_id` no construtor) e, na camada de
requisição, por `app/utils/tenant_context.py`:

- **Lojista autenticado**: `g.tenant` é resolvido automaticamente a partir
  de `current_user.tenant` em todo request (`before_request`).
- **Visitante do cardápio público** (`/loja/<slug>`): `g.tenant` é
  resolvido pelo slug da URL. Lojas com conta suspensa, bloqueada por
  inadimplência ou cancelada retornam **404**.

`get_current_tenant()` é o único ponto de leitura do tenant atual usado
pelo resto da aplicação.

## Painel do Lojista

- **Categorias**: criar, listar, editar, excluir. Excluir uma categoria
  não apaga os produtos dela — eles ficam "sem categoria".
- **Produtos**: criar, listar (com filtro por categoria), editar,
  excluir. Preço digitado em reais (`94.90`) é convertido e armazenado em
  centavos (`9490`).
- **Imagens**: upload com validação real de conteúdo (Pillow),
  redimensionamento automático (máx. 1600px), armazenamento isolado por
  tenant em disco, definição de imagem principal, remoção.
- **Limites de plano**: `Plan.max_categories` / `Plan.max_products`
  checados na criação.
- **Link do cardápio**: exibido no dashboard com botão "Copiar link".

## Autenticação e autorização

- Login único por e-mail + senha (`/login`) para Super Admin e Lojista.
- `app/services/auth_service.py` centraliza as regras: credenciais
  inválidas, usuário inativo, e conta do lojista bloqueada.
- `@super_admin_required` e `@lojista_required` bloqueiam com **403** o
  acesso cruzado entre papéis.
- CSRF habilitado em todos os formulários e no endpoint JSON de
  checkout (validado via cabeçalho `X-CSRFToken`).
- Rate limiting no login: 10 tentativas por minuto por IP.

## Testes automatizados

```bash
pytest tests/ -v
```

123 testes cobrindo: login válido/inválido, redirecionamento por papel,
bloqueio de acesso cruzado (403), bloqueio de conta por inadimplência,
resolução multi-tenant por slug, CRUD de categorias e produtos,
conversão de preço para centavos, upload de imagem válida/inválida,
isolamento entre lojistas, limite de plano, **checkout público**
(pedido criado corretamente, preço sempre do servidor mesmo com payload
manipulado, numeração sequencial por loja, validação de endereço de
entrega, regras de entrega/retirada habilitadas pelo lojista, pedido
mínimo, carrinho vazio rejeitado, produto de outro tenant rejeitado,
produto inativo rejeitado, link do WhatsApp gerado corretamente,
cliente recorrente reaproveitado), **interações HTMX** (toggle de
status via clique no badge, exclusão inline sem navegação, fallback
sem HTMX continua funcionando, upload de imagem retorna o fragmento
da galeria com a mensagem certa) e **limites de campo do login**
(senha acima do limite é rejeitada, atributos `maxlength` presentes no
HTML), e **painel do Super Admin** (criar lojista com usuário dono
funcional, e-mail duplicado rejeitado, busca/filtro de lojistas, editar
dados, exclusão em cascata, todas as transições de status incluindo o
ciclo completo bloqueio→login falha→fatura paga→login funciona, CRUD e
toggle de planos, lançamento e cancelamento de faturas, isolamento de
acesso do lojista às rotas do Super Admin), e **pedidos e relatórios**
(listagem e filtro por status, detalhe com itens e totais corretos,
transição de status válida aceita, transição inválida rejeitada com o
pedido permanecendo no status original, fluxo completo do pedido do
recebimento à conclusão, pedido em status final sem mais transições
disponíveis, isolamento entre lojistas, resumo de receita reflete os
pedidos criados, pedidos cancelados excluídos do cálculo de receita,
ranking de produtos mais vendidos correto), e **funcionalidades da
Fase 7** (auto-cadastro cria loja trial + login automático, e-mail
duplicado rejeitado no cadastro, checagem de slug disponível/ocupado,
recuperação de senha com mensagem genérica independente do e-mail
existir, fluxo completo de redefinição de senha, token de recuperação
inválido rejeitado, token invalidado após a troca de senha, senhas
que não coincidem rejeitadas, CRUD e toggle de banner, banner ativo
aparece no cardápio público, criação de grupo de variação/complemento
com opção, isolamento entre tenants na gestão de complementos, reverter
status volta exatamente um passo, pedido pendente não pode reverter,
aceitar/rejeitar pedido rápido, entrega grátis isentada acima do valor
configurado e cobrada normalmente abaixo dele, cálculo de margem com e
sem preço de custo, atualização de dados da loja/cardápio/checkout). E **testes de regressão anti-tela-branca e de produção**
(a tag `<body>` nunca mais pode ter `x-cloak`, os assets críticos nunca
mais podem depender de CDN externo, os arquivos locais de
Bootstrap/Alpine/HTMX/Chart.js existem e não estão corrompidos, o app
recusa subir em produção sem `DATABASE_URL`, recusa subir sem
`SECRET_KEY` customizada, sobe normalmente com config válida, e o QR
Code é gerado localmente sem API externa).

## Como rodar localmente (SQLite)

```bash
# 1. Ambiente virtual
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Dependências
pip install -r requirements.txt

# 3. Variáveis de ambiente (.flaskenv já define FLASK_APP/FLASK_ENV)
cp .env.example .env

# 4. Banco de dados (SQLite, criado em instance/dev.db)
flask db upgrade

# 5. Dados iniciais (super admin + plano + loja demo)
flask seed-db

# 6. Rodar
flask run
```

Acesse `http://127.0.0.1:5000/` para ver a landing page pública, ou vá
direto para `http://127.0.0.1:5000/login` com:

| Papel        | E-mail                          | Senha       |
|--------------|----------------------------------|-------------|
| Super Admin  | admin@cardapio.saas              | admin123    |
| Lojista      | lojista@braseiroecia.com.br      | lojista123  |

Cardápio público de demonstração: `http://127.0.0.1:5000/loja/braseiro-cia`
(crie uma categoria e um produto pelo painel do lojista antes, para ver
o cardápio populado).

Você também pode criar sua própria loja sem passar pelo Super Admin,
via auto-cadastro: `http://127.0.0.1:5000/cadastro` — o endereço do
cardápio é validado em tempo real enquanto você digita.

Para testar a recuperação de senha (`/recuperar-senha`), como não há
serviço de e-mail configurado em desenvolvimento, o link de redefinição
aparece no console/log do `flask run`, não na tela.

Como Super Admin (`admin@cardapio.saas`), acesse `/admin/lojistas` para
criar novos lojistas (o formulário já cria a loja e o usuário de login
dele juntos), gerenciar planos em `/admin/planos`, e usar as ações de
bloquear/suspender/ativar/cancelar e lançar faturas na página de
detalhe de cada lojista.

(troque essas senhas antes de qualquer uso além de desenvolvimento local)

## Deploy em produção

### Correções recentes importantes (leia se você viu tela branca)

Se a aplicação abria e mostrava **tela branca** (nada renderizava, nem
erro), a causa era um bug real que corrigimos: a tag `<body>` tinha o
atributo `x-cloak` do Alpine.js, e o CSS tem a regra
`[x-cloak] { display: none !important; }`. Isso deixava a **página
inteira invisível até o Alpine.js terminar de carregar** — se o CDN do
Alpine falhasse, atrasasse, ou qualquer script da página desse erro
antes disso, a tela ficava branca para sempre. Removemos `x-cloak` do
`<body>` (ele continua, corretamente, em elementos pequenos e
específicos como modais).

Na mesma limpeza, **paramos de depender de CDNs externos** para o que é
essencial pra página renderizar: Bootstrap, Bootstrap Icons, Alpine.js,
HTMX e Chart.js agora são servidos pelo próprio Flask, a partir de
`app/static/vendor/` — não tem mais risco de firewall corporativo, CSP,
ou o CDN estar fora do ar deixando a aplicação quebrada. (As Google
Fonts continuam via CDN — se falharem, o navegador só cai numa fonte
padrão, a página não quebra.) O QR Code do cardápio também parou de
depender de uma API externa (`api.qrserver.com`) e passou a ser gerado
localmente com a biblioteca `qrcode`.

Se você atualizou de uma versão anterior deste projeto, rode
`git pull`/reimporte os arquivos e reinicie o servidor — não precisa de
migration nova para essa correção.

### Checklist antes de subir em produção

1. **`SECRET_KEY`** — obrigatória, o app recusa iniciar com o valor
   padrão de desenvolvimento. Gere uma com:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
2. **`DATABASE_URL`** — obrigatória, aponte para um PostgreSQL real.
3. **HTTPS** — por padrão o cookie de sessão exige conexão HTTPS
   (`SESSION_COOKIE_SECURE=True`). Se você ainda não configurou HTTPS
   (certificado/proxy reverso) e está testando direto por HTTP, o
   login vai "não funcionar" silenciosamente — defina
   `FORCE_HTTPS=false` **temporariamente** até ter HTTPS de verdade.
4. **Atrás de um proxy reverso** (nginx, Render, Railway, Fly.io, load
   balancer) — já está coberto: o app aplica `ProxyFix` automaticamente
   em produção, então os cabeçalhos `X-Forwarded-*` são respeitados.
5. **Migrations** — rode `flask db upgrade` antes do primeiro start
   (e a cada deploy que inclua mudança de schema).
6. **Rate limiting com múltiplos workers** — o limitador padrão é em
   memória (não compartilhado entre processos). Com `gunicorn -w N`
   (N > 1), configure `RATELIMIT_STORAGE_URI=redis://...` para um
   limite realmente global; sem isso, o rate limit funciona, só que
   por worker.

### Opção 1 — Docker (qualquer plataforma que rode containers)

```bash
docker build -t comanda .
docker run --env-file .env -p 8000:8000 comanda flask db upgrade   # uma vez
docker run --env-file .env -p 8000:8000 comanda                    # sobe o servidor
```

### Opção 2 — Heroku / Railway / similares (usam `Procfile`)

O `Procfile` já está configurado (`web` + `release` para rodar
migrations automaticamente a cada deploy). Basta conectar o repositório
e configurar as variáveis de ambiente do checklist acima.

### Opção 3 — Servidor próprio / VM

```bash
export FLASK_ENV=production
export SECRET_KEY="uma-chave-bem-aleatoria"
export DATABASE_URL="postgresql+psycopg2://usuario:senha@host:5432/cardapio_saas"

pip install -r requirements.txt
flask db upgrade
flask create-admin   # cria o super admin de produção interativamente
gunicorn -w 4 -b 0.0.0.0:8000 --timeout 60 --preload wsgi:app
```

Coloque um nginx (ou similar) na frente para TLS e para servir
`/static` diretamente com mais performance (opcional — o Flask também
serve `/static` corretamente sozinho, só que sem cache/compressão
otimizados).

### Verificando que subiu certo

- `GET /healthz` deve responder `{"status": "ok"}` — use isso como
  health check do seu orquestrador/plataforma.
- Se a tela continuar branca depois de tudo isso, abra o DevTools do
  navegador (F12 → aba Console/Network) — qualquer erro de carregamento
  de asset ou JavaScript vai aparecer ali, e com os assets agora
  locais, praticamente elimina causas externas.

## Comandos úteis

```bash
flask db migrate -m "descrição"   # gera nova migration a partir de mudanças nos models
flask db upgrade                   # aplica migrations pendentes
flask db downgrade                 # reverte a última migration
flask seed-db                      # popula dados mínimos (idempotente)
flask create-admin                 # cria/atualiza um super admin específico
pytest tests/ -v                    # roda a suíte de testes
```

## Modal de produto e variações/complementos no checkout (esta atualização)

O cardápio público ganhou um modal de produto (inspirado no modelo visual
fornecido) que corrige uma lacuna real: o modelo de dados de
variações/complementos (`ComplementGroup`/`ComplementOption`) existia
desde a Fase 1, e a Fase 7 deu a ele uma tela de gestão no painel do
lojista — mas o checkout do cliente final nunca soube que isso existia.
Agora:

- Clicar num produto abre um modal com imagem, descrição, grupos de
  variação (ex: Tamanho, escolha única) e complementos (ex: Molhos,
  múltipla escolha), com o preço final recalculado ao vivo.
- O carrinho passou a ser indexado por produto **+ combinação de
  opções escolhidas** — dois lançamentos do mesmo produto com opções
  diferentes viram linhas separadas no carrinho, corretamente.
- No servidor, `OrderService._resolve_options` valida tudo de novo,
  nunca confiando no navegador: grupo obrigatório sem escolha é
  rejeitado, grupo de escolha única com mais de uma opção é rejeitado,
  e uma opção que não pertence àquele produto/tenant é rejeitada —
  testei explicitamente uma tentativa de injetar o ID de uma opção de
  outra loja.
- As escolhas ficam registradas por item (`OrderItemChoice`, tabela que
  já existia desde a Fase 1 mas nunca era populada) e aparecem tanto no
  detalhe do pedido no painel do lojista quanto na mensagem do
  WhatsApp gerada.

## Validações reforçadas (esta atualização)

- **Telefone/WhatsApp**: antes só validava tamanho de texto; agora
  extrai os dígitos e exige uma quantidade plausível (10 a 15),
  tolerando formatação com parênteses/hífens/espaços. Aplicado no
  auto-cadastro, nos formulários do Super Admin, nas configurações da
  loja e no checkout público.
- **Nomes só com espaço** (categoria, produto, banner, grupo/opção de
  complemento) são rejeitados.
- **Slug do cardápio** nas configurações do lojista agora valida
  formato (letras minúsculas, números, hífen) antes de chegar no
  serviço.
- **Preço de custo maior que preço de venda** é bloqueado no formulário
  de produto — evita cadastrar sem querer uma margem negativa por
  trocar os dois campos.
- **Endereço de entrega** não aceita mais uma string só de espaços em
  branco disfarçada de preenchida.

## Integração com Asaas — cobrança das faturas dos lojistas (esta atualização)

O Super Admin já lançava e marcava faturas manualmente (Fase 5). Esta
atualização prepara — e implementa de verdade, na medida do que dá pra
testar sem uma conta real — a integração com o
[Asaas](https://www.asaas.com) para gerar cobrança de verdade
(boleto/Pix/cartão) e liberar a loja automaticamente quando o pagamento
é confirmado.

**⚠️ Aviso importante**: o código foi escrito seguindo a estrutura
pública documentada da API v3 do Asaas (endpoints, payload, nomes de
campo), mas **não há uma conta Asaas conectada neste ambiente** — não
foi possível testar contra a API real. Os testes automatizados cobrem
que o *nosso* código monta a requisição certa e trata a resposta certa
(via mocks), não que a API do Asaas de fato se comporta assim hoje.
**Antes de usar em produção, valide contra o ambiente sandbox do Asaas**
com uma chave de API de teste e confira a documentação oficial atual.

### Como funciona

- **Desligado por padrão.** Sem `ASAAS_API_KEY` configurada, nada muda
  — o fluxo manual de fatura continua exatamente como era.
- **Como ligar**: defina `ASAAS_API_KEY` (painel do Asaas → Integrações
  → API) e, se for usar em produção de verdade, `ASAAS_ENVIRONMENT=production`
  (o padrão é `sandbox`, o ambiente de testes do próprio Asaas).
- Com a chave configurada, cada fatura pendente na tela de detalhe do
  lojista (`/admin/lojistas/<id>`) ganha um botão **"Gerar cobrança
  Asaas"**, que cria (ou reaproveita) um cliente no Asaas vinculado ao
  tenant e gera uma cobrança com Pix/boleto/cartão à escolha do
  lojista, mostrando o link de pagamento.
- **Webhook de confirmação**: configure no painel do Asaas a URL
  `https://SEU-DOMINIO/webhooks/asaas` com o token definido em
  `ASAAS_WEBHOOK_TOKEN` (invente uma string aleatória e use o mesmo
  valor nos dois lugares — sem isso o webhook não é aceito, para que
  ninguém consiga forjar uma notificação de "pagamento confirmado" e
  liberar uma loja bloqueada de graça). Quando o Asaas confirma o
  pagamento, o webhook chama exatamente a mesma lógica de "marcar como
  paga" que já existia — a loja bloqueada por inadimplência é liberada
  automaticamente, sem o Super Admin precisar fazer nada.
- Sem `ASAAS_WEBHOOK_TOKEN` configurado, o endpoint de webhook recusa
  qualquer chamada (503) — é impossível ele processar algo por engano
  sem essa configuração explícita.

### Arquitetura da integração

```
app/services/payment_gateway/
├── base.py            # contrato abstrato (facilita trocar/adicionar gateway no futuro)
├── asaas_gateway.py    # implementação real (requests → API do Asaas)
└── __init__.py         # get_gateway() — retorna None se não configurado
app/controllers/webhooks_controller.py   # POST /webhooks/asaas
```

`AdminBillingService.generate_asaas_charge(invoice)` orquestra:
cria/reaproveita o cliente Asaas do tenant → cria a cobrança → salva
`asaas_payment_id` e `payment_link_url` na fatura. `mark_paid_by_asaas_payment_id`
é chamado pelo webhook para casar a notificação com a fatura certa.

## Roadmap

1. ~~Fundação: Flask + banco de dados + migrations~~ ✅
2. ~~Autenticação (login por e-mail/senha) + middleware multi-tenant~~ ✅
3. ~~Painel do Lojista (produtos, categorias, imagens, link do cardápio)~~ ✅
4. ~~Cardápio público (Alpine.js + HTMX) + checkout que grava o pedido
   no banco e dispara o WhatsApp~~ ✅
5. ~~Painel do Super Admin (lojistas, planos, cobrança, bloqueio)~~ ✅
6. ~~Pedidos, vendas e relatórios financeiros (painel do lojista)~~ ✅
7. ~~Identidade visual "Comanda" + auto-cadastro + recuperação de senha +
   variações/complementos + banners + custo/margem + QR Code~~ ✅ (esta fase)

Todas as fases do escopo original, mais os aprimoramentos visuais e de
produto pedidos na Fase 7, foram entregues. Itens que ficam
conscientemente fora do escopo atual, e por quê:

- **Envio real de e-mail**: a recuperação de senha funciona de ponta a
  ponta, mas o link é registrado em log em vez de enviado — não há
  serviço de e-mail (SMTP/SendGrid/SES) configurado no projeto. A
  integração real é uma função só (`app/utils/mailer.py`).
- **Gateway de pagamento real**: faturas continuam sendo lançadas
  manualmente pelo Super Admin; não há cobrança recorrente automática
  nem checkout de assinatura self-service para o lojista.
- **API oficial do WhatsApp Business**: o envio continua via link
  `wa.me` aberto pelo navegador do cliente, não uma integração
  server-to-server.
- **Testes de navegador (visual)**: toda a cobertura de testes é via
  `pytest` + test client Flask (HTTP, HTML, regras de negócio) — não há
  Selenium/Playwright validando renderização real em um navegador.
