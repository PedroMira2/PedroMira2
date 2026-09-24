"""
Sistema Inteligente de Atividade e Documentação Técnica no GitHub com Gemini AI
Autor: Pedro Mira
"""

import os
import sys
import time
import json
import random
import datetime
import subprocess
import requests

# Diretórios
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(REPO_DIR, "docs")
KB_DIR = os.path.join(DOCS_DIR, "knowledge-base")
LOG_FILE = os.path.join(DOCS_DIR, "activity-log.md")
ENV_FILE = os.path.join(REPO_DIR, ".env")

# Modelos do Gemini em ordem de prioridade
GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite"
]

def load_api_key():
    """Carrega a chave de API estritamente do arquivo .env ou variável de ambiente."""
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("Chave GEMINI_API_KEY não configurada. Defina-a no arquivo local .env.")
    return key

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
        "filename": "sql-injection-prevention.md",
        "commit_message": "docs(appsec): atualizar tecnicas de prepared statements contra SQLi",
        "title": "Prevenção Avançada Contra SQL Injection em Aplicações Web",
        "content": "A injeção de SQL continua sendo uma das falhas mais críticas na segurança de aplicações. O uso de Prepared Statements com consultas parametrizadas garante que os dados fornecidos pelo usuário sejam tratados estritamente como literais, neutralizando a interpretação arbitrária de comandos pelo SGBD.\n\n```python\n# Exemplo de consulta parametrizada segura em Python (SQLite/PostgreSQL)\nimport sqlite3\n\nconn = sqlite3.connect('database.db')\ncursor = conn.cursor()\n\nusername = input('Usuario: ')\nquery = 'SELECT id, role FROM users WHERE username = ? AND is_active = 1'\ncursor.execute(query, (username,))\nresult = cursor.fetchall()\n```"
    },
    {
        "category": "Hardening",
        "filename": "linux-ssh-hardening.md",
        "commit_message": "docs(hardening): revisar configuracoes restritivas para SSH",
        "title": "Checklist de Hardening para o Serviço OpenSSH",
        "content": "A proteção do acesso remoto via SSH é a primeira linha de defesa em servidores Linux. Desabilitar login direto do usuário root, restringir autenticação exclusivamente a chaves públicas ED25519 e alterar portas padrão reduzem drasticamente ataques de força bruta.\n\n```bash\n# /etc/ssh/sshd_config\nPermitRootLogin no\nPasswordAuthentication no\nPubkeyAuthentication yes\nX11Forwarding no\nMaxAuthTries 3\n```"
    }
]

def generate_entry_with_gemini(api_key):
    """Gera uma entrada técnica realista e inédita utilizando a IA do Gemini."""
    domain = random.choice(DOMAINS)
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
    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.7
            }
        }
        try:
            r = requests.post(url, json=payload, timeout=25)
            if r.status_code == 200:
                raw_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(raw_text)
                return data
            else:
                print(f"[!] Modelo {model} retornou status {r.status_code}. Tentando alternativa...")
        except Exception as e:
            print(f"[!] Erro ao chamar {model}: {e}")
            time.sleep(1)

    print("[!] Utilizando template técnico de contingência (offline fallback)...")
    return random.choice(FALLBACK_TEMPLATES)

def save_and_commit(entry):
    """Salva a documentação técnica gerada e faz o push para o GitHub."""
    os.makedirs(KB_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    filename = entry.get("filename", "security-notes.md")
    if not filename.endswith(".md"):
        filename += ".md"
    file_path = os.path.join(KB_DIR, filename)

    now = datetime.datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Salva ou anexa ao arquivo específico da base de conhecimento
    file_mode = "a" if os.path.exists(file_path) else "w"
    with open(file_path, file_mode, encoding="utf-8") as f:
        if file_mode == "w":
            f.write(f"# {entry.get('title', 'Documentação Técnica')}\n\n")
            f.write(f"> Categoria: `{entry.get('category', 'Cibersegurança')}` | Criado em: `{timestamp_str}`\n\n")
        else:
            f.write(f"\n\n---\n\n## Atualização: {entry.get('title', 'Registro Técnico')} ({timestamp_str})\n\n")
        f.write(entry.get("content", "").strip() + "\n")

    # Atualiza o diário de bordo / activity log
    log_entry = f"- **[{timestamp_str}]** `{entry.get('category')}`: [{entry.get('title')}](knowledge-base/{filename}) &bull; *{entry.get('commit_message')}*\n"
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("# Registro Contínuo de Estudos e Atividades Técnicas\n\n")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)

    commit_msg = entry.get("commit_message", "docs(security): atualizar base de conhecimento")

    try:
        subprocess.run(["git", "add", "docs/"], cwd=REPO_DIR, check=True)
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_DIR, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True)
        print(f"\n[+] [{timestamp_str}] Sucesso!")
        print(f"    Commit: \"{commit_msg}\"")
        print(f"    Arquivo: docs/knowledge-base/{filename}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[-] Erro ao executar Git: {e}")
        return False

