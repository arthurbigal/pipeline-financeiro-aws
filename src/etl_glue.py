import boto3
import json
import pandas as pd
from io import BytesIO

BUCKET_NAME = "arthur-financeiro-raw-data"
RAW_PREFIX = "raw/"
PROCESSED_PREFIX = "processed/"

s3 = boto3.client("s3")


def listar_arquivos_raw():
    #Lista todos os arquivos .json dentro da pasta raw/ no S3.
    paginator = s3.get_paginator("list_objects_v2")
    arquivos = []

    for pagina in paginator.paginate(Bucket=BUCKET_NAME, Prefix=RAW_PREFIX):
        for obj in pagina.get("Contents", []):
            if obj["Key"].endswith(".json"):
                arquivos.append(obj["Key"])

    return arquivos


def carregar_dados(chaves):
    #Baixa e junta todos os JSONs num único DataFrame.
    todas_linhas = []

    for chave in chaves:
        resposta = s3.get_object(Bucket=BUCKET_NAME, Key=chave)
        conteudo = json.loads(resposta["Body"].read())

        ticker = conteudo["ticker"]
        for registro in conteudo["registros"]:
            registro["ticker"] = ticker
            todas_linhas.append(registro)

    df = pd.DataFrame(todas_linhas)
    df["data"] = pd.to_datetime(df["data"])

    #Remove duplicatas (caso a Lambda tenha rodado mais de uma vez no mesmo dia)
    df = df.drop_duplicates(subset=["ticker", "data"])

    return df


def calcular_metricas(df):
    #Calcula variação diária, média móvel e volatilidade por ativo.
    df = df.sort_values(["ticker", "data"])

    #groupby + transform aplica o cálculo separadamente para cada ticker,
    #sem misturar dados de ativos diferentes
    df["variacao_diaria_pct"] = df.groupby("ticker")["fechamento"].pct_change() * 100

    df["media_movel_5d"] = (
        df.groupby("ticker")["fechamento"]
        .transform(lambda x: x.rolling(window=5, min_periods=1).mean())
    )

    df["volatilidade_5d"] = (
        df.groupby("ticker")["variacao_diaria_pct"]
        .transform(lambda x: x.rolling(window=5, min_periods=1).std())
    )

    #Arredonda as métricas calculadas para 2 casas decimais -- os preços
    #originais (abertura, fechamento, etc.) já vêm limpos do yfinance
    df["variacao_diaria_pct"] = df["variacao_diaria_pct"].round(2)
    df["media_movel_5d"] = df["media_movel_5d"].round(2)
    df["volatilidade_5d"] = df["volatilidade_5d"].round(2)

    return df


def salvar_processado(df):
    """Salva o DataFrame em Parquet no S3, particionado por ticker."""
    for ticker, grupo in df.groupby("ticker"):
        #Remove a coluna "ticker" antes de salvar -- ela já fica implícita
        #no caminho da partição (ticker=XXXX/), então mantê-la dentro do
        #arquivo também causaria conflito de coluna duplicada no Athena.
        grupo = grupo.drop(columns=["ticker"])

        buffer = BytesIO()
        grupo.to_parquet(buffer, index=False, engine="pyarrow")
        buffer.seek(0)

        chave = f"{PROCESSED_PREFIX}ticker={ticker}/dados.parquet"
        s3.put_object(Bucket=BUCKET_NAME, Key=chave, Body=buffer.getvalue())
        print(f"Salvo: {chave} ({len(grupo)} linhas)")


def main():
    print("Listando arquivos brutos...")
    arquivos = listar_arquivos_raw()
    print(f"{len(arquivos)} arquivos encontrados.")

    print("Carregando e consolidando dados...")
    df = carregar_dados(arquivos)

    print("Calculando métricas...")
    df = calcular_metricas(df)

    print("Salvando dados processados...")
    salvar_processado(df)

    print("ETL concluído!")


if __name__ == "__main__":
    main()