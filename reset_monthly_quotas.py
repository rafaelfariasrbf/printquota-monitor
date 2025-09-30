#!/opt/cups_monitor_env/bin/python3
import mysql.connector
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

# Log
logging.basicConfig(
    filename="/var/log/quota_reset.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def reset_monthly_quotas():
    """Reset das cotas mensais com log completo"""
    try:
        db = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASS,
            database=MYSQL_DB
        )
        cursor = db.cursor(dictionary=True)
        
        # Registra uso antes do reset
        cursor.execute("SELECT name, current_count, monthly_quota FROM printers")
        printers = cursor.fetchall()
        
        logging.info("=== INÍCIO RESET MENSAL ===")
        for printer in printers:
            logging.info(f"ANTES: {printer['name']} - {printer['current_count']}/{printer['monthly_quota']} páginas")
        
        # Registra alertas de reset
        cursor.execute("""
            INSERT INTO quota_alerts (printer_name, alert_type, current_usage, quota_limit, message)
            SELECT name, 'QUOTA_RESET', current_count, monthly_quota, 
                   CONCAT('Reset mensal automático - Uso anterior: ', current_count, ' páginas')
            FROM printers
        """)
        
        # Reset dos contadores
        cursor.execute("UPDATE printers SET current_count = 0, updated_at = NOW()")
        db.commit()
        
        logging.info("Cotas mensais resetadas com sucesso")
        logging.info("=== FIM RESET MENSAL ===")
        
        # Habilita impressoras que podem ter sido bloqueadas
        import subprocess
        for printer in printers:
            try:
                subprocess.run(['cupsenable', printer['name']], check=True)
                logging.info(f"Impressora {printer['name']} habilitada")
            except:
                pass
        
    except Exception as e:
        logging.error(f"ERRO no reset mensal: {e}")
    finally:
        try:
            cursor.close()
            db.close()
        except:
            pass

if __name__ == "__main__":
    reset_monthly_quotas()
