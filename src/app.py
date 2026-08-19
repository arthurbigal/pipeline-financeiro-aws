import streamlit as st
import pandas as pd
import plotly.express as px

BUCKET_NAME = "arthur-financeiro-raw-data"
PROCESSED_PATH = f"s3://{BUCKET_NAME}/processed/"

# Configuração da página -- precisa ser a primeira chamada do Streamlit
st.set_page_config(page_title="Pipeline Financeiro AWS", layout="wide")

# ---- Credenciais AWS ----
# Localmente, o boto3/pandas usam as credenciais do "aws configure" automaticamente.
# No Streamlit Cloud, não existe esse arquivo local -- por isso, se as credenciais
# estiverem cadastradas em st.secrets (configurado no site do Streamlit Cloud,
# nunca no código), nós montamos um dicionário para passar explicitamente ao
# pandas na hora de ler o S3.
storage_options = {}
if "aws" in st.secrets:
    storage_options = {
        "key": st.secrets["aws"]["access_key_id"],
        "secret": st.secrets["aws"]["secret_access_key"],
    }


@st.cache_data(ttl=3600)  # guarda o resultado em cache por 1h, evita reler o S3 toda hora
def carregar_dados():
    """Lê todos os arquivos Parquet particionados por ticker no S3."""
    df = pd.read_parquet(PROCESSED_PATH, storage_options=storage_options)
    df["data"] = pd.to_datetime(df["data"])
    return df


# ---- Carregamento ----
st.title("📊 Pipeline de Dados Financeiros — AWS")
st.caption("Dados coletados via yfinance, processados com AWS Glue, armazenados no S3")

with st.spinner("Carregando dados do S3..."):
    df = carregar_dados()

# ---- Filtro lateral ----
st.sidebar.header("Filtros")
tickers_disponiveis = sorted(df["ticker"].unique())
tickers_selecionados = st.sidebar.multiselect(
    "Selecione os ativos",
    options=tickers_disponiveis,
    default=tickers_disponiveis[:3]  # mostra os 3 primeiros por padrão
)

df_filtrado = df[df["ticker"].isin(tickers_selecionados)]

# ---- Métricas resumo (cards no topo) ----
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Ativos monitorados", len(tickers_disponiveis))

with col2:
    variacao_media = df_filtrado["variacao_diaria_pct"].mean()
    st.metric("Variação média (selecionados)", f"{variacao_media:.2f}%")

with col3:
    periodo_dias = (df["data"].max() - df["data"].min()).days
    st.metric("Período de dados", f"{periodo_dias} dias")

# ---- Gráfico 1: Evolução de preço ----
st.subheader("Evolução do preço de fechamento")
fig_preco = px.line(
    df_filtrado,
    x="data",
    y="fechamento",
    color="ticker",
    labels={"data": "Data", "fechamento": "Preço de Fechamento", "ticker": "Ativo"}
)
st.plotly_chart(fig_preco, use_container_width=True)

# ---- Gráfico 2: Ranking de variação média ----
st.subheader("Ranking de variação média no período")
ranking = (
    df.groupby("ticker")["variacao_diaria_pct"]
    .mean()
    .round(2)
    .sort_values(ascending=False)
    .reset_index()
)
fig_ranking = px.bar(
    ranking,
    x="ticker",
    y="variacao_diaria_pct",
    color="variacao_diaria_pct",
    color_continuous_scale="RdYlGn",
    labels={"ticker": "Ativo", "variacao_diaria_pct": "Variação Média (%)"}
)
st.plotly_chart(fig_ranking, use_container_width=True)

# ---- Tabela detalhada ----
st.subheader("Dados detalhados")
st.dataframe(
    df_filtrado[["ticker", "data", "fechamento", "variacao_diaria_pct", "media_movel_5d", "volatilidade_5d"]]
    .sort_values("data", ascending=False),
    use_container_width=True
)