# Monitor de preços — iPhone 512GB

Coleta diária de ofertas de **iPhone 15 em diante com 512GB** nas principais lojas brasileiras. Os dados ficam versionados neste repositório (SQLite). A análise é publicada num dashboard no GitHub Pages e chega por e-mail.

Custo: **R$ 0**. Usa GitHub Actions (grátis em repositório público), GitHub Pages e SMTP do Gmail.

## Como funciona

```
GitHub Actions (todo dia 07:47 BRT)
  → coletores por loja → normalização (modelo, 512GB, cor, condição, tags)
  → data/prices.sqlite (histórico, commitado no repo)
  → análise (mín. 7/30/90 dias, mediana 30d, recorde, vs Apple Store, desconto inflado)
  → docs/data/*.json → dashboard (GitHub Pages)
  → e-mail HTML com alertas, tabela por modelo/condição e link do dashboard
```

### Lojas

| Loja | Método | Status no teste (17/11/2026) |
|---|---|---|
| Kabum | JSON da página de busca (`__NEXT_DATA__`) | ok (inclui parceiros: Magalu, iPlace…) |
| Americanas | API pública VTEX Intelligent Search | ok (inclui parceiros: Magalu, iPlace, Trocafone…) |
| Carrefour | API pública VTEX Intelligent Search | ok (inclui parceiros) |
| Apple Store BR | JSON da página de compra | ok (preço oficial de referência) |
| Magalu, Casas Bahia, Mercado Livre, Amazon | JSON-LD genérico | bloqueiam acesso de servidores; aparecem como "bloqueada" no relatório |

### Tags de cada oferta

- **Condição:** `novo`, `vitrine` (inclui open box e mostruário), `recondicionado`, `usado` (inclui seminovo).
- **Estado do usado:** `estado: excelente / muito bom / bom`.
- **Vendedor:** `loja oficial` ou `marketplace` (vendido por terceiro).
- **Outras:** `importado`, `somente eSIM`, `lacrado`, `promoção`, `-X% vs preço 'de'`.

### Alertas (editáveis em `config.toml`)

- Preço X% abaixo da mediana de 30 dias (padrão: 8%).
- Menor preço já registrado (pelo menos 1% abaixo do recorde anterior).
- Preço-alvo por modelo.
- Aviso de desconto possivelmente inflado: o preço "de" está alto, mas o preço real está igual à média.

## Configuração (uma vez)

1. **Secrets do repositório.** Em *Settings → Secrets and variables → Actions → New repository secret*, crie:
   - `SMTP_USER`: seu Gmail (remetente).
   - `SMTP_PASS`: uma **senha de app** do Google (myaccount.google.com → Segurança → Verificação em duas etapas → Senhas de app). Não use a senha normal.
   - `EMAIL_TO`: o e-mail que vai receber o relatório (aceita vários, separados por vírgula).
2. **GitHub Pages.** Em *Settings → Pages → Build and deployment*, escolha *Deploy from a branch*, depois `main` e a pasta `/docs`.
3. **Primeira execução.** Em *Actions → Coleta diária de preços → Run workflow*.

O link do dashboard é `https://<usuario>.github.io/<repositorio>/`.

## Rodar localmente

```bash
pip install -r requirements.txt
python -m tracker.main --no-email          # todas as lojas
python -m tracker.main --only kabum apple  # só algumas
python -m pytest -q
```

## Limitações

- O preço à vista é o menor preço PIX/boleto anunciado. Frete e cupons aplicados no checkout não entram.
- Os coletores dependem do formato dos sites. Se uma loja mudar, ela aparece como `erro` no e-mail e as outras continuam funcionando.
- O GitHub pode atrasar execuções agendadas em horários de pico.
