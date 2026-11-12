import re
import sqlite3
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests
import pandas as pd

DB_PATH = "concursos.db"


def inicializar_banco():
  """Cria a tabela no SQLite e garante auto-migração caso a estrutura antiga exista."""
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()

  # Verifica se a tabela existe com a estrutura antiga (sem a coluna 'chave_unica')
  cursor.execute("PRAGMA table_info(editais)")
  colunas_existentes = [col[1] for col in cursor.fetchall()]

  if colunas_existentes and "chave_unica" not in colunas_existentes:
    cursor.execute("DROP TABLE editais")

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS editais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave_unica TEXT UNIQUE,
            fonte TEXT,
            orgao TEXT,
            uf TEXT,
            detalhes TEXT,
            salario_max REAL,
            prazo TEXT,
            url TEXT,
            criado_em TEXT
        )
    """)
  conn.commit()
  conn.close()

def extrair_maior_salario(texto):
  """Usa Regex para capturar o maior valor em R$ dentro da string de detalhes."""
  valores = re.findall(r"R\$\s?([\d\.]+,\d{2})", texto)
  if not valores:
    return 0.0
  numeros = [float(v.replace(".", "").replace(",", ".")) for v in valores]
  return max(numeros)


def salvar_no_banco(dados):
  """Insere apenas editais inéditos no banco e retorna a contagem exata de novos registros."""
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  novos = 0

  for item in dados:
    # Normaliza o nome do órgão (tudo maiúsculo e sem espaços extras) para impedir duplicata
    chave = re.sub(r"\s+", " ", item["orgao"]).strip().upper()
    salario = extrair_maior_salario(item["detalhes"])

    try:
      cursor.execute(
          """
                INSERT INTO editais (chave_unica, fonte, orgao, uf, detalhes, salario_max, prazo, url, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
          (
              chave,
              item["fonte"],
              item["orgao"],
              item["uf"],
              item["detalhes"],
              salario,
              item["prazo"],
              item["url"],
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          ),
      )
      novos += 1
    except sqlite3.IntegrityError:
      # Já existe no banco: ignora silenciosamente
      pass

  conn.commit()
  conn.close()
  return novos


def raspar_pci(url, nome_fonte, filtrar_sp=True):
  """Motor de raspagem para páginas do PCI Concursos (Sudeste e Nacional)."""
  coletados = []
  try:
    r = requests.get(url, impersonate="chrome120", timeout=20)
    if r.status_code == 200:
      sopa = BeautifulSoup(r.text, "html.parser")
      cards = sopa.find_all("div", class_="ca")

      for card in cards:
        link_tag = card.find("a", href=True)
        if not link_tag:
          continue

        orgao = link_tag.get_text(strip=True)
        url_concurso = link_tag["href"]

        detalhes_div = card.find("div", class_="cd")
        detalhes_texto = (
            detalhes_div.get_text(" | ", strip=True)
            if detalhes_div
            else "Sem detalhes"
        )

        prazo_div = card.find("div", class_="ce")
        prazo_texto = (
            prazo_div.get_text(" ", strip=True)
            if prazo_div
            else "Consultar edital"
        )

        uf_span = card.find("div", class_="cc")
        uf = uf_span.get_text(strip=True) if uf_span else ""

        if not filtrar_sp or uf in ["SP", "BR", ""]:
          coletados.append({
              "fonte": nome_fonte,
              "orgao": orgao,
              "uf": uf if uf else "Nacional",
              "detalhes": detalhes_texto,
              "prazo": prazo_texto,
              "url": url_concurso,
          })
  except Exception as e:
    print(f"Erro na fonte {nome_fonte}: {e}")
  return coletados


def raspar_concursos_no_brasil():
  """Segunda fonte independente: Portal Concursos no Brasil (Seção SP)."""
  url = "https://concursosnobrasil.com/concursos/sp/"
  coletados = []
  try:
    r = requests.get(url, impersonate="chrome120", timeout=20)
    if r.status_code == 200:
      sopa = BeautifulSoup(r.text, "html.parser")
      linhas = sopa.select("table tbody tr")
      for tr in linhas:
        colunas = tr.find_all("td")
        if len(colunas) >= 2:
          link_tag = colunas[0].find("a", href=True)
          if not link_tag:
            continue
          orgao = link_tag.get_text(strip=True)
          url_concurso = link_tag["href"]
          vagas_texto = colunas[1].get_text(strip=True)
          coletados.append({
              "fonte": "Concursos no Brasil",
              "orgao": orgao,
              "uf": "SP",
              "detalhes": f"Vagas previstas/abertas: {vagas_texto}",
              "prazo": "Verificar edital",
              "url": url_concurso,
          })
  except Exception as e:
    print(f"Erro na fonte Concursos no Brasil: {e}")
  return coletados


def raspar_e_atualizar():
  """Orquestrador multi-fonte: varre as 3 fontes e persiste apenas o que é inédito."""
  inicializar_banco()
  todos_dados = []

  # Fonte 1: PCI Concursos Sudeste (foco SP)
  todos_dados.extend(
      raspar_pci(
          "https://www.pciconcursos.com.br/concursos/sudeste/",
          "PCI Sudeste",
          filtrar_sp=True,
      )
  )
  # Fonte 2: PCI Concursos Nacional (Órgãos Federais com lotação em SP)
  todos_dados.extend(
      raspar_pci(
          "https://www.pciconcursos.com.br/concursos/nacional/",
          "PCI Nacional",
          filtrar_sp=False,
      )
  )
  # Fonte 3: Concursos no Brasil (SP)
  todos_dados.extend(raspar_concursos_no_brasil())

  return salvar_no_banco(todos_dados)


def carregar_editais_do_banco():
  """Lê a base consolidada do SQLite."""
  inicializar_banco()
  conn = sqlite3.connect(DB_PATH)
  query = """
        SELECT orgao AS 'Órgão / Edital',
               fonte AS 'Fonte',
               uf AS 'UF',
               detalhes AS 'Cargos, Vagas e Salário',
               salario_max AS 'Salário Max',
               prazo AS 'Prazo',
               url AS 'Url',
               criado_em AS 'Data de Registro'
        FROM editais
        ORDER BY id DESC
    """
  df = pd.read_sql_query(query, conn)
  conn.close()
  return df