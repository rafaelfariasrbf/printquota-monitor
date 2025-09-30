#!/opt/cups_monitor_env/bin/python3
import mysql.connector
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

def show_quota_status():
    """Mostra status atual das cotas"""
    try:
        db = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASS,
            database=MYSQL_DB
        )
        cursor = db.cursor(dictionary=True)
        
        print("\n" + "="*80)
        print("SISTEMA DE COTAS DE IMPRESSÃO - STATUS ATUAL")
        print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("="*80)
        
        # Status das impressoras
        cursor.execute("""
            SELECT name, monthly_quota, current_count,
                   ROUND((current_count / monthly_quota) * 100, 1) as usage_percent,
                   (monthly_quota - current_count) as remaining_pages
            FROM printers 
            ORDER BY usage_percent DESC
        """)
        
        print(f"{'IMPRESSORA':<20} {'COTA':<6} {'USADO':<6} {'%':<7} {'RESTANTE':<9} {'STATUS'}")
        print("-"*80)
        
        for row in cursor.fetchall():
            status = "OK"
            if row['usage_percent'] >= 100:
                status = "BLOQUEADA"
            elif row['usage_percent'] >= 90:
                status = "ALERTA"
            elif row['usage_percent'] >= 70:
                status = "ATENÇÃO"
            
            print(f"{row['name']:<20} {row['monthly_quota']:<6} {row['current_count']:<6} "
                  f"{row['usage_percent']:>6.1f} {row['remaining_pages']:<9} {status}")
        
        # Últimos alertas
        cursor.execute("""
            SELECT printer_name, alert_type, current_usage, quota_limit, created_at
            FROM quota_alerts 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        alerts = cursor.fetchall()
        if alerts:
            print("\nÚLTIMOS ALERTAS (7 dias):")
            print("-"*80)
            for alert in alerts:
                print(f"{alert['created_at'].strftime('%d/%m %H:%M')} - "
                      f"{alert['printer_name']} - {alert['alert_type']} - "
                      f"{alert['current_usage']}/{alert['quota_limit']}")
        
        # Status do CUPS
        print("\nSTATUS DAS IMPRESSORAS NO CUPS:")
        print("-"*80)
        try:
            result = subprocess.run(['lpstat', '-p'], capture_output=True, text=True)
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if 'printer' in line.lower():
                        print(line)
        except:
            print("Erro ao consultar status do CUPS")
        
        print("="*80)
        
    except Exception as e:
        print(f"Erro ao consultar status: {e}")
    finally:
        try:
            cursor.close()
            db.close()
        except:
            pass

if __name__ == "__main__":
    show_quota_status()
