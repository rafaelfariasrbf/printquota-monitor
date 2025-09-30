# Sistema de Cotas de Impressão com CUPS e MySQL

Este projeto implementa um **monitor de impressões para o CUPS**, integrado a um banco **MySQL/MariaDB**, com controle de cotas mensais, cancelamento automático de jobs excedentes e relatórios de uso.

---

## 📌 Funcionalidades

* Monitoramento contínuo de jobs no **CUPS**.
* Registro de todos os trabalhos de impressão em `print_jobs`.
* Controle de cotas mensais por impressora em `printer_monthly_usage`.
* Bloqueio automático da impressora ao atingir a cota:

  * Desabilita a fila no CUPS (`cupsdisable`).
  * Cancela todos os jobs pendentes (`cancel -a`).
* Reset automático das cotas no início de cada mês.
* Relatórios diários e semanais.
* Integração com **Active Directory + GPO** (para mapeamento das impressoras em Windows).
* Segurança: credenciais do banco em arquivo `.env` (não expostas no código).

---

## 📂 Estrutura do Projeto

```
/opt/cups_monitor_env/
├── cups_monitor.py          # Serviço principal de monitoramento
├── manage_quotas.py         # Utilitário de administração de cotas
├── quota_status.py          # Consulta status das impressoras
├── reset_monthly_quotas.py  # Reset automático das cotas
├── daily_quota_check.py     # Verificação diária
├── weekly_report.py         # Relatório semanal
├── .env                     # Configuração segura do banco
```

---

## ⚙️ Requisitos

* Debian 12+
* CUPS configurado
* MySQL/MariaDB
* Python 3.11+
* Pacotes Python:

  * `mysql-connector-python`
  * `python-dotenv`
  * `pycups`

---

## 🔑 Configuração

### 1. Banco de Dados

Crie um usuário dedicado e as tabelas necessárias:

```sql
CREATE USER 'cupsuser'@'localhost' IDENTIFIED BY 'SenhaFort3!';
GRANT ALL PRIVILEGES ON laravel_printing.* TO 'cupsuser'@'localhost';
FLUSH PRIVILEGES;
```

As tabelas principais:

* `print_jobs` – histórico de impressões.
* `printer_monthly_usage` – cotas e uso atual.
* `quota_alerts` – alertas de bloqueio.

### 2. Variáveis de Ambiente

Crie o arquivo `.env` em `/opt/cups_monitor_env/`:

```ini
MYSQL_HOST=localhost
MYSQL_USER=cupsuser
MYSQL_PASS=SenhaFort3!
MYSQL_DB=laravel_printing
```

Restrinja o acesso:

```bash
chmod 600 /opt/cups_monitor_env/.env
```

### 3. Ambiente Virtual

```bash
python3 -m venv /opt/cups_monitor_env
/opt/cups_monitor_env/bin/pip install --upgrade pip setuptools wheel
/opt/cups_monitor_env/bin/pip install mysql-connector-python pycups python-dotenv
```

---

## 🖥️ Serviço Systemd

Crie `/etc/systemd/system/cups-monitor.service`:

```ini
[Unit]
Description=CUPS monitor (grava páginas no MySQL e aplica cotas)
After=network.target cups.service

[Service]
Type=simple
ExecStart=/opt/cups_monitor_env/bin/python3 /opt/cups_monitor_env/cups_monitor.py
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target
```

Ative e inicie:

```bash
systemctl daemon-reload
systemctl enable cups-monitor.service
systemctl start cups-monitor.service
```

Verifique status:

```bash
systemctl status cups-monitor.service -l
```

---

## 📊 Relatórios

* `daily_quota_check.py` → resumo diário de uso.
* `weekly_report.py` → relatório semanal consolidado.
* `quota_status.py` → consulta status atual das impressoras.

---

## 🔒 Segurança

* Senhas não ficam no código-fonte → são lidas do `.env`.
* Apenas o usuário root tem permissão para ler o `.env`.
* Usuário dedicado do MySQL (`cupsuser`) com acesso limitado.

---

# 🛠️ Guia de Manutenção Rápida

## 🔎 Verificar status do serviço

```bash
systemctl status cups-monitor.service -l
journalctl -u cups-monitor.service -f
```

---

## 📜 Logs do sistema

```bash
tail -f /var/log/cups_monitor.log
```

---

## 🖨️ Gerenciar impressoras no CUPS

* Listar impressoras:

  ```bash
  lpstat -p
  ```
* Desabilitar manualmente:

  ```bash
  cupsdisable NOME_IMPRESSORA
  ```
* Reabilitar:

  ```bash
  cupsenable NOME_IMPRESSORA
  ```
* Cancelar todos os jobs:

  ```bash
  cancel -a NOME_IMPRESSORA
  ```

---

## 📊 Consultar cotas

Rodar script para checar status atual:

```bash
/opt/cups_monitor_env/bin/python3 /opt/cups_monitor_env/quota_status.py
```

Consultar diretamente no banco:

```sql
SELECT * FROM printer_monthly_usage;
```

---

## 🔄 Resetar cotas

Reset manual (além do agendamento mensal):

```bash
/opt/cups_monitor_env/bin/python3 /opt/cups_monitor_env/reset_monthly_quotas.py
```

---

## 🚨 Liberar impressora bloqueada antes do ciclo

1. No banco:

   ```sql
   UPDATE printer_monthly_usage
   SET current_count=0, remaining_pages=monthly_quota, usage_percentage=0, status='active'
   WHERE printer_name='NOME_IMPRESSORA';
   ```
2. Reabilitar no CUPS:

   ```bash
   cupsenable NOME_IMPRESSORA
   ```

---

## 📧 Relatórios

* Diário:

  ```bash
  /opt/cups_monitor_env/bin/python3 /opt/cups_monitor_env/daily_quota_check.py
  ```
* Semanal:

  ```bash
  /opt/cups_monitor_env/bin/python3 /opt/cups_monitor_env/weekly_report.py
  ```

---

## 📝 TODO

* [ ] Criar painel web para visualização de cotas e relatórios.
* [ ] Implementar envio automático de relatórios por e-mail.
* [ ] Adicionar testes unitários.

---

## 👨‍💻 Autor

Sistema desenvolvido e mantido por **Rafael**.
