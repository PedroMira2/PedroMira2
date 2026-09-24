import os
import sys
import time
import json
import random
import datetime
import threading
import subprocess
import webbrowser
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

# Força UTF-8 no console Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Detecção robusta do diretório real da aplicação (compatível com PyInstaller .exe)
if getattr(sys, 'frozen', False):
    REPO_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    REPO_DIR = os.path.dirname(os.path.abspath(__file__))

DOCS_DIR = os.path.join(REPO_DIR, "docs")
KB_DIR = os.path.join(DOCS_DIR, "knowledge-base")
LOG_FILE = os.path.join(DOCS_DIR, "activity-log.md")
ENV_FILE = os.path.join(REPO_DIR, ".env")
CONFIG_FILE = os.path.join(REPO_DIR, "config.json")

PORT = 5050

DEFAULT_CONFIG = {
    "api_key": "",
    "model": "gemini-3.5-flash-lite",
    "start_hour": 9,
    "end_hour": 22,
    "min_interval": 75,
    "max_interval": 210,
    "git_branch": "main"
}

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            cfg["api_key"] = val
        except Exception:
            pass
    return cfg

def save_config(new_cfg):
    cfg = load_config()
    cfg.update(new_cfg)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        add_log("ERRO", f"Erro ao salvar config.json: {e}")

    if "api_key" in new_cfg and new_cfg["api_key"]:
        try:
            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write(f"GEMINI_API_KEY={new_cfg['api_key'].strip()}\n")
        except Exception as e:
            add_log("ERRO", f"Erro ao salvar .env: {e}")
    return cfg

# Estado global da automação
STATE = {
    "is_running": True,
    "is_paused": False,
    "status_message": "🟢 Sistema Online e Monitorando",
    "last_run": None,
    "next_run_timestamp": 0,
    "commits_today": 0,
    "total_generated": 0,
    "last_commit_sha": "---",
    "last_commit_msg": "Nenhum commit recente",
    "last_topic": "---",
    "active_model": "gemini-3.5-flash-lite",
    "logs": []
}

