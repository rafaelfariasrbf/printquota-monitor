#!/opt/cups_monitor_env/bin/python3
import cups
import mysql.connector
import logging
import time
import subprocess
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Carregar variáveis do .env
load_dotenv("/opt/cups_monitor_env/.env")

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASS = os.getenv("MYSQL_PASS")
MYSQL_DB   = os.getenv("MYSQL_DB")

CHECK_INTERVAL = 5
DAYS_TO_LOOK_BACK = 1
LOG_FILE = "/var/log/cups_monitor.log"

# Configurações de cotas
QUOTA_CHECK_ENABLED = True
QUOTA_WARNING_THRESHOLD = 0.9  # Alerta quando atingir 90% da cota
ADMIN_EMAIL = "rafaelrbf@fab.mil.br"

# ========== LOG ==========
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# ========== DB ==========
def get_db_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASS,
        database=MYSQL_DB,
        autocommit=False,
        buffered=True
    )

# ========== QUOTA MANAGEMENT ==========
def initialize_printers_from_cups():
    """Inicializa impressoras do CUPS no banco de dados se não existirem"""
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    try:
        cups_conn = cups.Connection()
        printers = cups_conn.getPrinters()
        
        for printer_name, attrs in printers.items():
            # Verifica se a impressora já existe no banco
            cursor.execute("SELECT id FROM printers WHERE name = %s", (printer_name,))
            if cursor.fetchone():
                continue
                
            # Extrai IP do DeviceURI
            device_uri = attrs.get('device-uri', '')
            ip_address = 'unknown'
            if 'socket://' in device_uri:
                ip_address = device_uri.replace('socket://', '').split(':')[0]
            
            # Insere nova impressora com cota padrão de 1000 páginas/mês
            cursor.execute("""
                INSERT INTO printers (name, ip_address, monthly_quota, current_count, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
            """, (printer_name, ip_address, 1000, 0))
            
            logging.info(f"Impressora {printer_name} adicionada ao sistema com cota mensal de 1000 páginas")
        
        db.commit()
        
    except Exception as e:
        logging.error(f"Erro ao inicializar impressoras: {e}")
        db.rollback()
    finally:
        cursor.close()
        db.close()

def get_printer_quota_info(cursor, printer_name):
    """Obtém informações de cota da impressora"""
    cursor.execute("""
        SELECT id, monthly_quota, current_count
        FROM printers 
        WHERE name = %s
    """, (printer_name,))
    return cursor.fetchone()

def update_printer_usage(cursor, db, printer_name, pages):
    """Atualiza o uso da impressora"""
    cursor.execute("""
        UPDATE printers 
        SET current_count = current_count + %s, updated_at = NOW()
        WHERE name = %s
    """, (pages, printer_name))
    db.commit()
    logging.info(f"Atualizado uso da impressora {printer_name}: +{pages} páginas")

def check_quota_exceeded(cursor, printer_name, pages_to_add=0):
    """Verifica se a cota será excedida"""
    quota_info = get_printer_quota_info(cursor, printer_name)
    if not quota_info:
        return False, "Impressora não encontrada no sistema"
    
    total_after_print = quota_info['current_count'] + pages_to_add
    
    if total_after_print > quota_info['monthly_quota']:
        return True, f"Cota excedida: {total_after_print}/{quota_info['monthly_quota']} páginas"
    
    # Verifica se está próximo do limite
    usage_percentage = total_after_print / quota_info['monthly_quota']
    if usage_percentage >= QUOTA_WARNING_THRESHOLD:
        logging.warning(f"ALERTA: Impressora {printer_name} em {usage_percentage:.1%} da cota mensal")
    
    return False, f"OK: {total_after_print}/{quota_info['monthly_quota']} páginas"

def reset_monthly_quotas():
    """Reseta as cotas mensais (executar via cron no início de cada mês)"""
    db = get_db_connection()
    cursor = db.cursor()
    
    try:
        cursor.execute("UPDATE printers SET current_count = 0, updated_at = NOW()")
        db.commit()
        logging.info("Cotas mensais resetadas para todas as impressoras")
        
        # Log das cotas resetadas
        cursor.execute("SELECT name, monthly_quota FROM printers")
        for row in cursor.fetchall():
            logging.info(f"Cota resetada: {row[0]} - {row[1]} páginas/mês")
            
    except Exception as e:
        logging.error(f"Erro ao resetar cotas: {e}")
        db.rollback()
    finally:
        cursor.close()
        db.close()

