#!/usr/bin/env bash
#
# Atualização segura do Comanda: busca a versão mais nova do repositório,
# aplica migrations e reinicia a aplicação — com backup do banco e
# rollback automático se algo der errado no caminho.
#
# Uso:
#   sudo bash deploy/update.sh
#
# Pré-requisito: a máquina já configurada por deploy/install.sh (existe
# deploy/.deploy.conf) e o git remoto já com acesso configurado (SSH ou
# um token de acesso na URL do remote), já que este script só dá
# `git fetch` / `git pull` — não lida com autenticação.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_FILE="${SCRIPT_DIR}/.deploy.conf"

C_RESET="\033[0m"; C_BOLD="\033[1m"; C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"
log()  { echo -e "${C_GREEN}==>${C_RESET} ${C_BOLD}$*${C_RESET}"; }
info() { echo -e "    $*"; }
warn() { echo -e "${C_YELLOW}==> AVISO:${C_RESET} $*"; }
err()  { echo -e "${C_RED}==> ERRO:${C_RESET} $*" >&2; }
die()  { err "$*"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Rode este script como root (ex: sudo bash deploy/update.sh)."
[ -f "$CONF_FILE" ] || die "Não encontrei ${CONF_FILE}. Rode deploy/install.sh primeiro."

# shellcheck disable=SC1090
source "$CONF_FILE"

APP_DIR="${APP_DIR:?}"
SERVICE_USER="${SERVICE_USER:?}"
SERVICE_NAME="${SERVICE_NAME:-comanda}"
APP_PORT="${APP_PORT:-8000}"
DB_ENGINE="${DB_ENGINE:-postgres_local}"

BACKUP_DIR="${APP_DIR}/deploy/backups"
KEEP_BACKUPS=5
STAMP="$(date +%Y%m%d%H%M%S)"

run_as_app_user() { sudo -u "${SERVICE_USER}" -H bash -lc "$*"; }

get_database_url() {
    grep -m1 '^DATABASE_URL=' "${APP_DIR}/.env" | cut -d= -f2- || true
}

backup_database() {
    mkdir -p "$BACKUP_DIR"
    local db_url; db_url="$(get_database_url)"
    case "$db_url" in
        postgres*)
            log "Fazendo backup do PostgreSQL..."
            if run_as_app_user "pg_dump --clean --if-exists '${db_url}' > '${BACKUP_DIR}/db_${STAMP}.sql'"; then
                echo "${BACKUP_DIR}/db_${STAMP}.sql" > "${BACKUP_DIR}/.last_backup"
                info "Backup salvo em ${BACKUP_DIR}/db_${STAMP}.sql"
            else
                warn "Falha ao gerar backup do banco — continuando mesmo assim, mas sem rede de segurança para o banco."
                rm -f "${BACKUP_DIR}/.last_backup"
            fi
            ;;
        sqlite*)
            log "Fazendo backup do SQLite..."
            local db_path="${db_url#sqlite:///}"
            db_path="/${db_path#/}"
            if [ -f "$db_path" ]; then
                cp "$db_path" "${BACKUP_DIR}/db_${STAMP}.sqlite3"
                echo "${BACKUP_DIR}/db_${STAMP}.sqlite3" > "${BACKUP_DIR}/.last_backup"
                info "Backup salvo em ${BACKUP_DIR}/db_${STAMP}.sqlite3"
            else
                warn "Arquivo SQLite não encontrado em ${db_path} — pulando backup."
                rm -f "${BACKUP_DIR}/.last_backup"
            fi
            ;;
        *)
            warn "Não reconheci o tipo de DATABASE_URL — pulando backup do banco."
            rm -f "${BACKUP_DIR}/.last_backup"
            ;;
    esac

    # mantém só os KEEP_BACKUPS mais recentes de cada tipo
    ls -1t "${BACKUP_DIR}"/db_*.sql 2>/dev/null      | tail -n +$((KEEP_BACKUPS + 1)) | xargs -r rm -f
    ls -1t "${BACKUP_DIR}"/db_*.sqlite3 2>/dev/null  | tail -n +$((KEEP_BACKUPS + 1)) | xargs -r rm -f
}