def run_now():
    """Gera e comita uma atualização imediatamente usando IA."""
    api_key = load_api_key()
    print("[*] Gerando documentação técnica com Gemini AI...")
    entry = generate_entry_with_gemini(api_key)
    print(f"[*] Tópico gerado: {entry.get('title')}")
    print(f"[*] Mensagem de commit: {entry.get('commit_message')}")
    return save_and_commit(entry)

def test_ai():
    """Testa apenas a geração da IA sem comitar nada."""
    api_key = load_api_key()
    print(f"[*] Testando conexão com a API do Gemini (Chave: {api_key[:6]}...{api_key[-4:]})...")
    entry = generate_entry_with_gemini(api_key)
    print("\n--- TESTE DE GERAÇÃO CONCLUÍDO COM SUCESSO ---")
    print(f"Categoria: {entry.get('category')}")
    print(f"Arquivo Alvo: {entry.get('filename')}")
    print(f"Commit: {entry.get('commit_message')}")
    print(f"Título: {entry.get('title')}")
    print("\nConteúdo Técnico:")
    print(entry.get("content"))
    print("---------------------------------------------")

def print_status():
    """Exibe o status do repositório e da automação."""
    api_key = load_api_key()
    masked_key = f"{api_key[:6]}...{api_key[-4:]}" if api_key else "Não configurada"
    print("=" * 60)
    print("STATUS DO SISTEMA INTELIGENTE DE ATIVIDADE")
    print("=" * 60)
    print(f"Repositório Local: {REPO_DIR}")
    print(f"Chave Gemini: {masked_key}")
    print(f"Modelo Primário: {GEMINI_MODELS[0]}")
    try:
        last_commit = subprocess.check_output(["git", "log", "-1", "--oneline"], cwd=REPO_DIR, text=True).strip()
        print(f"Último Commit: {last_commit}")
    except Exception:
        print("Último Commit: Não foi possível obter.")
    print("Horário de Operação Humana: 09:00 às 22:30 (dias úteis)")
    print("=" * 60)

def main_daemon():
    """Loop contínuo com comportamento humano e IA."""
    api_key = load_api_key()
    print("=" * 65)
    print("SISTEMA DE ATIVIDADE CONTÍNUA COM GEMINI AI INICIADO")
    print("=" * 65)
    print(f"Horário de operação: 09:00 às 22:30")
    print(f"Intervalo dinâmico: 75 a 210 minutos entre commits")
    print("Pressione Ctrl+C para pausar a qualquer momento.")
    print("=" * 65)

    while True:
        now = datetime.datetime.now()
        current_hour = now.hour

        if 9 <= current_hour <= 22:
            print(f"\n[*] [{now.strftime('%H:%M:%S')}] Horário ativo detectado. Solicitando tópico à IA...")
            entry = generate_entry_with_gemini(api_key)
            save_and_commit(entry)

            sleep_minutes = random.randint(75, 210)
            next_time = now + datetime.timedelta(minutes=sleep_minutes)
            print(f"[*] Próxima atividade programada para: {next_time.strftime('%H:%M:%S')} (~{sleep_minutes} min)")
            time.sleep(sleep_minutes * 60)
        else:
            print(f"[*] [{now.strftime('%H:%M:%S')}] Fora do horário humano. Em repouso até as 09:00...")
            time.sleep(3600)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "--now":
            run_now()
        elif arg == "--test-ai":
            test_ai()
        elif arg == "--status":
            print_status()
        else:
            print(f"Opção desconhecida: {arg}")
            print("Opções disponíveis: --now, --test-ai, --status")
    else:
        main_daemon()
