#!/usr/bin/env bash
#
# Instalador guiado do Comanda para um servidor Ubuntu (VPS).
#
# O que este script faz:
#   - instala as dependências de sistema (Python, Nginx, banco de dados, etc.);
#   - cria um usuário de sistema dedicado para rodar a aplicação;
#   - cria o ambiente virtual Python e instala as dependências do projeto;
#   - gera a chave secreta e o arquivo .env de produção;
#   - configura o banco de dados (PostgreSQL local, SQLite ou uma URL externa);
#   - roda as migrations e, opcionalmente, cria o super admin;
#   - configura o Gunicorn como serviço systemd (reinicia sozinho se cair);
#   - configura o Nginx como proxy reverso, com domínio ou apenas o IP;
#   - opcionalmente emite um certificado SSL gratuito (Let's Encrypt ou
#     ZeroSSL) e configura a renovação automática.
#
# Uso:
#   sudo bash deploy/install.sh
#
# O script é interativo (faz perguntas). Rode-o a partir de uma cópia do
# repositório já clonada no servidor (ex: /opt/comanda). Ele detecta
# automaticamente o diretório do projeto a partir da própria localização
# deste arquivo.

set -euo pipefail

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATES_DIR="${SCRIPT_DIR}/templates"
CONF_FILE="${SCRIPT_DIR}/.deploy.conf"

C_RESET="\033[0m"; C_BOLD="\033[1m"; C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"; C_BLUE="\033[34m"

log()  { echo -e "${C_GREEN}==>${C_RESET} ${C_BOLD}$*${C_RESET}"; }
info() { echo -e "    $*"; }
warn() { echo -e "${C_YELLOW}==> AVISO:${C_RESET} $*"; }
err()  { echo -e "${C_RED}==> ERRO:${C_RESET} $*" >&2; }
die()  { err "$*"; exit 1; }

ask() {
    # ask "pergunta" "valor_padrao" -> imprime a resposta em REPLY_VALUE
    local prompt="$1" default="${2:-}" answer
    if [ -n "$default" ]; then
        read -rp "$(echo -e "${C_BLUE}?${C_RESET} ${prompt} [${default}]: ")" answer || true
        REPLY_VALUE="${answer:-$default}"
    else
        read -rp "$(echo -e "${C_BLUE}?${C_RESET} ${prompt}: ")" answer || true
        REPLY_VALUE="${answer}"
    fi
}

confirm() {
    # confirm "pergunta" "S|n" -> retorna 0 (sim) ou 1 (não)
    local prompt="$1" default="${2:-S}" answer
    local hint="S/n"; [ "$default" = "n" ] && hint="s/N"
    read -rp "$(echo -e "${C_BLUE}?${C_RESET} ${prompt} [${hint}]: ")" answer || true
    answer="${answer:-$default}"
    [[ "$answer" =~ ^[sSyY] ]]
}

require_root() {
    if [ "$(id -u)" -ne 0 ]; then
        die "Rode este script como root (ex: sudo bash deploy/install.sh)."
    fi
}

detect_public_ip() {
    curl -fsSL --max-time 5 https://ifconfig.me 2>/dev/null \
        || curl -fsSL --max-time 5 https://api.ipify.org 2>/dev/null \
        || hostname -I 2>/dev/null | awk '{print $1}' \
        || echo ""
}

render_template() {
    # render_template arquivo_origem arquivo_destino
    local src="$1" dst="$2"
    sed \
        -e "s#__APP_DIR__#${APP_DIR}#g" \
        -e "s#__SERVICE_USER__#${SERVICE_USER}#g" \
        -e "s#__PORT__#${APP_PORT}#g" \
        -e "s#__WORKERS__#${GUNICORN_WORKERS}#g" \
        -e "s#__SERVER_NAME__#${SERVER_NAME}#g" \
        -e "s#__DB_SERVICE__#${DB_SYSTEMD_DEP:-}#g" \
        "$src" > "$dst"
}

run_as_app_user() {
    sudo -u "${SERVICE_USER}" -H bash -lc "$*"
}

# --------------------------------------------------------------------------
# 0. Checagens iniciais
# --------------------------------------------------------------------------

require_root

if [ -r /etc/os-release ]; then
    . /etc/os-release
    if [ "${ID:-}" != "ubuntu" ]; then
        warn "Este script foi feito e testado para Ubuntu. Detectado: ${PRETTY_NAME:-desconhecido}. Continuando mesmo assim."
    fi
else
    warn "Não foi possível identificar a distribuição do sistema. Continuando mesmo assim."
fi

echo
echo -e "${C_BOLD}Instalador guiado do Comanda${C_RESET}"
echo "Diretório do projeto: ${APP_DIR}"
echo

if [ -f "$CONF_FILE" ]; then
    warn "Já existe uma configuração de deploy anterior em ${CONF_FILE}."
    if ! confirm "Deseja reconfigurar (isso pode sobrescrever .env, Nginx e o serviço systemd)?" "n"; then
        die "Instalação cancelada. Use deploy/update.sh para apenas atualizar uma instalação existente."
    fi
fi

# --------------------------------------------------------------------------
# 1. Perguntas
# --------------------------------------------------------------------------

log "Domínio ou IP"
info "Deixe em branco para acessar apenas pelo IP do servidor (sem SSL — os"
info "certificados gratuitos exigem um domínio válido apontando para o servidor)."
ask "Domínio (ex: cardapio.seusite.com.br)" ""
DOMAIN="$REPLY_VALUE"

PUBLIC_IP="$(detect_public_ip)"
if [ -n "$DOMAIN" ]; then
    SERVER_NAME="$DOMAIN"
else
    if [ -z "$PUBLIC_IP" ]; then
        ask "Não consegui detectar o IP público automaticamente. Informe o IP do servidor" ""
        PUBLIC_IP="$REPLY_VALUE"
    fi
    SERVER_NAME="$PUBLIC_IP"
    info "Usando o IP do servidor: ${SERVER_NAME}"
fi

WANT_SSL="n"
SSL_PROVIDER=""
SSL_EMAIL=""
if [ -n "$DOMAIN" ]; then
    echo
    log "SSL (HTTPS)"
    if confirm "Configurar um certificado SSL gratuito para ${DOMAIN} agora?" "S"; then
        WANT_SSL="s"
        info "Antes de continuar, confirme que o DNS de ${DOMAIN} já aponta para"
        info "o IP deste servidor (${PUBLIC_IP:-desconhecido}) — a emissão do"
        info "certificado falha se o domínio ainda não resolver para cá."
        echo
        echo "  1) Let's Encrypt (via certbot) — recomendado, mais testado"
        echo "  2) ZeroSSL (via acme.sh)"
        ask "Escolha a autoridade certificadora [1/2]" "1"
        case "$REPLY_VALUE" in
            2) SSL_PROVIDER="zerossl" ;;
            *) SSL_PROVIDER="letsencrypt" ;;
        esac
        ask "E-mail para avisos de expiração/renovação do certificado" "admin@${DOMAIN}"
        SSL_EMAIL="$REPLY_VALUE"
    fi
