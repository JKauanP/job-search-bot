"""
Bot de busca de vagas — 100% gratuito
Fluxo: Adzuna (busca) -> Gemini (validação contra o currículo) -> Gmail SMTP (envio)

Todas as credenciais vêm de variáveis de ambiente (GitHub Secrets no workflow).
Nada de chave hardcoded aqui.
"""

import os
import sys
import json
import time
import smtplib
import ssl
import requests
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ---- Configuração (via env vars) ----
ADZUNA_APP_ID = os.environ["ADZUNA_APP_ID"]
ADZUNA_APP_KEY = os.environ["ADZUNA_APP_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
DEST_EMAIL = os.environ.get("DEST_EMAIL", GMAIL_ADDRESS)
RESUME_TEXT = os.environ["RESUME_TEXT"]

# Palavras-chave padrão: refletem o perfil real do currículo (estágio/júnior/trainee).
# "desenvolvedor pleno/sênior" NÃO entra aqui de propósito — não faz sentido gastar
# a cota da API avaliando vagas que o candidato não atende.
KEYWORDS = os.environ.get(
    "ADZUNA_WHAT_OR",
    "estagio desenvolvimento estagio programacao desenvolvedor junior trainee ti"
)
SCORE_THRESHOLD = int(os.environ.get("SCORE_THRESHOLD", "50"))
MAX_DAYS_OLD = int(os.environ.get("ADZUNA_MAX_DAYS_OLD", "1"))
RESULTS_PER_PAGE = int(os.environ.get("ADZUNA_RESULTS_PER_PAGE", "20"))

SEEN_FILE = "seen_jobs.json"
SEEN_RETENTION_DAYS = 14

GEMINI_MODEL = "gemini-3.5-flash-lite"  # modelo GA atual, do tier gratuito


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_seen(seen):
    cutoff = datetime.now(timezone.utc) - timedelta(days=SEEN_RETENTION_DAYS)
    pruned = {}
    for jid, ts in seen.items():
        try:
            if datetime.fromisoformat(ts) > cutoff:
                pruned[jid] = ts
        except ValueError:
            continue
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(pruned, f, ensure_ascii=False, indent=2)


def fetch_jobs():
    url = "https://api.adzuna.com/v1/api/jobs/br/search/1"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what_or": KEYWORDS,
        "category": "it-jobs",
        "max_days_old": MAX_DAYS_OLD,
        "results_per_page": RESULTS_PER_PAGE,
        "content-type": "application/json",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("results", [])


def evaluate_with_gemini(job):
    prompt = f"""Você é um avaliador honesto de aderência entre currículo e vaga de emprego.
Seja crítico: não infle o score para agradar. Se faltar requisito importante, isso deve reduzir o score.

CURRÍCULO DO CANDIDATO:
{RESUME_TEXT}

VAGA:
Título: {job.get('title', '')}
Empresa: {job.get('company', {}).get('display_name', 'Não informado')}
Descrição: {job.get('description', '')}

Responda ESTRITAMENTE em JSON válido, sem markdown, sem texto antes ou depois, no formato:
{{"score": <inteiro de 0 a 100>, "justificativa": "<2-3 frases: por que o candidato pode se candidatar e quais lacunas existem, se houver>"}}
"""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(url, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

    # Gemini às vezes envolve o JSON em ```json ... ``` mesmo pedindo pra não fazer isso
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    return json.loads(text)


def send_email(matches):
    if not matches:
        print("Nenhuma vaga compatível nesta execução — email não enviado.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Vagas compatíveis - {datetime.now().strftime('%d/%m %H:%M')}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = DEST_EMAIL

    body_lines = []
    for m in matches:
        job, ev = m["job"], m["eval"]
        company = job.get("company", {}).get("display_name", "Empresa não informada")
        body_lines.append(
            f"{job.get('title')} — {company}\n"
            f"Aderência: {ev.get('score')}/100\n"
            f"Por quê: {ev.get('justificativa')}\n"
            f"Candidatura: {job.get('redirect_url')}\n"
            "-----------------------------"
        )
    body = "\n\n".join(body_lines)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls(context=context)
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, DEST_EMAIL, msg.as_string())
    print(f"Email enviado com {len(matches)} vaga(s).")


def main():
    seen = load_seen()
    jobs = fetch_jobs()
    now_iso = datetime.now(timezone.utc).isoformat()

    matches = []
    novas = 0
    for job in jobs:
        jid = str(job.get("id"))
        if not jid or jid in seen:
            continue
        novas += 1
        try:
            ev = evaluate_with_gemini(job)
        except Exception as e:
            print(f"Erro avaliando vaga {jid}: {e}", file=sys.stderr)
            continue

        seen[jid] = now_iso
        if ev.get("score", 0) >= SCORE_THRESHOLD:
            matches.append({"job": job, "eval": ev})

        time.sleep(4.5)  # respeita o limite de 15 req/min do tier gratuito do Gemini

    send_email(matches)
    save_seen(seen)
    print(f"Vagas retornadas: {len(jobs)} | Novas: {novas} | Compatíveis: {len(matches)}")


if __name__ == "__main__":
    main()