def block_printer_job(printer_name, reason):
    """Bloqueia trabalhos de impressão em uma impressora"""
    try:
        # Para a impressora no CUPS
        subprocess.run(['cupsdisable', printer_name], check=True)

        # Cancela todos os jobs pendentes
        subprocess.run(['cancel', '-a', printer_name], check=True)

        logging.warning(f"IMPRESSORA BLOQUEADA: {printer_name} - {reason}")
        
        # Opcional: Enviar notificação por email
        send_quota_notification(printer_name, reason)
        
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao bloquear/cancelar jobs da impressora {printer_name}: {e}")

def unblock_printer_job(printer_name):
    """Desbloqueia trabalhos de impressão"""
    try:
        subprocess.run(['cupsenable', printer_name], check=True)
        logging.info(f"Impressora desbloqueada: {printer_name}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao desbloquear impressora {printer_name}: {e}")

def send_quota_notification(printer_name, message):
    """Envia notificação de cota (implementar conforme necessidade)"""
    logging.info(f"NOTIFICAÇÃO COTA: {printer_name} - {message}")
    # Aqui você pode implementar envio de email, webhook, etc.

# ========== INTERCEPTAÇÃO PRÉ-IMPRESSÃO ==========
def check_job_before_printing(printer_name, pages):
    """Verifica cota antes de permitir a impressão"""
    if not QUOTA_CHECK_ENABLED:
        return True, "Controle de cota desabilitado"
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    try:
        exceeded, message = check_quota_exceeded(cursor, printer_name, pages)
        
        if exceeded:
            # Bloqueia a impressora
            block_printer_job(printer_name, message)
            return False, message
        
        return True, message
        
    except Exception as e:
        logging.error(f"Erro ao verificar cota: {e}")
        return True, "Erro na verificação - permitindo impressão"
    finally:
        cursor.close()
        db.close()

# ========== HELPERS ORIGINAIS ==========
def cups_to_printer_name(uri):
    if not uri:
        return 'UNKNOWN'
    return str(uri).rstrip('/').split('/')[-1]

def extract_pages(attrs):
    for key in ('job-media-sheets-completed', 'job-pages-completed', 'job-impressions-completed'):
        v = attrs.get(key)
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            v = v[0] if v else None
        try:
            return int(v)
        except:
            continue
    return 1

def insert_or_update_job(cursor, db, jid, printer, user, title, pages, completed_dt, attrs=None):
    """Versão modificada que também atualiza cotas, ignorando jobs cancelados"""
    state = attrs.get('job-state') if attrs else None

    # Estados do CUPS:
    # 3 = pending, 4 = held, 5 = processing, 6 = stopped, 
    # 7 = aborted, 8 = canceled, 9 = completed
    if state in (7, 8):  # aborted ou canceled
        logging.info(f"[IGNORADO] job_id={jid} (estado={state}) - não conta para cota")
        return

    cursor.execute("SELECT id, completed_at FROM print_jobs WHERE job_id = %s", (jid,))
    existing = cursor.fetchone()

    if existing and existing.get('completed_at') is not None:
        return  # já processado

    if existing:
        cursor.execute("""
            UPDATE print_jobs
            SET printer=%s, user=%s, title=%s, pages=%s, completed_at=%s, updated_at=NOW()
            WHERE job_id=%s
        """, (printer, user, title, pages, completed_dt, jid))
        logging.info("[UPDATE] job_id=%s pages=%s", jid, pages)
    else:
        cursor.execute("""
            INSERT INTO print_jobs (printer, user, job_id, title, pages, completed_at, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (printer, user, jid, title, pages, completed_dt))
        logging.info("[INSERT] job_id=%s pages=%s", jid, pages)

    db.commit()

    # Atualiza cotas apenas se o job foi concluído
    if state == 9 and pages and pages > 0:
        update_printer_usage(cursor, db, printer, pages)

def fetch_jobs_from_lpstat():
    """Versão original mantida"""
    try:
        output = subprocess.check_output(["lpstat", "-W", "completed", "-o"], text=True)
        jobs = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            job_full = parts[0]
            printer = "-".join(job_full.split("-")[:-1])
            jid = job_full.split("-")[-1]
            user = parts[1]
            title = ""
            pages = 1
            try:
                completed_str = " ".join(parts[3:])
                completed_dt = datetime.strptime(completed_str, "%a %d %b %Y %H:%M:%S")
            except Exception:
                completed_dt = datetime.now()
            jobs.append((jid, printer, user, title, pages, completed_dt))
        return jobs
    except subprocess.CalledProcessError:
        return []

# ========== RELATÓRIOS ==========
def generate_quota_report():
    """Gera relatório de uso das cotas"""
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT name, monthly_quota, current_count, 
                   ROUND((current_count / monthly_quota) * 100, 1) as usage_percent,
                   (monthly_quota - current_count) as remaining_pages
            FROM printers 
            ORDER BY usage_percent DESC
        """)
        
        print("\n" + "="*80)
        print("RELATÓRIO DE COTAS DE IMPRESSÃO")
        print("="*80)
        print(f"{'IMPRESSORA':<20} {'COTA':<8} {'USADO':<8} {'%':<8} {'RESTANTE':<10}")
        print("-"*80)
        
        for row in cursor.fetchall():
            print(f"{row['name']:<20} {row['monthly_quota']:<8} {row['current_count']:<8} "
                  f"{row['usage_percent']:<7}% {row['remaining_pages']:<10}")
        
        print("="*80)
        
    except Exception as e:
        logging.error(f"Erro ao gerar relatório: {e}")
    finally:
        cursor.close()
        db.close()