else
    warn "Sem domínio configurado: a aplicação vai rodar em HTTP simples (http://${SERVER_NAME}/)."
    warn "Você pode rodar este script novamente mais tarde, depois de apontar um domínio para este servidor, para habilitar HTTPS."
fi

echo
log "Porta interna da aplicação"
info "O Gunicorn escuta só localmente nessa porta; o Nginx é quem fica exposto na 80/443."
ask "Porta interna (mude só se já tiver algo usando a 8000 neste servidor)" "8000"
APP_PORT="$REPLY_VALUE"

echo
log "Banco de dados"
echo "  1) PostgreSQL local (recomendado — o script instala e configura tudo)"
echo "  2) SQLite (mais simples, sem serviço extra — ok para baixo volume/poucos lojistas)"
echo "  3) Já tenho uma URL de banco (PostgreSQL gerenciado, RDS, Supabase, etc.)"
ask "Escolha [1/2/3]" "1"
DB_CHOICE="$REPLY_VALUE"

DATABASE_URL=""
DB_SYSTEMD_DEP=""
case "$DB_CHOICE" in
    2)
        DB_ENGINE="sqlite"
        GUNICORN_WORKERS=1
        info "SQLite escolhido: usando 1 worker do Gunicorn para evitar erros de 'banco travado' sob concorrência."
        ;;
    3)
        DB_ENGINE="external"
        ask "Cole a DATABASE_URL (ex: postgresql+psycopg2://usuario:senha@host:5432/banco)" ""
        DATABASE_URL="$REPLY_VALUE"
        [ -n "$DATABASE_URL" ] || die "DATABASE_URL não pode ficar em branco."
        GUNICORN_WORKERS=3
        ;;
    *)
        DB_ENGINE="postgres_local"
        DB_SYSTEMD_DEP="postgresql.service"
        GUNICORN_WORKERS=3
        ;;
esac

echo
log "Usuário de sistema"
info "A aplicação roda com um usuário dedicado, sem privilégios de root."
ask "Nome do usuário de sistema a criar/usar" "comanda"
SERVICE_USER="$REPLY_VALUE"

