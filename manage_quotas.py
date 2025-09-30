#!/opt/cups_monitor_env/bin/python3
import mysql.connector
import sys
import subprocess
from dotenv import load_dotenv
import os

# Carregar variáveis do .env
load_dotenv("/opt/cups_monitor_env/.env")

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASS = os.getenv("MYSQL_PASS")
MYSQL_DB   = os.getenv("MYSQL_DB")

def manage_quotas():
    """Script de gerenciamento de cotas"""
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python3 manage_quotas.py status                    - Status atual")
        print("  python3 manage_quotas.py set IMPRESSORA COTA       - Define cota")
        print("  python3 manage_quotas.py reset IMPRESSORA          - Reset contador")
        print("  python3 manage_quotas.py enable IMPRESSORA         - Habilita impressora")
        print("  python3 manage_quotas.py disable IMPRESSORA        - Bloqueia impressora")
        print("  python3 manage_quotas.py report                    - Relatório detalhado")
        return
    
    command = sys.argv[1]
    
    try:
        db = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASS,
            database=MYSQL_DB
        )
        cursor = db.cursor(dictionary=True)
        
        if command == "status":
            # Importar e executar status
            import os
            os.system('/opt/cups_monitor_env/quota_status.py')
            
        elif command == "set" and len(sys.argv) == 4:
            printer = sys.argv[2]
            quota = int(sys.argv[3])
            cursor.execute("UPDATE printers SET monthly_quota = %s WHERE name = %s", (quota, printer))
            db.commit()
            print(f"Cota da {printer} ajustada para {quota} páginas/mês")
            
        elif command == "reset" and len(sys.argv) == 3:
            printer = sys.argv[2]
            cursor.execute("UPDATE printers SET current_count = 0 WHERE name = %s", (printer,))
            db.commit()
            print(f"Contador da {printer} resetado")
            
        elif command == "enable" and len(sys.argv) == 3:
            printer = sys.argv[2]
            subprocess.run(['cupsenable', printer], check=True)
            print(f"Impressora {printer} habilitada")
            
        elif command == "disable" and len(sys.argv) == 3:
            printer = sys.argv[2]
            subprocess.run(['cupsdisable', printer], check=True)
            print(f"Impressora {printer} desabilitada")
            
        elif command == "report":
            import os
            os.system('/opt/cups_monitor_env/weekly_report.py')
            
        else:
            print("Comando inválido")
            
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        try:
            cursor.close()
            db.close()
        except:
            pass

if __name__ == "__main__":
    manage_quotas()