restore_database() {
    local last_backup_file="${BACKUP_DIR}/.last_backup"
    [ -f "$last_backup_file" ] || { warn "Nenhum backup registrado desta execução — banco não foi restaurado."; return; }
    local backup_path; backup_path="$(cat "$last_backup_file")"
    [ -f "$backup_path" ] || { warn "Arquivo de backup ${backup_path} não encontrado — banco não foi restaurado."; return; }

    local db_url; db_url="$(get_database_url)"
    case "$backup_path" in
        *.sql)
            log "Restaurando backup do PostgreSQL a partir de ${backup_path}..."
            run_as_app_user "psql '${db_url}' < '${backup_path}'" || warn "Falha ao restaurar o backup do PostgreSQL — verifique manualmente."
            ;;
        *.sqlite3)
            log "Restaurando backup do SQLite a partir de ${backup_path}..."
            local db_path="${db_url#sqlite:///}"
            db_path="/${db_path#/}"
            cp "$backup_path" "$db_path" || warn "Falha ao restaurar o backup do SQLite — verifique manualmente."
            ;;
    esac
}

health_check() {
    local tries=15
    for _ in $(seq 1 "$tries"); do
        if curl -fsS -m 3 "http://127.0.0.1:${APP_PORT}/healthz" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    return 1
}

rollback() {
    local previous_commit="$1"
    err "Algo deu errado durante a atualização — revertendo para o estado anterior."
    run_as_app_user "cd '${APP_DIR}' && git reset --hard '${previous_commit}'"
    run_as_app_user "cd '${APP_DIR}' && venv/bin/pip install --quiet -r requirements.txt"
    restore_database
    systemctl restart "$SERVICE_NAME"
    if health_check; then
        warn "Rollback concluído: a aplicação voltou a responder na versão anterior."
    else
        err "A aplicação não respondeu nem após o rollback. Verifique manualmente:"
        err "  journalctl -u ${SERVICE_NAME} -n 100 --no-pager"
    fi
    exit 1
}

# --------------------------------------------------------------------------

cd "$APP_DIR"

log "Verificando atualizações..."
run_as_app_user "cd '${APP_DIR}' && git fetch --quiet origin"

PREVIOUS_COMMIT="$(run_as_app_user "cd '${APP_DIR}' && git rev-parse HEAD")"
REMOTE_COMMIT="$(run_as_app_user "cd '${APP_DIR}' && git rev-parse '@{u}'" 2>/dev/null || true)"

if [ -z "$REMOTE_COMMIT" ]; then
    die "Não há um branch remoto (upstream) configurado para o branch atual. Configure com: git branch --set-upstream-to=origin/<branch>"
fi

if [ "$PREVIOUS_COMMIT" = "$REMOTE_COMMIT" ]; then
    log "Já está atualizado (${PREVIOUS_COMMIT:0:7}). Nada a fazer."
    exit 0
fi

info "Versão atual : ${PREVIOUS_COMMIT:0:7}"
info "Nova versão  : ${REMOTE_COMMIT:0:7}"

backup_database

log "Baixando a nova versão (fast-forward)..."
if ! run_as_app_user "cd '${APP_DIR}' && git merge --ff-only '@{u}'"; then
    die "Não foi possível avançar por fast-forward (há mudanças locais divergentes no servidor). Resolva manualmente antes de tentar de novo — nada foi alterado."
fi

log "Atualizando dependências Python..."
if ! run_as_app_user "cd '${APP_DIR}' && venv/bin/pip install --quiet -r requirements.txt"; then
    rollback "$PREVIOUS_COMMIT"
fi

log "Rodando migrations do banco de dados..."
if ! run_as_app_user "cd '${APP_DIR}' && venv/bin/flask db upgrade"; then
    rollback "$PREVIOUS_COMMIT"
fi

log "Reiniciando o serviço..."
systemctl restart "$SERVICE_NAME"

log "Verificando se a aplicação subiu corretamente..."
if ! health_check; then
    rollback "$PREVIOUS_COMMIT"
fi

log "Atualização concluída com sucesso (${PREVIOUS_COMMIT:0:7} → ${REMOTE_COMMIT:0:7})."
