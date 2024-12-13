#!/bin/bash

# ==============================================================================
# change_vpn_server.sh
# Script per riconnettere automaticamente OpenVPN e verificare il cambiamento dell'IP.
# ==============================================================================

# Configurazione
SCRIPT_DIR="$(dirname "$0")"
CONFIG_DIR="$SCRIPT_DIR/vpn_configs"
CONFIG_FILE="$CONFIG_DIR/it.protonvpn.udp.ovpn"
AUTH_FILE="$SCRIPT_DIR/auth.txt"
CHECK_INTERVAL=1800    # Intervallo in secondi : 30 minuti
RECHECK_DELAY=15      # Attesa in secondi prima di verificare il nuovo IP
LOG_FILE="$SCRIPT_DIR/vpn_reconnect.log"
TEMP_LOG="$SCRIPT_DIR/openvpn_temp.log"
MAX_RECONNECT_ATTEMPTS=3  # Numero massimo di tentativi di riconnessione

# Funzione per loggare i messaggi usando logger e scrivere nel file di log
log() {
    local MESSAGE="$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') : $MESSAGE" | tee -a "$LOG_FILE"
    logger -t VPN_Reconnect "$MESSAGE"
}

# Funzione per ottenere l'indirizzo IP attuale (solo IPv4)
get_current_ip() {
    curl -4 -s --max-time 10 ifconfig.me
}

# Funzione per terminare OpenVPN
terminate_openvpn() {
    log "Terminazione dei processi OpenVPN esistenti..."
    killall openvpn 2>/dev/null
    sleep 5
    if pgrep openvpn > /dev/null; then
        log "Errore: Non è stato possibile terminare tutti i processi OpenVPN."
        return 1
    fi
    log "Processi OpenVPN terminati con successo."
    return 0
}

# Funzione per riconnettersi a OpenVPN con il file .ovpn specificato
reconnect_vpn() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log "Errore: File di configurazione $CONFIG_FILE non trovato."
        return 1
    fi

    for ((i=1;i<=MAX_RECONNECT_ATTEMPTS;i++)); do
        log "Tentativo di riconnessione a OpenVPN (Tentativo $i)..."
        openvpn --config "$CONFIG_FILE" --auth-user-pass "$AUTH_FILE" --daemon --log "$TEMP_LOG"

        sleep 10  # Attendi per consentire la connessione

        if grep -q "Initialization Sequence Completed" "$TEMP_LOG"; then
            log "OpenVPN connesso con successo al server selezionato."
            rm -f "$TEMP_LOG"
            return 0
        else
            log "Errore: OpenVPN non si è connesso correttamente al server selezionato."
            killall openvpn 2>/dev/null
            rm -f "$TEMP_LOG"
            sleep 5
        fi
    done
    log "Errore: Riconnessione a OpenVPN fallita dopo $MAX_RECONNECT_ATTEMPTS tentativi."
    return 1
}

# Funzione per gestire la riconnessione e il controllo dell'IP
handle_vpn_reconnect() {
    terminate_openvpn || return 1
    reconnect_vpn || return 1

    log "Attesa di $RECHECK_DELAY secondi prima di verificare il nuovo IP..."
    sleep "$RECHECK_DELAY"

    new_ip=$(get_current_ip)
    if [[ -z "$new_ip" ]]; then
        log "Errore: Impossibile ottenere il nuovo IP dopo la riconnessione."
        return 1
    fi

    log "Nuovo IP: $new_ip"
    return 0
}

# Funzione di pulizia al termine dello script
cleanup() {
    log "Interruzione dello script richiesta. Terminazione di OpenVPN..."
    terminate_openvpn
    log "Script terminato."
    exit 0
}

# Imposta il trap per catturare CTRL+C e altre interruzioni
trap cleanup SIGINT SIGTERM

# Verifica la presenza dei file di configurazione
if [[ ! -d "$CONFIG_DIR" ]]; then
    log "Errore: Directory di configurazione $CONFIG_DIR non trovata."
    exit 1
fi

if [[ ! -f "$AUTH_FILE" ]]; then
    log "Errore: File delle credenziali $AUTH_FILE non trovato."
    exit 1
fi

# Verifica che i comandi necessari siano disponibili
for cmd in openvpn curl killall pgrep grep logger; do
    if ! command -v "$cmd" &> /dev/null; then
        log "Errore: Il comando '$cmd' non è installato."
        exit 1
    fi
done

# Ottieni l'IP corrente prima di iniziare (solo IPv4)
old_ip=$(get_current_ip)
if [[ -z "$old_ip" ]]; then
    log "Errore: Impossibile ottenere l'IP corrente. Uscita."
    exit 1
fi
log "IP corrente: $old_ip"

# Ciclo infinito per la riconnessione periodica
while true; do
    log "Inizio processo di riconnessione e verifica dell'IP."

    if handle_vpn_reconnect; then
        new_ip=$(get_current_ip)
        if [[ -z "$new_ip" ]]; then
            log "Errore: Impossibile ottenere il nuovo IP."
        else
            log "Nuovo IP ottenuto: $new_ip"

            if [[ "$old_ip" != "$new_ip" ]]; then
                log "Successo: L'IP è cambiato da $old_ip a $new_ip."
                old_ip="$new_ip"  # Aggiorna l'IP di riferimento
            else
                log "Avviso: L'IP non è cambiato dopo la riconnessione."
            fi
        fi
    else
        log "Errore: Il processo di riconnessione non è riuscito."
    fi

    log "Attesa di $CHECK_INTERVAL secondi prima del prossimo tentativo."
    sleep "$CHECK_INTERVAL"
done
