from datetime import datetime
from backend import carregar_editais_do_banco, raspar_e_atualizar
import streamlit as st

st.set_page_config(
    page_title="Radar de Concursos SP", page_icon="🎯", layout="wide"
)

st.title("🎯 Radar Multi-Fonte de Concursos — SP & Nacional")
st.caption(
    "Agregador ETL (PCI Sudeste + PCI Nacional + Concursos no Brasil) |"
    f" Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
)

with st.sidebar:
  st.header("⚙️ Motor de Varredura")

  if st.button("🚀 Varrer Fontes e Atualizar Banco", use_container_width=True):
    with st.spinner("Varrendo portais e filtrando duplicatas..."):
      try:
        novos = raspar_e_atualizar()
        if novos > 0:
          st.success(f"Sucesso! {novos} edital(is) inédito(s) gravado(s).")
        else:
          st.info("Varredura concluída. Nenhum edital inédito encontrado hoje.")
        st.rerun()
      except Exception as e:
        st.error(f"Erro durante a varredura: {e}")

  st.divider()
  st.header("🔍 Filtros Inteligentes")

  apenas_novos = st.toggle("🆕 Mostrar apenas capturados hoje", value=False)
  ordenar_salario = st.toggle("💰 Ordenar pelo maior salário", value=False)

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

try:
  df = carregar_editais_do_banco()
except Exception as e:
  st.error(f"Erro ao ler banco de dados: {e}")
  st.stop()

if not df.empty:
  df_filtrado = df.copy()
  hoje_str = datetime.now().strftime("%Y-%m-%d")

  if apenas_novos:
    df_filtrado = df_filtrado[
        df_filtrado["Data de Registro"].str.startswith(hoje_str)
    ]

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

  if ordenar_salario and "Salário Max" in df_filtrado.columns:
    df_filtrado = df_filtrado.sort_values(by="Salário Max", ascending=False)

  def formatar_orgao(row):
    if str(row["Data de Registro"]).startswith(hoje_str):
      return f'<span class="badge-novo">NOVO</span> {row["Órgão / Edital"]}'
    return row["Órgão / Edital"]

  df_filtrado["Órgão / Edital"] = df_filtrado.apply(formatar_orgao, axis=1)
  df_filtrado["Acesso"] = df_filtrado["Url"].apply(
      lambda x: f'<a href="{x}" target="_blank" class="btn-abrir">Abrir ↗</a>'
  )

  colunas_exibir = [
      "Órgão / Edital",
      "Fonte",
      "UF",
      "Cargos, Vagas e Salário",
      "Prazo",
      "Data de Registro",
      "Acesso",
  ]
  df_exibicao = df_filtrado[
      [c for c in colunas_exibir if c in df_filtrado.columns]
  ]

  col1, col2, col3 = st.columns(3)
  col1.metric("Total Consolidado no Banco", len(df))
  col2.metric("Exibidos no Filtro Atual", len(df_exibicao))
  novos_hoje = df["Data de Registro"].str.startswith(hoje_str).sum()
  col3.metric("Novos Capturados Hoje", int(novos_hoje))

  st.divider()

  tabela_html = df_exibicao.to_html(escape=False, index=False)
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
  st.info(
      "Banco de dados pronto e vazio. Clique em '🚀 Varrer Fontes e Atualizar"
      " Banco' na barra lateral esquerda para iniciar a coleta."
  )