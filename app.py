from datetime import datetime
from backend import carregar_editais_do_banco, raspar_e_atualizar
import streamlit as st

st.set_page_config(
    page_title="Radar de Concursos SP", page_icon="🎯", layout="wide"
)

st.title("🎯 Radar de Editais e Concursos — SP & Região")
st.caption(
    "Arquitetura Modular (Python + SQLite + Streamlit) | Atualizado em:"
    f" {datetime.now().strftime('%d/%m/%Y %H:%M')}"
)

df = carregar_editais_do_banco()

with st.sidebar:
  st.header("⚙️ Painel de Controle")

  if st.button("🚀 Buscar Novos Editais na Web", use_container_width=True):
    with st.spinner("Conectando e raspando editais..."):
      novos = raspar_e_atualizar()
      st.success(f"Varredura concluída! {novos} novo(s) edital(is) adicionado(s).")
      st.rerun()

  st.divider()
  st.header("🔍 Filtros de Busca")
  termo_livre = st.text_input(
      "Buscar por Cidade ou Cargo:",
      placeholder="Ex: Botucatu, Bauru, TI, Escrevente...",
  )
  filtro_rapido = st.multiselect(
      "Atalhos de Perfil:",
      [
          "Informática",
          "Tecnologia",
          "Analista",
          "Escrevente",
          "Técnico",
          "Superior",
          "Médio",
          "Prefeitura",
      ],
      default=[],
  )

if not df.empty:
  df_filtrado = df.copy()
  hoje_str = datetime.now().strftime("%Y-%m-%d")

  if termo_livre:
    mascara = df_filtrado["Órgão / Edital"].str.contains(
        termo_livre, case=False, na=False
    ) | df_filtrado["Cargos, Vagas e Salário"].str.contains(
        termo_livre, case=False, na=False
    )
    df_filtrado = df_filtrado[mascara]

  if filtro_rapido:
    padrao = "|".join(filtro_rapido)
    mascara_rapida = df_filtrado["Órgão / Edital"].str.contains(
        padrao, case=False, na=False
    ) | df_filtrado["Cargos, Vagas e Salário"].str.contains(
        padrao, case=False, na=False
    )
    df_filtrado = df_filtrado[mascara_rapida]

  # Adiciona badge visual se o registro foi capturado na data de hoje
  def formatar_orgao(row):
    if str(row["Data de Registro"]).startswith(hoje_str):
      return f'<span class="badge-novo">NOVO</span> {row["Órgão / Edital"]}'
    return row["Órgão / Edital"]

  df_filtrado["Órgão / Edital"] = df_filtrado.apply(formatar_orgao, axis=1)

  # Botão corrigido sem quebra de linha (white-space: nowrap)
  df_filtrado["Acesso"] = df_filtrado["Url"].apply(
      lambda x: f'<a href="{x}" target="_blank" class="btn-abrir">Abrir ↗</a>'
  )

  col1, col2, col3 = st.columns(3)
  col1.metric("Editais Salvos no Banco", len(df))
  col2.metric("Resultados no Filtro", len(df_filtrado))
  col3.metric("Banco de Dados", "SQLite Online 🗄️")

  st.divider()

  tabela_html = (
      df_filtrado.drop(columns=["Url"])
      .to_html(escape=False, index=False)
  )
  st.html(f"""
    <style>
        table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; }}
        th {{ background-color: #0f172a; color: white; padding: 14px; text-align: left; position: sticky; top: 0; }}
        td {{ padding: 14px; border-bottom: 1px solid #cbd5e1; vertical-align: middle; }}
        tr:hover {{ background-color: #f8fafc; }}
        .btn-abrir {{
            display: inline-block;
            padding: 8px 14px;
            background-color: #2563eb;
            color: #ffffff !important;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            white-space: nowrap;
        }}
        .btn-abrir:hover {{ background-color: #1d4ed8; }}
        .badge-novo {{
            background-color: #16a34a;
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            margin-right: 6px;
        }}
    </style>
    <div style="max-height: 550px; overflow-y: auto; border: 1px solid #cbd5e1; border-radius: 8px;">
        {tabela_html}
    </div>
    """)
else:
  st.warning(
      "O banco de dados está vazio. Clique no botão '🚀 Buscar Novos Editais na"
      " Web' na barra lateral!"
  )