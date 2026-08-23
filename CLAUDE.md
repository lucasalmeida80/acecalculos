# ACE — Antunes Consultoria Empresarial (site institucional)

Site institucional de contabilidade/consultoria pericial, de Oswaldo Antunes Neto (contador, ~40 anos de experiência), em Manaus/AM. No ar em [acecalculos.com.br](https://acecalculos.com.br/).

## Stack

Site **single-file**, sem build, sem framework, sem dependências npm:

- `index.html` — HTML + CSS + JS tudo inline (~2850 linhas). Fontes via Google Fonts (Newsreader + Geist).
- `vau.json` — tabela de dados (VAU por UF/categoria de obra), atualizada manualmente todo mês.
- `ACE - Logo 1.png` — logo (navbar, footer, favicon, og:image).

Deploy: hospedagem estática simples, subindo os arquivos direto (ver instrução de atualização mensal no README).

## Rodar localmente

```bash
python3 -m http.server 8080
```

Precisa ser via HTTP (não `file://`), porque o JS faz `fetch('vau.json')` e chama a API do Banco Central.

## Estrutura do `index.html`

Seções (na ordem, todas `<section id="...">`):

1. `#navbar` — nav fixa + menu mobile (hamburger)
2. `#hero`
3. `#sobre`
4. `#mvv` — Missão/Visão/Valores
5. `#servicos`
6. `#calculadora` — **Calculadora de Correção Monetária**
7. `#inss-obra` — **Simulador SERO (INSS de Obras)**
8. `#contato`
9. `footer`
10. `.fc-overlay` (`#fcOverlay`) — modal "fale conosco" flutuante

### Calculadora de Correção Monetária (`#calculadora`)
Busca índices em tempo real na API do Banco Central (SGS/BCData):
`https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados`

Códigos SGS usados (em `INDICES`, por volta da linha 2599 de `index.html`): IPCA=433, IGP-M=189, INPC=188 (+ SELIC, CDI, TR). Calcula fator de correção entre duas datas informadas pelo usuário.

### Simulador SERO — INSS de Obras (`#inss-obra`)
Aferição indireta conforme **IN RFB nº 2.021/2021**. Usa a tabela `vau.json` (VAU por UF e categoria: `uni`, `multi`, `comercial`, `galpao`, `popular`, `conjunto`) para estimar o valor devido de INSS sobre a obra (base RMT, alíquota 36,8%). CTA final manda o resultado formatado para o WhatsApp.

### Contato
Não há backend/formulário real. O "formulário" (`#fcForm`, overlay flutuante) monta uma mensagem e abre `wa.me/5592991564219?text=...` (WhatsApp). Todos os CTAs de contato do site (nav, hero, footer, FAB flutuante) apontam para esse mesmo número via `wa.me`.

## Atualização mensal do `vau.json`

Quando a nova competência do VAU é publicada (início de cada mês):

1. Adicionar o bloco do novo mês no **topo** de `periodos` em `vau.json`
2. Atualizar `periodoAtual`
3. Subir o `vau.json` novo para a hospedagem

Formato de cada bloco: `{ "descricao": "Mês/Ano", "vau": { "UF": { uni, multi, comercial, galpao, popular, conjunto }, ... } }` para as 27 UFs.

## Tracking / integrações externas

- **Google Ads (gtag.js)** — `AW-18388636462`, com evento de conversão `gtag_report_conversion` disparado em cliques de WhatsApp.
- **Schema.org JSON-LD** (`AccountingService`) no `<head>` — manter sincronizado com dados reais (telefone, e-mail, serviços) se estes mudarem.
- **WhatsApp** — número fixo `5592991564219`, usado em vários lugares por `wa.me` (não centralizado numa única constante em todos os pontos — checar antes de trocar o número).

## Convenções / coisas a saber antes de mexer

- É tudo um arquivo só: ao editar, localizar a seção certa por `<section id="...">` ou pelo nome da função JS antes de fazer mudanças pontuais.
- CSS usa custom properties em `:root` (`--navy`, `--teal`, `--cyan`, `--cream`, etc.) — reaproveitar essas variáveis em vez de hardcodar cores novas.
- `.gitignore` exclui `material/`, `*.zip`, rascunhos de design e `*.docx` (pedidos de alteração) — esses não fazem parte do site publicado, não assumir que existem no repo.
- Repo git local: cloná­do de `https://github.com/lucasalmeida80/acecalculos.git`, branch `main`.

## Próximos passos combinados

Vamos trabalhar em melhorias incrementais neste site e, mais adiante, criar uma **landing page nova** (provavelmente um arquivo/seção separada, a definir).
