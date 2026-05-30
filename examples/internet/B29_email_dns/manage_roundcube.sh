#!/bin/bash
#
# Roundcube Webmail 管理脚本
# 用于 SEED 邮件系统 (29-email-system)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose-roundcube.yml"
SEED_B29_PROJECT_NAME="${SEED_B29_PROJECT_NAME:-b29}"
SEED_B29_ROUNDCUBE_PROJECT_NAME="${SEED_B29_ROUNDCUBE_PROJECT_NAME:-b29_roundcube}"
# Roundcube is a sidecar compose project. Do not inherit the main B29
# COMPOSE_PROJECT_NAME, otherwise stop/down may target the wrong project.
COMPOSE_PROJECT_NAME="$SEED_B29_ROUNDCUBE_PROJECT_NAME"
SEED_B29_NETWORK_PREFIX="${SEED_B29_NETWORK_PREFIX:-${SEED_B29_PROJECT_NAME:-b29}}"
export COMPOSE_PROJECT_NAME
export SEED_B29_NETWORK_PREFIX

compose() {
    if docker compose version >/dev/null 2>&1; then
        docker compose "$@"
    elif command -v docker-compose >/dev/null 2>&1; then
        docker-compose "$@"
    else
        print_error "docker compose/docker-compose not installed"
        return 1
    fi
}

main_compose() {
    local previous_project="${COMPOSE_PROJECT_NAME:-}"
    COMPOSE_PROJECT_NAME="$SEED_B29_PROJECT_NAME" compose "$@"
    local rc=$?
    COMPOSE_PROJECT_NAME="$previous_project"
    export COMPOSE_PROJECT_NAME
    return "$rc"
}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Colored printing helpers
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check mail servers running
check_mail_servers() {
    print_info "Checking mail servers state..."
    
    cd "$SCRIPT_DIR/output" 2>/dev/null || {
        print_error "output directory not found. Run email_realistic.py to generate first"
        return 1
    }
    
    MAIL_SERVERS=$(main_compose ps 2>/dev/null | grep -E "^mail-" | grep -E "Up|running" | wc -l)
    
    if [ "$MAIL_SERVERS" -eq 6 ]; then
        print_success "All 6 mail servers are running"
        return 0
    else
        print_warning "Only $MAIL_SERVERS mail servers are running (expected 6)"
        print_info "Starting mail servers..."
        main_compose up -d
        sleep 10
        return 0
    fi
}

# Start Roundcube
start_roundcube() {
    print_info "Starting Roundcube Webmail..."
    
    # 检查邮件服务器
    check_mail_servers || return 1
    
    # 启动Roundcube
    cd "$SCRIPT_DIR"
    compose -f "$COMPOSE_FILE" up -d
    
    if [ $? -eq 0 ]; then
        print_success "Roundcube Webmail started"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  📬 Roundcube Webmail: http://localhost:8082"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Test accounts:"
        echo "  • user@qq.com (password: password123)"
        echo "  • user@gmail.com (password: password123)"
        echo "  • user@163.com (password: password123)"
        echo ""
        echo "Supported providers:"
        echo "  • qq.com (QQ Mail)"
        echo "  • 163.com (NetEase)"
        echo "  • gmail.com (Gmail)"
        echo "  • outlook.com (Outlook)"
        echo "  • company.cn (Company)"
        echo "  • startup.net (Startup)"
        echo ""
    else
        print_error "Failed to start Roundcube"
        return 1
    fi
}

# Stop Roundcube
stop_roundcube() {
    print_info "Stopping Roundcube Webmail..."
    cd "$SCRIPT_DIR"
    compose -f "$COMPOSE_FILE" down
    
    if [ $? -eq 0 ]; then
        print_success "Roundcube Webmail stopped"
    else
        print_error "Stop failed"
        return 1
    fi
}

# Restart Roundcube
restart_roundcube() {
    print_info "Restarting Roundcube Webmail..."
    stop_roundcube
    sleep 2
    start_roundcube
}

# Status
status_roundcube() {
    print_info "Roundcube service status:"
    echo ""
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(roundcube|NAME)"
    echo ""
    
    # 检查服务是否可访问
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8082 | grep -q "200\|302"; then
        print_success "Roundcube is reachable at http://localhost:8082"
    else
        print_warning "Roundcube web is not reachable"
    fi
}

# Logs
logs_roundcube() {
    print_info "Roundcube logs (Ctrl+C to exit):"
    docker logs -f roundcube-webmail-b29
}

# Create test accounts (6 providers)
create_test_accounts() {
    print_info "Creating test mail accounts..."
    
    # QQ邮箱
    printf "password123\npassword123\n" | docker exec -i mail-qq-tencent setup email add user@qq.com 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Created user@qq.com"
    else
        print_warning "user@qq.com may already exist"
    fi
    
    # 163邮箱
    printf "password123\npassword123\n" | docker exec -i mail-163-netease setup email add user@163.com 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Created user@163.com"
    else
        print_warning "user@163.com may already exist"
    fi
    
    # Gmail
    printf "password123\npassword123\n" | docker exec -i mail-gmail-google setup email add user@gmail.com 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Created user@gmail.com"
    else
        print_warning "user@gmail.com may already exist"
    fi
    
    # Outlook
    printf "password123\npassword123\n" | docker exec -i mail-outlook-microsoft setup email add user@outlook.com 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Created user@outlook.com"
    else
        print_warning "user@outlook.com may already exist"
    fi
    
    # 企业邮箱
    printf "password123\npassword123\n" | docker exec -i mail-company-aliyun setup email add admin@company.cn 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Created admin@company.cn"
    else
        print_warning "admin@company.cn may already exist"
    fi
    
    # 自建邮箱
    printf "password123\npassword123\n" | docker exec -i mail-startup-selfhosted setup email add founder@startup.net 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Created founder@startup.net"
    else
        print_warning "founder@startup.net may already exist"
    fi
    
    echo ""
    print_success "Test accounts ready. You can log in with these accounts in Roundcube."
    echo ""
    echo "Test account list:"
    echo "  • user@qq.com / password123"
    echo "  • user@163.com / password123"
    echo "  • user@gmail.com / password123"
    echo "  • user@outlook.com / password123"
    echo "  • admin@company.cn / password123"
    echo "  • founder@startup.net / password123"
}

# Help
show_help() {
    echo ""
    echo "Roundcube Webmail Management"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  start       - Start Roundcube Webmail"
    echo "  stop        - Stop Roundcube Webmail"
    echo "  restart     - Restart Roundcube Webmail"
    echo "  status      - Show status"
    echo "  logs        - Tail logs"
    echo "  accounts    - Create test mail accounts"
    echo "  help        - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 start     # Start Roundcube"
    echo "  $0 status    # Show status"
    echo "  $0 accounts  # Create test accounts"
    echo ""
}

# 主程序
main() {
    case "$1" in
        start)
            start_roundcube
            ;;
        stop)
            stop_roundcube
            ;;
        restart)
            restart_roundcube
            ;;
        status)
            status_roundcube
            ;;
        logs)
            logs_roundcube
            ;;
        accounts)
            create_test_accounts
            ;;
        help|--help|-h|"")
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
