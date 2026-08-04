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

## Desenvolvimento local

```bash
python3 -m http.server 8080
```

Abrir http://localhost:8080 — servir via HTTP é necessário porque o `fetch` do `vau.json` e da API do BC não funciona com `file://`.

## Atualização mensal do VAU

No início de cada mês, quando a nova competência é publicada:

1. Adicionar o bloco do novo mês no topo de `periodos` no `vau.json`
2. Atualizar `periodoAtual`
3. Subir o `vau.json` para a hospedagem
