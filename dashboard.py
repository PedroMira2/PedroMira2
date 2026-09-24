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

# Diretórios base
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(REPO_DIR, "docs")
KB_DIR = os.path.join(DOCS_DIR, "knowledge-base")
LOG_FILE = os.path.join(DOCS_DIR, "activity-log.md")
ENV_FILE = os.path.join(REPO_DIR, ".env")

PORT = 5050

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
    if len(STATE["logs"]) > 100:
        STATE["logs"].pop(0)
    print(f"[{timestamp}] [{tag}] {message}")

def load_api_key():
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
    return os.environ.get("GEMINI_API_KEY", "")

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
    api_key = load_api_key()
    if not api_key:
        add_log("ERRO", "Chave GEMINI_API_KEY não configurada no arquivo .env.")
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
    for model in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]:
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
        add_log("ERRO", f"Falha no Git: {err.strip()[:100]}")
        return False

def background_scheduler():
    """Thread que gerencia os intervalos e horários humanos."""
    add_log("SISTEMA", "Agendador inteligente iniciado.")
    # Primeira execução agenda o próximo commit
    delay = random.randint(75, 210)
    STATE["next_run_timestamp"] = time.time() + (delay * 60)
    add_log("AGENDADOR", f"Primeiro ciclo automático programado para daqui a {delay} minutos.")

    while STATE["is_running"]:
        if STATE["is_paused"]:
            time.sleep(2)
            continue

        now = datetime.datetime.now()
        current_hour = now.hour

        # Verifica se está no horário humano (09:00 às 22:30)
        if 9 <= current_hour <= 22:
            remaining = STATE["next_run_timestamp"] - time.time()
            if remaining <= 0:
                execute_commit_cycle()
                delay = random.randint(75, 210)
                STATE["next_run_timestamp"] = time.time() + (delay * 60)
                add_log("AGENDADOR", f"Próxima atividade programada para daqui a {delay} minutos.")
            else:
                STATE["status_message"] = f"🟢 Ativo & Monitorando (Próximo ciclo em {int(remaining//60)}m)"
        else:
            STATE["status_message"] = "🌙 Repouso Noturno (Pausado até as 09:00 para simular rotina humana)"

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
      overflow: hidden;
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
      <div class="status-badge" id="badge-status">
        <div class="status-dot" id="badge-dot"></div>
        <span id="badge-text">Conectado & Ativo</span>
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
        <div class="card-sub">Horário Ativo: 09h às 22h30</div>
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

  <script>
    let isPaused = false;

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
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
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
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silencia logs padrão do HTTP para manter o console limpo
        pass

def run_server():
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    add_log("SISTEMA", f"Servidor Dashboard Web iniciado em http://127.0.0.1:{PORT}")
    server.serve_forever()

def main():
    add_log("SISTEMA", "Iniciando GitHub AI Activity Hub...")
    # Inicia thread do agendador em segundo plano
    t_sched = threading.Thread(target=background_scheduler, daemon=True)
    t_sched.start()

    # Abre o navegador automaticamente
    threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(f"http://127.0.0.1:{PORT}")), daemon=True).start()

    # Roda o servidor Web
    run_server()

if __name__ == "__main__":
    main()
