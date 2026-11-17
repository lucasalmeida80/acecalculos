# ACE — Antunes Consultoria Empresarial

Site institucional da **ACE Antunes Consultoria Empresarial**, de Oswaldo Antunes Neto, contador com quase 40 anos de experiência.

🌐 **No ar em:** [acecalculos.com.br](https://acecalculos.com.br/)

## O que tem no site

- **Calculadora de Correção Monetária** — busca índices em tempo real na API do Banco Central (IPCA, IGP-M, INPC, SELIC, CDI, TR) e calcula o valor corrigido no período.
- **Simulador SERO — INSS de Obras** — aferição indireta conforme IN RFB nº 2.021/2021, com valores de VAU por UF e categoria de obra.

## Estrutura

| Arquivo | Descrição |
|---|---|
| `index.html` | Site completo (single-file: HTML + CSS + JS inline) |
| `vau.json` | Tabela de VAU por período/UF, atualizada mensalmente |
| `ACE - Logo 1.png` | Logo oficial (navbar, footer e favicon) |
| `scripts/atualiza_vau.py` | Virada de mês automática do VAU (roda via launchd todo dia 3) |
| `scripts/instalar_agendamento.sh` | Instala o agendamento no launchd do Mac |

## Desenvolvimento local

```bash
python3 -m http.server 8080
```

Abrir http://localhost:8080 — servir via HTTP é necessário porque o `fetch` do `vau.json` e da API do BC não funciona com `file://`.

## Deploy

O site é estático e vai para a HostGator por FTPS. O GitHub é só versionamento — **push não publica nada**.

Credenciais ficam no `~/.netrc` (peça ao Lucas; nunca commitar):

```
machine sh00048.hostgator.com.br
login deploy@acecalculos.com.br
password "..."
```

Depois: `chmod 600 ~/.netrc`.

Subir um arquivo:

```bash
curl --netrc --ssl-reqd -T vau.json "ftp://sh00048.hostgator.com.br/vau.json"
```

Conferir no ar (o `cb` fura o cache):

```bash
curl -s "https://acecalculos.com.br/vau.json?cb=$(date +%s)" | shasum
shasum vau.json
```

### Cuidados

- **Sempre `sh00048.hostgator.com.br`, nunca `ftp.acecalculos.com.br`.** O `.netrc` tem as duas entradas, mas o certificado TLS do servidor não cobre o domínio da ACE e o curl falha com `SSL: no alternative certificate subject name matches target host name`.
- Antes de sobrescrever, baixe o arquivo remoto e compare o checksum com sua cópia de partida — garante que ninguém publicou algo pelo cPanel no meio do caminho.
- A `public_html` tem restos de uma instalação WordPress antiga (`wp-admin`, `wp-*.php`). O site atual não usa nada disso — não mexer.
- Arquivos que existem no servidor: `index.html`, `vau.json`, `ACE - Logo 1.png` e o HTML de verificação do Google.

### Virada de mês (VAU)

Fonte: <https://www.tabelavau.seroassessoria.com.br/tabela_vau.php> (pública, sem login). Os valores estão em `<input name="val_vau_{UF}_{CAT}" value="...">` — baixar com `curl` e extrair com regex.

Mapeamento das categorias: `RU=uni`, `RM=multi`, `COM=comercial`, `GI=galpao`, `CP=popular`, `CHP=conjunto`.

1. Checar se a competência já saiu (sai nos primeiros dias do mês) — o `<select name="filtro_periodo_vau">` marca a ativa com "(Ativado)"
2. Adicionar o bloco do mês no topo de `periodos` no `vau.json` e atualizar `periodoAtual`
3. Upload do `vau.json` (só ele — o `index.html` não muda)
4. Verificar no ar
5. Commit + push

Sanity check: a variação mensal é uniforme para todas as UFs (Sinapi é nacional). Se uma UF destoar, é erro de parse — ou da fonte.

#### Automático (launchd)

Tudo acima é feito sozinho por `scripts/atualiza_vau.py`, agendado no launchd do Mac para o **dia 3 de cada mês às 10h** (hora local), repetindo nos dias 4 a 12 até a SERO publicar a competência. O script é idempotente: se o mês já está no `vau.json`, sai sem fazer nada.

O agente roda a partir de um clone próprio em `~/.acecalculos` (o macOS não deixa processos em segundo plano lerem `~/Documents`). Ele dá `git pull` antes e `git push` depois, então **na cópia de trabalho basta um `git pull` para receber o mês novo**.

Regras embutidas:
- Variação uniforme: célula que destoa mais de 0,5% da mediana do mês e repete o valor de outra categoria da mesma UF é erro de cópia da SERO → substituída por `valor anterior × variação do mês`, registrado no commit. Qualquer outra anomalia aborta.
- Antes de subir, confere que o `vau.json` do servidor é igual ao do último commit (ninguém mexeu pelo cPanel). Depois, confere que a cópia pública bate com a local.
- Notificação do macOS no sucesso, na anomalia e no erro. Log em `~/Library/Logs/acecalculos-vau.log`.

Instalar/reinstalar neste Mac: `sh scripts/instalar_agendamento.sh`. Testar na hora: `launchctl kickstart gui/$(id -u)/com.acecalculos.vau`. Rodar à mão sem subir nada: `scripts/atualiza_vau.py --mes 2026-11 --forcar --dry-run`.