def add_log(tag, message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    entry = {"time": timestamp, "tag": tag, "message": message}
    STATE["logs"].append(entry)
    if len(STATE["logs"]) > 120:
        STATE["logs"].pop(0)
    print(f"[{timestamp}] [{tag}] {message}")

DOMAINS = [
    "AppSec & OWASP Top 10 (SQLi, XSS, SSRF, CSRF, IDOR, Broken Authentication, Deserialização Insegura)",
    "Hardening de Servidores Linux (Auditoria com Lynis, Chaves SSH, UFW/iptables, Permissões SUID, PAM)",
    "Redes & Protocolos (Análise de Tráfego Wireshark, TCP/IP, DNSSEC, TLS 1.3, Scan com Nmap)",
    "Automação e Scripting de Segurança em Python (Scanners modulares, Requests, BeautifulSoup, Sockets)",
    "Pentesting & Metodologias Ofensivas (Burp Suite, OWASP ZAP, Metasploit, SQLmap, Relatórios Técnicos)",
    "Arquitetura Web Segura & Servidores (Apache/Nginx Hardening, CSP, HSTS, CORS, WAF e ModSecurity)"
]

FALLBACK_TEMPLATES = [
    {
        "category": "AppSec",
        "filename": "sql-injection-mitigation.md",
        "commit_message": "docs(appsec): detalhar prepared statements parametrizados",
        "title": "Prevenção Técnica Contra Injeção SQL com Prepared Statements",
        "content": "A injeção de SQL (SQLi) é neutralizada através da separação estrita entre dados e lógica de comandos. Ao utilizar prepared statements com parâmetros tipados, o motor do SGBD compila a consulta previamente, impossibilitando que dados de entrada alterem a árvore sintática da query.\n\n```python\n# Exemplo de consulta segura parametrizada em Python\nimport sqlite3\nconn = sqlite3.connect('app.db')\ncursor = conn.cursor()\ncursor.execute('SELECT id, email FROM users WHERE username = ?', (user_input,))\n```"
    },
    {
        "category": "Hardening",
        "filename": "ssh-defense-guide.md",
        "commit_message": "docs(hardening): implementar chaves ED25519 e desabilitar root",
        "title": "Checklist de Hardening em Acessos SSH",
        "content": "Para blindar servidores contra ataques de dicionário e força bruta, o serviço SSH deve ser restringido para autenticação exclusiva via chaves assimétricas ED25519, desabilitando logins diretos do usuário root e limitando tentativas simultâneas.\n\n```bash\n# /etc/ssh/sshd_config\nPermitRootLogin no\nPasswordAuthentication no\nPubkeyAuthentication yes\nMaxAuthTries 3\n```"
    }
]

def generate_with_gemini():
    cfg = load_config()
    api_key = cfg.get("api_key", "").strip()
    if not api_key:
        add_log("ERRO", "Chave da API do Gemini não configurada! Abra o menu de Configurações.")
        return random.choice(FALLBACK_TEMPLATES)

    domain = random.choice(DOMAINS)
    add_log("GEMINI", f"Sorteando domínio: {domain.split('(')[0].strip()}...")
    
    prompt = f"""
Você é um Engenheiro Sênior de Cibersegurança e Segurança de Aplicações (AppSec).
Gere uma nota de documentação técnica INÉDITA, densa, prática e de alto nível sobre o seguinte domínio: {domain}.

Retorne ESTRITAMENTE um JSON com as seguintes chaves:
{{
  "category": "AppSec | Hardening | Redes | Automação | Pentest | Servidores",
  "filename": "nome_do_arquivo.md (ex: ssrf-mitigation.md, ssh-hardening.md, nmap-workflows.md, python-port-scanner.md)",
  "commit_message": "mensagem curta no padrao conventional commits em portugues (ex: docs(appsec): implementar controle estrito contra SSRF)",
  "title": "Título técnico específico e profissional",
  "content": "Texto técnico explicativo completo (2 a 3 parágrafos densos e aprofundados) acompanhado de um bloco de código prático em Python, Bash ou configuração Nginx/Apache demonstrando a aplicação do conceito."
}}
"""
    selected_model = cfg.get("model", "gemini-3.5-flash-lite")
    models_to_try = [selected_model]
    if "gemini-3.5-flash-lite" not in models_to_try:
        models_to_try.append("gemini-3.5-flash-lite")
    if "gemini-3.1-flash-lite" not in models_to_try:
        models_to_try.append("gemini-3.1-flash-lite")

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}
        }
        try:
            r = requests.post(url, json=payload, timeout=25)
            if r.status_code == 200:
                raw_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(raw_text)
                STATE["active_model"] = model
                add_log("GEMINI", f"Conteúdo gerado com sucesso via {model}: \"{data.get('title')}\"")
                return data
            else:
                add_log("AVISO", f"Modelo {model} retornou status {r.status_code}. Tentando modelo reserva...")
        except Exception as e:
            add_log("AVISO", f"Falha de conexão com {model}: {e}")

    add_log("INFO", "Usando template de contingência offline.")
    return random.choice(FALLBACK_TEMPLATES)

def execute_commit_cycle(is_manual=False):
    """Executa o ciclo completo de IA, salvamento de arquivo, commit e push."""
    STATE["status_message"] = "🤖 Gerando conteúdo com Gemini AI..."
    add_log("CICLO", f"Iniciando ciclo de atividade {'(Manual)' if is_manual else '(Automático)'}...")

    entry = generate_with_gemini()
    STATE["last_topic"] = entry.get("title", "Tópico Técnico")
    
    os.makedirs(KB_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    filename = entry.get("filename", "security-note.md")
    if not filename.endswith(".md"):
        filename += ".md"
    file_path = os.path.join(KB_DIR, filename)

    now = datetime.datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

    file_mode = "a" if os.path.exists(file_path) else "w"
    with open(file_path, file_mode, encoding="utf-8") as f:
        if file_mode == "w":
            f.write(f"# {entry.get('title', 'Documentação Técnica')}\n\n")
            f.write(f"> Categoria: `{entry.get('category', 'Cibersegurança')}` | Criado em: `{timestamp_str}`\n\n")
        else:
            f.write(f"\n\n---\n\n## Atualização: {entry.get('title', 'Registro Técnico')} ({timestamp_str})\n\n")
        f.write(entry.get("content", "").strip() + "\n")

    log_entry = f"- **[{timestamp_str}]** `{entry.get('category')}`: [{entry.get('title')}](knowledge-base/{filename}) &bull; *{entry.get('commit_message')}*\n"
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("# Registro Contínuo de Estudos e Atividades Técnicas\n\n")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)

    commit_msg = entry.get("commit_message", "docs(security): atualizar notas tecnicas")
    STATE["status_message"] = f"🚀 Enviando para o GitHub: \"{commit_msg}\"..."
    add_log("GIT", f"Criando commit: \"{commit_msg}\"...")

    try:
        subprocess.run(["git", "add", "docs/"], cwd=REPO_DIR, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_DIR, check=True, capture_output=True)
        
        add_log("GIT", "Executando git push origin main...")
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True, capture_output=True)
        
        sha = subprocess.check_output(["git", "log", "-1", "--format=%h"], cwd=REPO_DIR, text=True).strip()
        STATE["last_commit_sha"] = sha
        STATE["last_commit_msg"] = commit_msg
        STATE["last_run"] = timestamp_str
        STATE["commits_today"] += 1
        STATE["total_generated"] += 1
        STATE["status_message"] = "🟢 Concluído com Sucesso! Monitorando..."
        add_log("SUCESSO", f"Commit {sha} enviado ao GitHub com sucesso!")
        return True
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors='ignore') if e.stderr else str(e)
        STATE["status_message"] = "⚠️ Erro ao enviar para o GitHub"
        add_log("ERRO", f"Falha no Git: {err.strip()[:120]}")
        return False

