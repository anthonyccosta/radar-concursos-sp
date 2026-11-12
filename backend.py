import sqlite3
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests
import pandas as pd

DB_PATH = "concursos.db"
TERMOS_BUSCA = [
    "escrevente",
    "tribunal de justiça",
    "tj-sp",
    "tjsp",
    "oficial de justiça",
]


def inicializar_banco():
  """Cria a tabela no SQLite se ela ainda não existir."""
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS editais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            orgao TEXT UNIQUE,
            uf TEXT,
            detalhes TEXT,
            prazo TEXT,
            url TEXT,
            criado_em TEXT
        )
    """)
  conn.commit()
  conn.close()


def salvar_no_banco(dados):
  """Insere novos editais ou ignora se o órgão já estiver cadastrado."""
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  novos = 0

  for item in dados:
    try:
      cursor.execute(
          """
                INSERT INTO editais (orgao, uf, detalhes, prazo, url, criado_em)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
          (
              item["orgao"],
              item["uf"],
              item["detalhes"],
              item["prazo"],
              item["url"],
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          ),
      )
      novos += 1
    except sqlite3.IntegrityError:
      # Se o edital já existir no banco (orgao UNIQUE), ignora para não duplicar
      pass

  conn.commit()
  conn.close()
  return novos


def raspar_e_atualizar():
  """Conecta na internet, raspa os editais e salva no SQLite."""
  inicializar_banco()
  url = "https://www.pciconcursos.com.br/concursos/sudeste/"
  dados_coletados = []

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
        uf = uf_span.get_text(strip=True) if uf_span else "SP/Sudeste"

        if uf in ["SP", "BR", ""]:
          dados_coletados.append({
              "orgao": orgao,
              "uf": uf if uf else "SP/Nacional",
              "detalhes": detalhes_texto,
              "prazo": prazo_texto,
              "url": url_concurso,
          })
  except Exception as e:
    print(f"Erro na raspagem: {e}")

  novos_inseridos = salvar_no_banco(dados_coletados)
  return novos_inseridos


def carregar_editais_do_banco():
  """Lê os editais diretamente do SQLite para exibir no site."""
  inicializar_banco()
  conn = sqlite3.connect(DB_PATH)
  query = """
        SELECT orgao AS 'Órgão / Edital', 
               uf AS 'UF', 
               detalhes AS 'Cargos, Vagas e Salário', 
               prazo AS 'Prazo', 
               url AS 'Url',
               criado_em AS 'Data de Registro'
        FROM editais
        ORDER BY id DESC
    """
  df = pd.read_sql_query(query, conn)
  conn.close()
  return df