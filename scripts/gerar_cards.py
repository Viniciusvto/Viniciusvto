#!/usr/bin/env python3
"""
Gera os cards de estatísticas do perfil como arquivos SVG dentro do próprio
repositório, para que o GitHub os sirva diretamente.

Sem dependências externas e sem serviços de terceiros: usa apenas a API pública
do GitHub, autenticada com o GITHUB_TOKEN que o Actions injeta automaticamente.

Uso:
    python scripts/gerar_cards.py --user ViniciusVto --out assets
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from html import escape
from typing import Any

API = "https://api.github.com"

# Paleta tokyonight (mesma do github-readme-stats)
TEMA = {
    "bg": "#1a1b27",
    "borda": "#2c2f45",
    "titulo": "#70a5fd",
    "texto": "#38bdae",
    "icone": "#bf91f3",
    "destaque": "#c0caf5",
}

# Cores oficiais do GitHub Linguist para as linguagens mais comuns.
CORES_LINGUAGEM = {
    "Python": "#3572A5",
    "Jupyter Notebook": "#DA5B0B",
    "Java": "#b07219",
    "C#": "#178600",
    "Batchfile": "#C1F12E",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "C": "#555555",
    "C++": "#f34b7d",
    "Shell": "#89e051",
    "PHP": "#4F5D95",
    "Ruby": "#701516",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Kotlin": "#A97BFF",
    "Swift": "#F05138",
    "Dart": "#00B4AB",
    "R": "#198CE7",
    "SQL": "#e38c00",
    "TeX": "#3D6117",
    "Makefile": "#427819",
    "Dockerfile": "#384d54",
    "Vue": "#41b883",
}
COR_PADRAO = "#858585"

FONTE = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"


# --------------------------------------------------------------------------
# Acesso à API
# --------------------------------------------------------------------------

def _requisitar(url: str, token: str | None) -> Any:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "perfil-cards-script")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def buscar(caminho: str, token: str | None) -> Any:
    """
    GET na API do GitHub.

    O GITHUB_TOKEN do Actions é limitado ao repositório. Se ele for recusado em
    algum endpoint de usuário, refaz a chamada sem autenticação — os dados são
    públicos de qualquer forma.
    """
    url = caminho if caminho.startswith("http") else f"{API}{caminho}"
    try:
        return _requisitar(url, token)
    except urllib.error.HTTPError as e:
        if token and e.code in (401, 403, 404):
            print(f"aviso: token recusado em {url} ({e.code}); repetindo sem autenticação",
                  file=sys.stderr)
            try:
                return _requisitar(url, None)
            except urllib.error.HTTPError as e2:
                e = e2
        detalhe = e.read().decode("utf-8", "replace")[:200]
        raise SystemExit(f"Erro {e.code} ao buscar {url}: {detalhe}") from e


def buscar_todos_repos(user: str, token: str | None) -> list[dict]:
    """Percorre todas as páginas de repositórios públicos do usuário."""
    repos: list[dict] = []
    pagina = 1
    while True:
        lote = buscar(f"/users/{user}/repos?per_page=100&page={pagina}&type=owner", token)
        if not lote:
            break
        repos.extend(lote)
        if len(lote) < 100:
            break
        pagina += 1
    return repos


def coletar_dados(user: str, token: str | None, incluir_forks: bool) -> dict:
    perfil = buscar(f"/users/{user}", token)
    repos = buscar_todos_repos(user, token)

    proprios = [r for r in repos if incluir_forks or not r.get("fork")]

    estrelas = sum(r.get("stargazers_count", 0) for r in proprios)
    forks = sum(r.get("forks_count", 0) for r in proprios)

    # Soma de bytes por linguagem em todos os repositórios considerados.
    bytes_por_linguagem: dict[str, int] = {}
    for r in proprios:
        dados = buscar(f"/repos/{user}/{r['name']}/languages", token)
        for linguagem, quantidade in dados.items():
            bytes_por_linguagem[linguagem] = bytes_por_linguagem.get(linguagem, 0) + quantidade

    return {
        "nome": perfil.get("name") or perfil.get("login"),
        "login": perfil.get("login"),
        "repos_publicos": perfil.get("public_repos", 0),
        "seguidores": perfil.get("followers", 0),
        "seguindo": perfil.get("following", 0),
        "estrelas": estrelas,
        "forks": forks,
        "desde": (perfil.get("created_at") or "")[:4],
        "linguagens": bytes_por_linguagem,
    }


# --------------------------------------------------------------------------
# Renderização dos SVGs
# --------------------------------------------------------------------------

def moldura(largura: int, altura: int, titulo: str, corpo: str) -> str:
    """Cartão base: fundo arredondado, borda e título."""
    return f"""<svg width="{largura}" height="{altura}" viewBox="0 0 {largura} {altura}"
     fill="none" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="{escape(titulo)}">
  <title>{escape(titulo)}</title>
  <rect x="0.5" y="0.5" width="{largura - 1}" height="{altura - 1}" rx="6"
        fill="{TEMA['bg']}" stroke="{TEMA['borda']}"/>
  <text x="25" y="35" font-family="{FONTE}" font-size="18" font-weight="600"
        fill="{TEMA['titulo']}">{escape(titulo)}</text>
{corpo}
</svg>
"""


def card_estatisticas(d: dict) -> str:
    linhas = [
        ("Repositórios públicos", d["repos_publicos"]),
        ("Estrelas recebidas", d["estrelas"]),
        ("Forks recebidos", d["forks"]),
        ("Seguidores", d["seguidores"]),
        ("No GitHub desde", d["desde"]),
    ]

    partes = []
    y = 75
    for rotulo, valor in linhas:
        partes.append(
            f'  <circle cx="30" cy="{y - 5}" r="4" fill="{TEMA["icone"]}"/>\n'
            f'  <text x="46" y="{y}" font-family="{FONTE}" font-size="14"'
            f' fill="{TEMA["texto"]}">{escape(rotulo)}</text>\n'
            f'  <text x="360" y="{y}" font-family="{FONTE}" font-size="14"'
            f' font-weight="700" text-anchor="end"'
            f' fill="{TEMA["destaque"]}">{valor}</text>'
        )
        y += 30

    titulo = f"Estatísticas de {d['nome']}"
    return moldura(380, 215, titulo, "\n".join(partes))


def formatar_percentual(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def card_linguagens(d: dict, quantidade: int) -> str:
    ordenadas = sorted(d["linguagens"].items(), key=lambda kv: kv[1], reverse=True)
    principais = ordenadas[:quantidade]
    total = sum(v for _, v in principais)

    if total == 0:
        corpo = (
            f'  <text x="25" y="75" font-family="{FONTE}" font-size="14"'
            f' fill="{TEMA["texto"]}">Nenhuma linguagem encontrada.</text>'
        )
        return moldura(380, 120, "Linguagens mais usadas", corpo)

    partes = []

    # Barra proporcional única, no topo.
    largura_barra = 330.0
    x = 25.0
    partes.append('  <g>')
    for i, (linguagem, quantidade_bytes) in enumerate(principais):
        fatia = largura_barra * quantidade_bytes / total
        cor = CORES_LINGUAGEM.get(linguagem, COR_PADRAO)
        # Cantos arredondados só nas pontas da barra completa.
        raio = 5 if i in (0, len(principais) - 1) else 0
        partes.append(
            f'    <rect x="{x:.2f}" y="55" width="{max(fatia, 0.5):.2f}" height="10"'
            f' rx="{raio}" fill="{cor}"/>'
        )
        x += fatia
    partes.append('  </g>')

    # Legenda em coluna única: nome à esquerda, percentual alinhado à direita.
    y = 100
    for linguagem, quantidade_bytes in principais:
        cor = CORES_LINGUAGEM.get(linguagem, COR_PADRAO)
        pct = formatar_percentual(100 * quantidade_bytes / total)
        partes.append(
            f'  <circle cx="32" cy="{y - 4}" r="5" fill="{cor}"/>\n'
            f'  <text x="46" y="{y}" font-family="{FONTE}" font-size="13"'
            f' fill="{TEMA["texto"]}">{escape(linguagem)}</text>\n'
            f'  <text x="355" y="{y}" font-family="{FONTE}" font-size="13"'
            f' font-weight="600" text-anchor="end"'
            f' fill="{TEMA["destaque"]}">{pct}%</text>'
        )
        y += 26

    altura = y + 6
    return moldura(380, altura, "Linguagens mais usadas", "\n".join(partes))


# --------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Gera os cards SVG do perfil.")
    p.add_argument("--user", required=True, help="Login do GitHub")
    p.add_argument("--out", default="assets", help="Pasta de saída")
    p.add_argument("--langs", type=int, default=6, help="Quantas linguagens listar")
    p.add_argument("--incluir-forks", action="store_true",
                   help="Contar também repositórios que são forks")
    args = p.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or None
    dados = coletar_dados(args.user, token, args.incluir_forks)

    os.makedirs(args.out, exist_ok=True)
    saidas = {
        "estatisticas.svg": card_estatisticas(dados),
        "linguagens.svg": card_linguagens(dados, args.langs),
    }
    for nome, conteudo in saidas.items():
        caminho = os.path.join(args.out, nome)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)
        print(f"gerado: {caminho}")

    print(json.dumps({k: v for k, v in dados.items() if k != "linguagens"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
