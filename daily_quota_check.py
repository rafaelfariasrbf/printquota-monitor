#!/opt/cups_monitor_env/bin/python3
import mysql.connector
import subprocess
import logging
from datetime import datetime
from dotenv import load_dotenv
import os

# Carregar variáveis do .env
load_dotenv("/opt/cups_monitor_env/.env")

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASS = os.getenv("MYSQL_PASS")
MYSQL_DB   = os.getenv("MYSQL_DB")

logging.basicConfig(
    filename="/var/log/daily_quota.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def daily_quota_check():
    """Verificação diária das cotas"""
    try:
        db = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASS,
            database=MYSQL_DB
        )
        cursor = db.cursor(dictionary=True)
        
        # Verificar impressoras com cota excedida
        cursor.execute("""
            SELECT name, current_count, monthly_quota
            FROM printers 
            WHERE current_count >= monthly_quota
        """)
        
        blocked_printers = cursor.fetchall()
        for printer in blocked_printers:
            try:
                # Bloquear impressora
                subprocess.run(['cupsdisable', printer['name']], check=True)
                logging.warning(f"Impressora {printer['name']} bloqueada - Cota esgotada: {printer['current_count']}/{printer['monthly_quota']}")
                
                # Registrar alerta
                cursor.execute("""
                    INSERT INTO quota_alerts (printer_name, alert_type, current_usage, quota_limit, message)
                    VALUES (%s, 'QUOTA_EXCEEDED', %s, %s, %s)
                """, (printer['name'], printer['current_count'], printer['monthly_quota'], 
                     f"Verificação diária - Cota esgotada"))
                
            except Exception as e:
                logging.error(f"Erro ao bloquear {printer['name']}: {e}")
        
        # Verificar impressoras próximas ao limite (90%)
        cursor.execute("""
            SELECT name, current_count, monthly_quota,
                   ROUND((current_count / monthly_quota) * 100, 1) as usage_percent
            FROM printers 
            WHERE (current_count / monthly_quota) >= 0.9 
            AND current_count < monthly_quota
        """)
        
        warning_printers = cursor.fetchall()
        for printer in warning_printers:
            logging.warning(f"ALERTA: {printer['name']} em {printer['usage_percent']}% da cota ({printer['current_count']}/{printer['monthly_quota']})")
            
            # Registrar alerta apenas uma vez por dia
            cursor.execute("""
                SELECT id FROM quota_alerts 
                WHERE printer_name = %s 
                AND alert_type = 'WARNING' 
                AND DATE(created_at) = CURDATE()
            """, (printer['name'],))
            
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO quota_alerts (printer_name, alert_type, current_usage, quota_limit, message)
                    VALUES (%s, 'WARNING', %s, %s, %s)
                """, (printer['name'], printer['current_count'], printer['monthly_quota'], 
                     f"Uso em {printer['usage_percent']}% da cota mensal"))
        
        db.commit()
        logging.info(f"Verificação concluída - {len(blocked_printers)} bloqueadas, {len(warning_printers)} em alerta")
        
    except Exception as e:
        logging.error(f"Erro na verificação diária: {e}")
    finally:
        try:
            cursor.close()
            db.close()
        except:
            pass

if __name__ == "__main__":
    daily_quota_check()