def background_scheduler():
    """Thread que gerencia os intervalos e horários humanos."""
    add_log("SISTEMA", f"Repositório detectado: {REPO_DIR}")
    cfg = load_config()
    start_hour = cfg.get("start_hour", 9)
    end_hour = cfg.get("end_hour", 22)
    min_int = cfg.get("min_interval", 75)
    max_int = cfg.get("max_interval", 210)

    delay = random.randint(min_int, max_int)
    STATE["next_run_timestamp"] = time.time() + (delay * 60)
    add_log("AGENDADOR", f"Primeiro ciclo automático programado para daqui a {delay} minutos.")

    while STATE["is_running"]:
        if STATE["is_paused"]:
            time.sleep(2)
            continue

        now = datetime.datetime.now()
        current_hour = now.hour
        cfg = load_config()
        start_hour = cfg.get("start_hour", 9)
        end_hour = cfg.get("end_hour", 22)

        if start_hour <= current_hour <= end_hour:
            remaining = STATE["next_run_timestamp"] - time.time()
            if remaining <= 0:
                execute_commit_cycle()
                min_int = cfg.get("min_interval", 75)
                max_int = cfg.get("max_interval", 210)
                delay = random.randint(min_int, max_int)
                STATE["next_run_timestamp"] = time.time() + (delay * 60)
                add_log("AGENDADOR", f"Próxima atividade programada para daqui a {delay} minutos.")
            else:
                STATE["status_message"] = f"🟢 Ativo & Monitorando (Próximo ciclo em {int(remaining//60)}m)"
        else:
            STATE["status_message"] = f"🌙 Repouso Noturno (Pausado até as {start_hour:02d}:00)"

        time.sleep(1)

