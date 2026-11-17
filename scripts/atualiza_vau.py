#!/usr/bin/python3
"""
Virada de mês automática do VAU (acecalculos.com.br).

Fluxo: baixa a tabela SERO -> confere se a competência do mês já está
"(Ativado)" -> extrai os valores das 27 UFs -> sanity check de variação
uniforme (corrige célula copiada de outra categoria, aborta em anomalia
desconhecida) -> grava vau.json -> confere que o arquivo no servidor não
foi mexido -> upload FTPS -> verifica no ar -> commit + push.

Idempotente: se o vau.json já tem o mês corrente, sai sem fazer nada.
Pensado para rodar via launchd todo dia 3 (e repetir diariamente até
a SERO publicar). Só depende de: /usr/bin/python3, curl + ~/.netrc
(host sh00048.hostgator.com.br), git com SSH sem senha.

O launchd roda a partir de um clone próprio em ~/.acecalculos (ver
scripts/instalar_agendamento.sh), porque o macOS bloqueia processos em
segundo plano de ler ~/Documents. O script dá git pull antes e git push
depois, então a cópia em Documentos só precisa de um `git pull` para
receber o mês novo.

Uso manual:
  scripts/atualiza_vau.py                 # mês corrente
  scripts/atualiza_vau.py --dry-run       # não sobe nem commita
  scripts/atualiza_vau.py --mes 2026-11 --forcar --dry-run   # reprocessa
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import urllib.request
from collections import OrderedDict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAU_JSON = os.path.join(REPO, "vau.json")
FONTE = "https://www.tabelavau.seroassessoria.com.br/tabela_vau.php"
FTP_HOST = "sh00048.hostgator.com.br"
URL_PUBLICA = "https://acecalculos.com.br/vau.json"
LOG = os.path.expanduser("~/Library/Logs/acecalculos-vau.log")

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
CATS = {"RU": "uni", "RM": "multi", "COM": "comercial",
        "GI": "galpao", "CP": "popular", "CHP": "conjunto"}
ORDEM = ["uni", "multi", "comercial", "galpao", "popular", "conjunto"]
TOLERANCIA = 0.005  # 0,5% de desvio em relação à variação do mês


class Abortar(Exception):
    pass


def log(msg):
    linha = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(linha, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except OSError:
        pass


def notificar(titulo, texto):
    """Notificação do macOS; falha silenciosa se não houver sessão gráfica."""
    if not shutil.which("osascript"):
        return
    txt = texto.replace("\\", "\\\\").replace('"', '\\"')
    tit = titulo.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(["osascript", "-e",
                    f'display notification "{txt}" with title "{tit}"'],
                   capture_output=True)


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, **kw)
    if r.returncode != 0:
        raise Abortar(f"comando falhou ({' '.join(cmd)}): {r.stderr.strip()}")
    return r.stdout


def md5(b):
    return hashlib.md5(b).hexdigest()


def baixar_html():
    req = urllib.request.Request(FONTE, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def competencia_ativa(html):
    m = re.search(r"(" + "|".join(MESES) + r") de (\d{4})[^<]*\(Ativado\)", html, re.I)
    if not m:
        raise Abortar("não achei a competência '(Ativado)' no HTML da SERO")
    return f"{int(m.group(2)):04d}-{MESES.index(m.group(1).lower()) + 1:02d}"


def extrair(html):
    dados = {}
    for uf, cat, val in re.findall(
            r'name="val_vau_([A-Z]{2})_([A-Z]+)"[^>]*value="([^"]*)"', html):
        v = float(val.replace(".", "").replace(",", "."))
        dados.setdefault(uf, {})[CATS[cat]] = v
    if len(dados) != 27 or any(len(d) != 6 for d in dados.values()):
        raise Abortar(f"parse incompleto: {len(dados)} UFs, "
                      f"{[u for u, d in dados.items() if len(d) != 6]} sem 6 categorias")
    return dados


def sanity_check(novo, base):
    """Variação mensal é nacional (Sinapi): todas as células devem subir
    pelo mesmo percentual. Célula fora do padrão que repete o valor de outra
    categoria da mesma UF é erro de cópia da SERO -> corrigir. Qualquer outra
    anomalia -> abortar."""
    razoes = {(uf, k): novo[uf][k] / base[uf][k] for uf in novo for k in ORDEM}
    mediana = statistics.median(razoes.values())
    correcoes = []
    for (uf, k), r in razoes.items():
        if abs(r / mediana - 1) <= TOLERANCIA:
            continue
        outras = [c for c in ORDEM if c != k and novo[uf][c] == novo[uf][k]]
        if k in ("popular", "conjunto") and outras == [
                "conjunto" if k == "popular" else "popular"]:
            outras = []  # popular e conjunto são iguais por definição
        if not outras:
            raise Abortar(f"anomalia não reconhecida em {uf}/{k}: "
                          f"{base[uf][k]} -> {novo[uf][k]} ({r - 1:+.2%}, "
                          f"mês {mediana - 1:+.2%})")
        corrigido = round(base[uf][k] * mediana, 2)
        correcoes.append(f"{uf} {k}: SERO {novo[uf][k]:.2f} (igual a {outras[0]}) "
                         f"-> {corrigido:.2f}")
        novo[uf][k] = corrigido
    return mediana, correcoes


def serializar(data):
    linhas = ["{", f'  "periodoAtual": "{data["periodoAtual"]}",',
              f'  "nota": {json.dumps(data["nota"], ensure_ascii=False)},',
              '  "periodos": {']
    chaves = list(data["periodos"])
    for i, p in enumerate(chaves):
        per = data["periodos"][p]
        linhas += [f'    "{p}": {{', f'      "descricao": "{per["descricao"]}",',
                   '      "vau": {']
        ufs = list(per["vau"])
        for j, uf in enumerate(ufs):
            d = per["vau"][uf]
            corpo = ", ".join(f'"{k}": {d[k]:.2f}' for k in ORDEM)
            linhas.append(f'        "{uf}": {{ {corpo} }}' + ("," if j < len(ufs) - 1 else ""))
        linhas += ["      }", "    }" + ("," if i < len(chaves) - 1 else "")]
    linhas += ["  }", "}"]
    return "\n".join(linhas) + "\n"


def descricao(mes):
    ano, m = mes.split("-")
    return f"{MESES[int(m) - 1].capitalize()}/{ano}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", help="competência alvo YYYY-MM (padrão: mês corrente)")
    ap.add_argument("--forcar", action="store_true", help="reprocessa mesmo se já existir")
    ap.add_argument("--dry-run", action="store_true", help="não sobe nem commita")
    a = ap.parse_args()
    alvo = a.mes or dt.date.today().strftime("%Y-%m")

    # Sincroniza com o GitHub antes de ler: o clone do launchd e a cópia de
    # trabalho em Documentos são repositórios diferentes.
    if not a.dry_run:
        sh(["git", "pull", "-q", "--ff-only", "origin", "main"])

    with open(VAU_JSON, encoding="utf-8") as f:
        data = json.load(f, object_pairs_hook=OrderedDict)
    if alvo in data["periodos"] and not a.forcar:
        log(f"{alvo} já está no vau.json; nada a fazer")
        return 0

    if sh(["git", "status", "--porcelain", "--", "vau.json"]).strip():
        raise Abortar("vau.json tem alterações locais não commitadas; resolva antes")

    html = baixar_html()
    ativa = competencia_ativa(html)
    if ativa != alvo:
        log(f"SERO ainda em {ativa}; alvo {alvo} não publicado. Tento de novo depois")
        if dt.date.today().day >= 8:
            notificar("VAU ACE", f"SERO ainda não publicou {descricao(alvo)}. Vou tentando todo dia.")
        return 0

    novo = extrair(html)
    anteriores = sorted(k for k in data["periodos"] if k < alvo)
    if not anteriores:
        raise Abortar("não há período anterior para o sanity check")
    base = data["periodos"][anteriores[-1]]["vau"]
    mediana, correcoes = sanity_check(novo, base)
    log(f"{descricao(alvo)}: variação do mês {mediana - 1:+.2%} sobre {anteriores[-1]}")
    for c in correcoes:
        log("CORREÇÃO " + c)

    periodos = OrderedDict()
    periodos[alvo] = OrderedDict([
        ("descricao", descricao(alvo)),
        ("vau", OrderedDict((uf, OrderedDict((k, novo[uf][k]) for k in ORDEM))
                            for uf in sorted(novo)))])
    for k, v in data["periodos"].items():
        if k != alvo:
            periodos[k] = v
    data["periodoAtual"] = alvo
    data["periodos"] = periodos
    conteudo = serializar(data).encode("utf-8")
    json.loads(conteudo)  # garante JSON válido

    if a.dry_run:
        caminho = VAU_JSON + ".dry-run"
        with open(caminho, "wb") as f:
            f.write(conteudo)
        log(f"dry-run: resultado gravado em {caminho}; nada subiu")
        return 0

    # Servidor ainda igual ao último commit? (ninguém mexeu pelo cPanel)
    head = sh(["git", "show", "HEAD:vau.json"]).encode("utf-8")
    remoto = subprocess.run(["curl", "-sS", "--netrc", "--ssl-reqd",
                             f"ftp://{FTP_HOST}/vau.json"], capture_output=True)
    if remoto.returncode != 0:
        raise Abortar("não consegui baixar o vau.json do servidor: " + remoto.stderr.decode())
    if md5(remoto.stdout) != md5(head):
        raise Abortar("vau.json no servidor difere do último commit; alguém mexeu pelo cPanel. Não vou sobrescrever")

    with open(VAU_JSON, "wb") as f:
        f.write(conteudo)
    try:
        sh(["curl", "-sS", "--netrc", "--ssl-reqd", "-T", VAU_JSON,
            f"ftp://{FTP_HOST}/vau.json"])
        ok = False
        for _ in range(3):
            cb = int(dt.datetime.now().timestamp())
            try:
                with urllib.request.urlopen(f"{URL_PUBLICA}?cb={cb}", timeout=60) as r:
                    ok = md5(r.read()) == md5(conteudo)
            except OSError:
                ok = False
            if ok:
                break
        if not ok:
            raise Abortar("upload feito, mas a cópia pública não bate com a local")
    except Abortar:
        sh(["git", "checkout", "--", "vau.json"])
        raise

    msg = f"Atualiza VAU para {descricao(alvo)}\n\nFonte: tabela SERO Assessoria. " \
          f"Variação uniforme de {mediana - 1:+.2%} sobre {descricao(anteriores[-1])}."
    if correcoes:
        msg += "\n\nCélulas corrigidas (SERO repetiu valor de outra categoria):\n" + \
               "\n".join("- " + c for c in correcoes)
    msg += "\n\nAutomático via scripts/atualiza_vau.py"
    sh(["git", "add", "vau.json"])
    sh(["git", "commit", "-q", "-m", msg])
    try:
        sh(["git", "push", "-q", "origin", "main"])
        push = "commit + push ok"
    except Abortar as e:
        push = f"site no ar, mas o push falhou: {e}"
        log(push)
    resumo = f"{descricao(alvo)} no ar ({mediana - 1:+.2%}). {push}"
    if correcoes:
        resumo += f" {len(correcoes)} célula(s) corrigida(s), veja o log."
    log(resumo)
    notificar("VAU ACE atualizado", resumo)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Abortar as e:
        log("ABORTADO: " + str(e))
        notificar("VAU ACE: precisa de você", str(e)[:200])
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        log(f"ERRO inesperado: {type(e).__name__}: {e}")
        notificar("VAU ACE: erro", f"{type(e).__name__}: {e}"[:200])
        sys.exit(1)
