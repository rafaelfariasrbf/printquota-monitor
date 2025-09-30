#!/opt/cups_monitor_env/bin/python3
import mysql.connector
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
import os

# Carregar variáveis do .env
load_dotenv("/opt/cups_monitor_env/.env")

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASS = os.getenv("MYSQL_PASS")
MYSQL_DB   = os.getenv("MYSQL_DB")
ADMIN_EMAIL = "admin@fab.mil.br"  # ALTERE AQUI

def generate_weekly_report():
    """Gera relatório semanal de uso"""
    try:
        db = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASS,
            database=MYSQL_DB
        )
        cursor = db.cursor(dictionary=True)
        
        # Relatório de cotas
        cursor.execute("""
            SELECT name, monthly_quota, current_count,
                   ROUND((current_count / monthly_quota) * 100, 1) as usage_percent,
                   (monthly_quota - current_count) as remaining_pages
            FROM printers 
            ORDER BY usage_percent DESC
        """)
        
        report = []
        report.append("RELATÓRIO SEMANAL DE IMPRESSÃO")
        report.append("=" * 50)
        report.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        report.append("")
        report.append("COTAS POR IMPRESSORA:")
        report.append("-" * 50)
        
        alert_printers = []
        for row in cursor.fetchall():
            status = "OK"
            if row['usage_percent'] >= 100:
                status = "QUOTA ESGOTADA!"
                alert_printers.append(row['name'])
            elif row['usage_percent'] >= 90:
                status = "ALERTA (>90%)"
                alert_printers.append(row['name'])
            elif row['usage_percent'] >= 70:
                status = "ATENÇÃO (>70%)"
            
            report.append(f"{row['name']:<20} {row['current_count']:>4}/{row['monthly_quota']:<4} "
                         f"({row['usage_percent']:>5.1f}%) - {status}")
        
        # Top usuários da semana
        cursor.execute("""
            SELECT user, COUNT(*) as jobs, SUM(COALESCE(pages,1)) as pages
            FROM print_jobs 
            WHERE completed_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY user 
            ORDER BY pages DESC 
            LIMIT 10
        """)
        
        report.append("")
        report.append("TOP 10 USUÁRIOS DA SEMANA:")
        report.append("-" * 50)
        for row in cursor.fetchall():
            report.append(f"{row['user']:<25} {row['jobs']:>3} jobs, {row['pages']:>4} páginas")
        
        report_text = "\n".join(report)
        print(report_text)
        
        # Salvar em arquivo
        with open("/var/log/weekly_report.txt", "w") as f:
            f.write(report_text)
        
        return report_text, alert_printers
        
    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")
        return "", []
    finally:
        try:
            cursor.close()
            db.close()
        except:
            pass

if __name__ == "__main__":
    generate_weekly_report()