echo
echo -e "${C_BOLD}Resumo${C_RESET}"
echo "  Diretório do projeto : ${APP_DIR}"
echo "  Domínio/IP           : ${SERVER_NAME}"
echo "  SSL                  : $( [ "$WANT_SSL" = "s" ] && echo "sim (${SSL_PROVIDER})" || echo "não" )"
echo "  Porta interna        : ${APP_PORT}"
echo "  Banco de dados       : ${DB_ENGINE}"
echo "  Usuário de sistema   : ${SERVICE_USER}"
echo
confirm "Confirma e inicia a instalação?" "S" || die "Instalação cancelada pelo usuário."

# --------------------------------------------------------------------------
# 2. Pacotes de sistema
# --------------------------------------------------------------------------

log "Atualizando pacotes e instalando dependências de sistema..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    python3 python3-venv python3-pip python3-dev \
    build-essential libjpeg-dev zlib1g-dev \
    git curl nginx ca-certificates

if [ "$DB_ENGINE" = "postgres_local" ]; then
    apt-get install -y -qq postgresql postgresql-contrib libpq-dev
    systemctl enable --now postgresql
elif [ "$DB_ENGINE" = "external" ]; then
    case "$DATABASE_URL" in
        postgres*) apt-get install -y -qq postgresql-client libpq-dev ;;
    esac
fi

if [ "$WANT_SSL" = "s" ] && [ "$SSL_PROVIDER" = "letsencrypt" ]; then
    apt-get install -y -qq certbot python3-certbot-nginx
fi

# --------------------------------------------------------------------------
# 3. Usuário de sistema e diretório
# --------------------------------------------------------------------------

log "Configurando o usuário de sistema '${SERVICE_USER}'..."
if ! id "${SERVICE_USER}" &>/dev/null; then
    useradd --system --create-home --home-dir "/home/${SERVICE_USER}" --shell /usr/sbin/nologin "${SERVICE_USER}"
fi
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"
mkdir -p "${APP_DIR}/instance" "${APP_DIR}/app/static/uploads" "${APP_DIR}/deploy/backups"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}/instance" "${APP_DIR}/app/static/uploads" "${APP_DIR}/deploy/backups"

# --------------------------------------------------------------------------
# 4. Ambiente virtual e dependências Python
# --------------------------------------------------------------------------

log "Criando ambiente virtual e instalando dependências Python (pode levar alguns minutos)..."
run_as_app_user "cd '${APP_DIR}' && python3 -m venv venv"
run_as_app_user "cd '${APP_DIR}' && venv/bin/pip install --quiet --upgrade pip"
run_as_app_user "cd '${APP_DIR}' && venv/bin/pip install --quiet -r requirements.txt"

# --------------------------------------------------------------------------
# 5. Banco de dados
# --------------------------------------------------------------------------

if [ "$DB_ENGINE" = "postgres_local" ]; then
    log "Criando banco de dados PostgreSQL local..."
    DB_NAME="comanda"
    DB_USER="comanda"
    DB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"

    sudo -u postgres psql -v ON_ERROR_STOP=1 <<-SQL
        DO \$\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
                CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
            ELSE
                ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
            END IF;
        END
        \$\$;
        SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec
SQL

    DATABASE_URL="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"
elif [ "$DB_ENGINE" = "sqlite" ]; then
    DATABASE_URL="sqlite:////${APP_DIR}/instance/prod.db"
fi
# DB_ENGINE = external já tem DATABASE_URL preenchida pela pergunta acima.

# --------------------------------------------------------------------------
# 6. Arquivo .env
# --------------------------------------------------------------------------

log "Gerando o arquivo .env de produção..."
if [ -f "${APP_DIR}/.env" ]; then
    cp "${APP_DIR}/.env" "${APP_DIR}/.env.bak.$(date +%Y%m%d%H%M%S)"
    info "Uma cópia do .env anterior foi salva (.env.bak.<timestamp>)."
fi

SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
FORCE_HTTPS="false"
[ "$WANT_SSL" = "s" ] && FORCE_HTTPS="true"

cat > "${APP_DIR}/.env" <<ENVEOF
# Gerado por deploy/install.sh em $(date -Iseconds)
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
DATABASE_URL=${DATABASE_URL}
FORCE_HTTPS=${FORCE_HTTPS}

# Rate limiting: em memória por padrão (por worker). Para um limite
# global entre workers, instale Redis e descomente a linha abaixo.
# RATELIMIT_STORAGE_URI=redis://localhost:6379/0

# Integração Asaas (opcional) — deixe em branco para manter o
# lançamento manual de faturas. Preencha para habilitar cobrança real.
ASAAS_API_KEY=
ASAAS_ENVIRONMENT=sandbox
ASAAS_WEBHOOK_TOKEN=
ENVEOF

chown "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}/.env"
chmod 600 "${APP_DIR}/.env"

# --------------------------------------------------------------------------
# 7. Migrations e dados iniciais
# --------------------------------------------------------------------------

log "Rodando as migrations do banco de dados..."
run_as_app_user "cd '${APP_DIR}' && venv/bin/flask db upgrade"