HTML_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GitHub AI Activity Hub | Pedro Mira</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0f111a;
      --card-bg: #1a1b26;
      --card-border: #292e42;
      --primary: #7aa2f7;
      --primary-hover: #89b4fa;
      --success: #9ece6a;
      --warning: #e0af68;
      --danger: #f7768e;
      --text: #c0caf5;
      --text-muted: #565f89;
      --code-bg: #16161e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Inter', sans-serif;
      padding: 24px;
      min-height: 100vh;
    }
    .container { max-width: 1100px; margin: 0 auto; }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 24px;
    }
    .brand { display: flex; align-items: center; gap: 12px; }
    .brand-icon {
      font-size: 32px;
      background: rgba(122, 162, 247, 0.15);
      border: 1px solid var(--primary);
      border-radius: 12px;
      padding: 6px 12px;
    }
    .brand h1 { font-size: 22px; font-weight: 700; color: #fff; }
    .brand p { font-size: 13px; color: var(--text-muted); }
    .header-actions { display: flex; align-items: center; gap: 12px; }
    .status-badge {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(158, 206, 106, 0.1);
      border: 1px solid var(--success);
      color: var(--success);
      padding: 8px 16px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 600;
    }
    .status-dot {
      width: 10px;
      height: 10px;
      background: var(--success);
      border-radius: 50%;
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0% { box-shadow: 0 0 0 0 rgba(158, 206, 106, 0.7); }
      70% { box-shadow: 0 0 0 10px rgba(158, 206, 106, 0); }
      100% { box-shadow: 0 0 0 0 rgba(158, 206, 106, 0); }
    }
    .grid-metrics {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 20px;
      position: relative;
    }
    .card-title {
      font-size: 13px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
    }
    .card-value { font-size: 26px; font-weight: 700; color: #fff; font-family: 'JetBrains Mono', monospace; }
    .card-sub { font-size: 12px; color: var(--primary); margin-top: 6px; }

    .actions-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 24px;
    }
    button {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: var(--primary);
      color: #0f111a;
      border: none;
      padding: 12px 20px;
      border-radius: 10px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    button:hover { background: var(--primary-hover); transform: translateY(-1px); }
    button.btn-secondary {
      background: var(--card-bg);
      color: var(--text);
      border: 1px solid var(--card-border);
    }
    button.btn-secondary:hover { background: var(--card-border); }

    .terminal-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 20px;
      margin-bottom: 24px;
    }
    .terminal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--card-border);
    }
    .terminal-header h3 { font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
    .terminal-body {
      background: var(--code-bg);
      border-radius: 10px;
      padding: 16px;
      height: 280px;
      overflow-y: auto;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12.5px;
      line-height: 1.6;
    }
    .log-line { display: flex; gap: 8px; margin-bottom: 4px; }
    .log-time { color: var(--text-muted); }
    .log-tag { font-weight: 700; padding: 0 4px; border-radius: 4px; }
    .tag-GEMINI { background: rgba(122, 162, 247, 0.2); color: var(--primary); }
    .tag-GIT { background: rgba(224, 175, 104, 0.2); color: var(--warning); }
    .tag-SUCESSO { background: rgba(158, 206, 106, 0.2); color: var(--success); }
    .tag-ERRO { background: rgba(247, 118, 142, 0.2); color: var(--danger); }
    .tag-INFO, .tag-CICLO, .tag-SISTEMA, .tag-AGENDADOR { background: rgba(86, 95, 137, 0.2); color: var(--text); }

    /* Modal de Configurações */
    .modal-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; width: 100vw; height: 100vh;
      background: rgba(15, 17, 26, 0.85);
      backdrop-filter: blur(4px);
      z-index: 1000;
      justify-content: center;
      align-items: center;
    }
    .modal-content {
      background: var(--card-bg);
      border: 1px solid var(--primary);
      border-radius: 18px;
      width: 90%;
      max-width: 600px;
      padding: 28px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--card-border);
    }
    .modal-header h2 { font-size: 18px; color: #fff; display: flex; align-items: center; gap: 8px; }
    .form-group { margin-bottom: 18px; }
    .form-group label {
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 6px;
    }
    .form-group .desc { font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }
    .input-wrapper { display: flex; gap: 8px; }
    input[type="text"], input[type="password"], input[type="number"], select {
      flex: 1;
      background: var(--code-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 10px 14px;
      color: #fff;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      outline: none;
    }
    input:focus, select:focus { border-color: var(--primary); }
    .modal-footer {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid var(--card-border);
    }
    .test-result {
      margin-top: 8px;
      font-size: 12px;
      display: none;
      padding: 8px 12px;
      border-radius: 6px;
    }
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: var(--success);
      color: #0f111a;
      padding: 12px 20px;
      border-radius: 8px;
      font-weight: 600;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      display: none;
      z-index: 2000;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="brand">
        <div class="brand-icon">🛡️</div>
        <div>
          <h1>GitHub AI Activity Hub</h1>
          <p>Automação Inteligente de Base Técnica & Contribuições &bull; <b>PedroMira2</b></p>
        </div>
      </div>
      <div class="header-actions">
        <button class="btn-secondary" onclick="openSettings()">
          ⚙️ Configurações
        </button>
        <div class="status-badge" id="badge-status">
          <div class="status-dot" id="badge-dot"></div>
          <span id="badge-text">Conectado & Ativo</span>
        </div>
      </div>
    </header>

    <div class="grid-metrics">
      <div class="card">
        <div class="card-title">⏱️ Próximo Commit em</div>
        <div class="card-value" id="countdown">--:--:--</div>
        <div class="card-sub" id="status-desc">Aguardando ciclo...</div>
      </div>
      <div class="card">
        <div class="card-title">📊 Commits Hoje</div>
        <div class="card-value" id="commits-today">0</div>
        <div class="card-sub" id="sched-hours">Horário: 09h às 22h</div>
      </div>
      <div class="card">
        <div class="card-title">🤖 Inteligência Artificial</div>
        <div class="card-value" id="active-model">Gemini 3.5</div>
        <div class="card-sub">Flash-Lite &bull; Alta Precisão</div>
      </div>
      <div class="card">
        <div class="card-title">🔗 Último Commit</div>
        <div class="card-value" id="last-commit-sha">---</div>
        <div class="card-sub" id="last-commit-msg" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">Nenhum ainda</div>
      </div>
    </div>

    <div class="actions-bar">
      <button onclick="triggerNow()" id="btn-trigger">
        ⚡ Gerar e Enviar com IA Agora
      </button>
      <button class="btn-secondary" onclick="togglePause()" id="btn-pause">
        ⏸️ Pausar Automação
      </button>
      <button class="btn-secondary" onclick="openGitHub()">
        🌐 Ver meu Perfil no GitHub
      </button>
    </div>

    <div class="terminal-card">
      <div class="terminal-header">
        <h3>📟 Console de Atividade em Tempo Real</h3>
        <span style="font-size: 12px; color: var(--text-muted);">Atualização ao vivo a cada 2s</span>
      </div>
      <div class="terminal-body" id="log-console">
        <div class="log-line"><span class="log-time">[00:00:00]</span> <span class="log-tag tag-INFO">[SISTEMA]</span> <span>Iniciando interface web de controle...</span></div>
      </div>
    </div>
  </div>

  <!-- Modal de Configurações -->
  <div class="modal-overlay" id="modal-settings">
    <div class="modal-content">
      <div class="modal-header">
        <h2>⚙️ Configurações do Sistema</h2>
        <button class="btn-secondary" style="padding: 6px 10px;" onclick="closeSettings()">✕</button>
      </div>
      <div class="form-group">
        <label>Chave de API do Google Gemini</label>
        <div class="desc">A sua chave de acesso à IA (armazenada de forma segura no arquivo local .env)</div>
        <div class="input-wrapper">
          <input type="password" id="cfg-api-key" placeholder="AQ.Ab... ou AIzaSy...">
          <button class="btn-secondary" type="button" onclick="toggleKeyVisibility()">👁️</button>
          <button class="btn-secondary" type="button" onclick="testApiKey()" id="btn-test-key">🧪 Testar</button>
        </div>
        <div class="test-result" id="test-key-result"></div>
      </div>
      <div class="form-group">
        <label>Modelo de Inteligência Artificial</label>
        <select id="cfg-model">
          <option value="gemini-3.5-flash-lite">gemini-3.5-flash-lite (Recomendado - Mais rápido e preciso)</option>
          <option value="gemini-3.1-flash-lite">gemini-3.1-flash-lite (Reserva de alta velocidade)</option>
          <option value="gemini-flash-latest">gemini-flash-latest</option>
        </select>
      </div>
      <div style="display: flex; gap: 16px;">
        <div class="form-group" style="flex: 1;">
          <label>Horário de Início (Hora)</label>
          <input type="number" id="cfg-start-hour" min="0" max="23" value="9">
        </div>
        <div class="form-group" style="flex: 1;">
          <label>Horário de Término (Hora)</label>
          <input type="number" id="cfg-end-hour" min="0" max="23" value="22">
        </div>
      </div>
      <div style="display: flex; gap: 16px;">
        <div class="form-group" style="flex: 1;">
          <label>Intervalo Mínimo (Minutos)</label>
          <input type="number" id="cfg-min-interval" min="10" max="300" value="75">
        </div>
        <div class="form-group" style="flex: 1;">
          <label>Intervalo Máximo (Minutos)</label>
          <input type="number" id="cfg-max-interval" min="20" max="600" value="210">
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-secondary" onclick="closeSettings()">Cancelar</button>
        <button onclick="saveSettings()">💾 Salvar Configurações</button>
      </div>
    </div>
  </div>

  <div class="toast" id="toast">Configurações salvas com sucesso!</div>

  <script>
    let isPaused = false;

    function showToast(msg, bg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      if (bg) t.style.background = bg;
      t.style.display = 'block';
      setTimeout(() => t.style.display = 'none', 3000);
    }

    async function updateStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();

        isPaused = data.is_paused;
        document.getElementById('btn-pause').innerHTML = isPaused ? '▶️ Retomar Automação' : '⏸️ Pausar Automação';
        
        const badge = document.getElementById('badge-status');
        const badgeText = document.getElementById('badge-text');
        const badgeDot = document.getElementById('badge-dot');
        
        if (isPaused) {
          badgeText.innerText = 'Pausado Manualmente';
          badge.style.borderColor = 'var(--warning)';
          badge.style.color = 'var(--warning)';
          badgeDot.style.background = 'var(--warning)';
        } else {
          badgeText.innerText = 'Online & Monitorando';
          badge.style.borderColor = 'var(--success)';
          badge.style.color = 'var(--success)';
          badgeDot.style.background = 'var(--success)';
        }

        document.getElementById('commits-today').innerText = data.commits_today;
        document.getElementById('last-commit-sha').innerText = data.last_commit_sha;
        document.getElementById('last-commit-msg').innerText = data.last_commit_msg;
        document.getElementById('status-desc').innerText = data.status_message;
        document.getElementById('active-model').innerText = data.active_model.replace('gemini-', '');

        // Countdown
        if (data.next_run_timestamp > 0) {
          const now = Date.now() / 1000;
          let diff = Math.max(0, Math.floor(data.next_run_timestamp - now));
          if (isPaused) {
            document.getElementById('countdown').innerText = 'PAUSADO';
          } else {
            const h = String(Math.floor(diff / 3600)).padStart(2, '0');
            const m = String(Math.floor((diff % 3600) / 60)).padStart(2, '0');
            const s = String(diff % 60).padStart(2, '0');
            document.getElementById('countdown').innerText = `${h}:${m}:${s}`;
          }
        }

        // Logs
        const consoleEl = document.getElementById('log-console');
        consoleEl.innerHTML = data.logs.map(l => `
          <div class="log-line">
            <span class="log-time">[${l.time}]</span>
            <span class="log-tag tag-${l.tag}">[${l.tag}]</span>
            <span>${l.message}</span>
          </div>
        `).join('');
        consoleEl.scrollTop = consoleEl.scrollHeight;

      } catch (err) {
        console.error("Erro ao atualizar status:", err);
      }
    }

    async function triggerNow() {
      const btn = document.getElementById('btn-trigger');
      btn.disabled = true;
      btn.innerHTML = '⏳ Gerando com Gemini...';
      try {
        await fetch('/api/trigger', { method: 'POST' });
        showToast("Ciclo iniciado! Acompanhe no console.");
      } catch (err) {
        alert("Erro ao disparar commit.");
      }
      setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = '⚡ Gerar e Enviar com IA Agora';
        updateStatus();
      }, 3000);
    }

    async function togglePause() {
      await fetch('/api/toggle-pause', { method: 'POST' });
      updateStatus();
    }

    function openGitHub() {
      window.open('https://github.com/PedroMira2', '_blank');
    }

    async function openSettings() {
      try {
        const res = await fetch('/api/config');
        const data = await res.json();
        document.getElementById('cfg-api-key').value = data.api_key || '';
        document.getElementById('cfg-model').value = data.model || 'gemini-3.5-flash-lite';
        document.getElementById('cfg-start-hour').value = data.start_hour !== undefined ? data.start_hour : 9;
        document.getElementById('cfg-end-hour').value = data.end_hour !== undefined ? data.end_hour : 22;
        document.getElementById('cfg-min-interval').value = data.min_interval || 75;
        document.getElementById('cfg-max-interval').value = data.max_interval || 210;
        document.getElementById('test-key-result').style.display = 'none';
        document.getElementById('modal-settings').style.display = 'flex';
      } catch (e) {
        alert("Erro ao carregar configurações: " + e);
      }
    }

    function closeSettings() {
      document.getElementById('modal-settings').style.display = 'none';
    }

    function toggleKeyVisibility() {
      const input = document.getElementById('cfg-api-key');
      input.type = input.type === 'password' ? 'text' : 'password';
    }

    async function testApiKey() {
      const key = document.getElementById('cfg-api-key').value.trim();
      const model = document.getElementById('cfg-model').value;
      const resEl = document.getElementById('test-key-result');
      const btn = document.getElementById('btn-test-key');
      btn.disabled = true;
      btn.innerText = 'Testando...';
      resEl.style.display = 'block';
      resEl.innerText = 'Conectando ao Google Gemini...';
      resEl.style.background = 'rgba(122, 162, 247, 0.15)';
      resEl.style.color = 'var(--primary)';

      try {
        const res = await fetch('/api/test-key', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: json_stringify = JSON.stringify({ api_key: key, model: model })
        });
        const result = await res.json();
        if (result.success) {
          resEl.style.background = 'rgba(158, 206, 106, 0.2)';
          resEl.style.color = 'var(--success)';
          resEl.innerText = '✅ ' + result.message;
        } else {
          resEl.style.background = 'rgba(247, 118, 142, 0.2)';
          resEl.style.color = 'var(--danger)';
          resEl.innerText = '❌ ' + result.message;
        }
      } catch (err) {
        resEl.style.background = 'rgba(247, 118, 142, 0.2)';
        resEl.style.color = 'var(--danger)';
        resEl.innerText = '❌ Erro de comunicação: ' + err;
      }
      btn.disabled = false;
      btn.innerText = '🧪 Testar';
    }

    async function saveSettings() {
      const cfg = {
        api_key: document.getElementById('cfg-api-key').value.trim(),
        model: document.getElementById('cfg-model').value,
        start_hour: parseInt(document.getElementById('cfg-start-hour').value) || 9,
        end_hour: parseInt(document.getElementById('cfg-end-hour').value) || 22,
        min_interval: parseInt(document.getElementById('cfg-min-interval').value) || 75,
        max_interval: parseInt(document.getElementById('cfg-max-interval').value) || 210,
      };

      try {
        const res = await fetch('/api/config', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(cfg)
        });
        const data = await res.json();
        closeSettings();
        showToast("Configurações salvas com sucesso!");
        document.getElementById('sched-hours').innerText = `Horário: ${cfg.start_hour}h às ${cfg.end_hour}h`;
        updateStatus();
      } catch (e) {
        alert("Erro ao salvar: " + e);
      }
    }

    setInterval(updateStatus, 2000);
    updateStatus();
  </script>
