# Bot de busca de vagas — 100% gratuito

Busca vagas de estágio/júnior na Adzuna, valida contra o seu currículo usando o
Gemini (Google) e manda por email as que passarem do score mínimo. Roda sozinho
a cada hora via GitHub Actions.

## Por que essas escolhas

- **Adzuna** em vez de LinkedIn/InfoJobs: é a única das opções com API pública,
  gratuita e sem risco de banimento de conta (LinkedIn e InfoJobs não têm API
  aberta — só dá pra pegar via scraping, o que quebra fácil e viola os termos
  de uso deles).
- **Gemini (tier gratuito)** em vez da API da Anthropic: a API da Anthropic não
  tem tier gratuito contínuo, só ~$5 de crédito único que acaba em 1-2 dias de
  uso. O Gemini free tier aguenta ~1.500 chamadas/dia sem cartão de crédito.
  **Atenção:** no tier gratuito, o Google pode usar o conteúdo enviado
  (incluindo seu currículo) para treinar modelos. Se isso for um problema pra
  você, dá pra trocar depois por um provedor pago barato só nessa etapa.
- **Repositório público** no GitHub: minutos de Actions ilimitados de graça
  (repositório privado tem teto de 2.000 min/mês, que é apertado rodando de
  hora em hora). Suas chaves ficam em *Secrets*, que não aparecem nem em
  repositório público — mas o **currículo também vai como Secret**, não como
  arquivo commitado, justamente para não expor seus dados pessoais
  publicamente.

## Passo a passo

### 1. Adzuna (fonte das vagas)
1. Crie conta em https://developer.adzuna.com/
2. Copie o `app_id` e o `app_key` do seu painel.

### 2. Gemini (validação das vagas)
1. Crie conta em https://aistudio.google.com/
2. Gere uma API key (não pede cartão de crédito).

### 3. Gmail (envio do email)
1. Ative a verificação em duas etapas na sua conta Google (obrigatório pra
   gerar senha de app): https://myaccount.google.com/security
2. Gere uma "senha de app" em https://myaccount.google.com/apppasswords
3. Use essa senha (não a senha normal da conta) na configuração abaixo.

### 4. Criar o repositório no GitHub
1. Crie um repositório **público** novo no GitHub.
2. Suba todos os arquivos desta pasta pra ele (`main.py`, `requirements.txt`,
   `seen_jobs.json`, a pasta `.github/`).

### 5. Configurar os Secrets
No repositório: **Settings → Secrets and variables → Actions → New repository
secret**. Crie cada um destes:

| Nome | Valor |
|---|---|
| `ADZUNA_APP_ID` | seu app_id da Adzuna |
| `ADZUNA_APP_KEY` | sua app_key da Adzuna |
| `GEMINI_API_KEY` | sua chave do Gemini |
| `GMAIL_ADDRESS` | seu email do Gmail |
| `GMAIL_APP_PASSWORD` | a senha de app gerada no passo 3 |
| `DEST_EMAIL` | email que vai receber as vagas (pode ser o mesmo do Gmail) |
| `RESUME_TEXT` | o texto do seu currículo, colado direto (não o PDF) |

### 6. Testar
Vá em **Actions** no repositório, escolha o workflow "Busca de vagas" e clique
em **Run workflow** pra rodar manualmente antes de esperar a próxima hora
cheia. Confira os logs — se der erro, ele aparece ali, com a mensagem exata de
qual etapa falhou.

## Ajustar depois

- **Palavras-chave da busca**: variável `ADZUNA_WHAT_OR` no `main.py` (ou como
  Secret/variável de ambiente, se preferir não editar código). Hoje está
  restrita a estágio/júnior/trainee, refletindo seu currículo atual.
- **Score mínimo pra considerar "compatível"**: `SCORE_THRESHOLD` (padrão 50).
- **Site pra ver no celular**: não incluído nesta primeira versão de
  propósito — entra depois que esse fluxo (busca → validação → email) provar
  que funciona sem quebrar.