if confirm "Criar um usuário Super Admin agora?" "S"; then
    run_as_app_user "cd '${APP_DIR}' && venv/bin/flask create-admin"
else
    info "Você pode criar depois com: sudo -u ${SERVICE_USER} bash -lc \"cd ${APP_DIR} && venv/bin/flask create-admin\""
fi

# --------------------------------------------------------------------------
# 8. Serviço systemd (Gunicorn)
# --------------------------------------------------------------------------

log "Configurando o serviço systemd..."
render_template "${TEMPLATES_DIR}/comanda.service.tmpl" "/etc/systemd/system/comanda.service"
systemctl daemon-reload
systemctl enable comanda
systemctl restart comanda
sleep 2
if ! systemctl is-active --quiet comanda; then
    err "O serviço 'comanda' não subiu corretamente. Últimas linhas do log:"
    journalctl -u comanda --no-pager -n 40
    die "Corrija o problema acima e rode: systemctl restart comanda"
fi
info "Serviço 'comanda' ativo (systemctl status comanda / journalctl -u comanda -f)."

# --------------------------------------------------------------------------
# 9. Nginx
# --------------------------------------------------------------------------

log "Configurando o Nginx..."
render_template "${TEMPLATES_DIR}/nginx.conf.tmpl" "/etc/nginx/sites-available/comanda"
ln -sf /etc/nginx/sites-available/comanda /etc/nginx/sites-enabled/comanda
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx || systemctl restart nginx

# --------------------------------------------------------------------------
# 10. SSL
# --------------------------------------------------------------------------

if [ "$WANT_SSL" = "s" ]; then
    if [ "$SSL_PROVIDER" = "letsencrypt" ]; then
        log "Emitindo certificado com Let's Encrypt (certbot)..."
        if certbot --nginx --non-interactive --agree-tos -m "${SSL_EMAIL}" -d "${DOMAIN}" --redirect; then
            info "Certificado emitido. A renovação automática já está agendada (certbot.timer)."
        else
            warn "A emissão do certificado falhou. Confira se o DNS de ${DOMAIN} já aponta para ${PUBLIC_IP:-este servidor} e rode depois:"
            warn "  certbot --nginx -d ${DOMAIN}"
        fi
    else
        log "Instalando acme.sh e emitindo certificado com ZeroSSL..."
        if [ ! -x "/root/.acme.sh/acme.sh" ]; then
            curl -fsSL https://get.acme.sh | sh -s email="${SSL_EMAIL}"
        fi
        ACME="/root/.acme.sh/acme.sh"
        "$ACME" --set-default-ca --server zerossl || true
        "$ACME" --register-account -m "${SSL_EMAIL}" --server zerossl || true
        mkdir -p "/etc/nginx/ssl/${DOMAIN}"
        if "$ACME" --issue -d "${DOMAIN}" --nginx; then
            "$ACME" --install-cert -d "${DOMAIN}" \
                --key-file       "/etc/nginx/ssl/${DOMAIN}/privkey.pem" \
                --fullchain-file "/etc/nginx/ssl/${DOMAIN}/fullchain.pem" \
                --reloadcmd      "systemctl reload nginx"
            render_template "${TEMPLATES_DIR}/nginx-ssl.conf.tmpl" "/etc/nginx/sites-available/comanda"
            nginx -t && systemctl reload nginx
            info "Certificado ZeroSSL emitido e instalado. acme.sh já agenda a renovação automática via cron."
        else
            warn "A emissão do certificado ZeroSSL falhou. Confira se o DNS de ${DOMAIN} já aponta para ${PUBLIC_IP:-este servidor} e rode depois:"
            warn "  ${ACME} --issue -d ${DOMAIN} --nginx"
        fi
    fi
fi

# --------------------------------------------------------------------------
# 11. Salva a configuração para o deploy/update.sh
# --------------------------------------------------------------------------

cat > "${CONF_FILE}" <<CONFEOF
APP_DIR=${APP_DIR}
SERVICE_USER=${SERVICE_USER}
SERVICE_NAME=comanda
APP_PORT=${APP_PORT}
DB_ENGINE=${DB_ENGINE}
DOMAIN=${DOMAIN}
SERVER_NAME=${SERVER_NAME}
SSL_ENABLED=${WANT_SSL}
CONFEOF

echo
log "Instalação concluída!"
if [ "$WANT_SSL" = "s" ]; then
    echo "  Acesse: https://${DOMAIN}/"
else
    echo "  Acesse: http://${SERVER_NAME}/"
fi
echo "  Logs da aplicação : journalctl -u comanda -f"
echo "  Reiniciar         : systemctl restart comanda"
echo "  Atualizar         : sudo bash ${APP_DIR}/deploy/update.sh"
echo