</body>
</html>
"""

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(STATE).encode("utf-8"))
        elif self.path == "/api/config":
            cfg = load_config()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(cfg).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len).decode('utf-8') if content_len > 0 else ""
        
        if self.path == "/api/trigger":
            threading.Thread(target=execute_commit_cycle, kwargs={"is_manual": True}).start()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "triggered"}).encode())
        elif self.path == "/api/toggle-pause":
            STATE["is_paused"] = not STATE["is_paused"]
            add_log("SISTEMA", f"Automação {'pausada' if STATE['is_paused'] else 'retomada'} pelo usuário.")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"is_paused": STATE["is_paused"]}).encode())
        elif self.path == "/api/config":
            try:
                new_data = json.loads(body)
                updated = save_config(new_data)
                add_log("CONFIG", "Configurações atualizadas com sucesso pelo usuário.")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "config": updated}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
        elif self.path == "/api/test-key":
            try:
                req_data = json.loads(body) if body else {}
                key = req_data.get("api_key") or load_config().get("api_key")
                model = req_data.get("model") or "gemini-3.5-flash-lite"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                test_r = requests.post(
                    url,
                    json={"contents": [{"parts": [{"text": "Responda apenas: OK"}]}]},
                    timeout=10
                )
                if test_r.status_code == 200:
                    res_json = {"success": True, "message": f"Chave válida! Conectado com sucesso ao {model}."}
                else:
                    err_msg = test_r.json().get("error", {}).get("message", test_r.text)
                    res_json = {"success": False, "message": f"Erro {test_r.status_code}: {err_msg[:120]}"}
            except Exception as err:
                res_json = {"success": False, "message": f"Erro de conexão: {str(err)[:120]}"}
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res_json).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def run_server():
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    add_log("SISTEMA", f"Servidor Dashboard Web ativo em http://127.0.0.1:{PORT}")
    server.serve_forever()

def main():
    add_log("SISTEMA", "Iniciando GitHub AI Activity Hub...")
    t_sched = threading.Thread(target=background_scheduler, daemon=True)
    t_sched.start()

    threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(f"http://127.0.0.1:{PORT}")), daemon=True).start()

    run_server()

if __name__ == "__main__":
    main()