# ========== MAIN LOOP ==========
def main_loop():
    # Inicializa impressoras no banco
    initialize_printers_from_cups()
    
    cups_conn = cups.Connection()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cutoff = datetime.now() - timedelta(days=DAYS_TO_LOOK_BACK)
    logging.info("Monitor com controle de cotas iniciado")

    try:
        while True:
            try:
                # -------- TEMPO REAL --------
                jobs = cups_conn.getJobs(my_jobs=False, which_jobs='completed')
                for job_id, attrs in jobs.items():
                    t = attrs.get('time-at-completed')
                    if not t:
                        continue
                    completed_dt = datetime.fromtimestamp(int(t))
                    if completed_dt < cutoff:
                        continue

                    jid = str(job_id)
                    printer = cups_to_printer_name(attrs.get('job-printer-uri', ''))
                    user = attrs.get('job-originating-user-name') or 'UNKNOWN'
                    title = attrs.get('job-name', '')
                    pages = extract_pages(attrs)

                    insert_or_update_job(cursor, db, jid, printer, user, title, pages, completed_dt, attrs)

                # # -------- HISTÓRICO --------
                # hist_jobs = fetch_jobs_from_lpstat()
                # for jid, printer, user, title, pages, completed_dt in hist_jobs:
                #     if completed_dt < cutoff:
                #         continue
                #     insert_or_update_job(cursor, db, jid, printer, user, title, pages, completed_dt, attrs)

                # -------- VERIFICAÇÃO DE COTAS --------
                if QUOTA_CHECK_ENABLED:
                    cursor.execute("""
                        SELECT name, monthly_quota, current_count
                        FROM printers 
                        WHERE current_count >= monthly_quota
                    """)
                    
                    blocked_printers = cursor.fetchall()
                    for printer_info in blocked_printers:
                        printer_name = printer_info['name']
                        message = f"Cota esgotada: {printer_info['current_count']}/{printer_info['monthly_quota']}"
                        block_printer_job(printer_name, message)

                time.sleep(CHECK_INTERVAL)

            except Exception as e:
                logging.exception("Erro no loop principal: %s", e)
                try:
                    db.rollback()
                except:
                    pass
                time.sleep(CHECK_INTERVAL)

    finally:
        try:
            cursor.close()
            db.close()
        except:
            pass

# ========== UTILITÁRIOS CLI ==========
def main():
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "report":
            generate_quota_report()
        elif command == "reset":
            reset_monthly_quotas()
        elif command == "init":
            initialize_printers_from_cups()
            print("Impressoras inicializadas no sistema")
        else:
            print("Comandos disponíveis:")
            print("  python3 script.py report  - Relatório de cotas")
            print("  python3 script.py reset   - Reset cotas mensais")
            print("  python3 script.py init    - Inicializar impressoras")
    else:
        main_loop()

if __name__ == "__main__":
    main()
