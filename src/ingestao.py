import yfinance as yf
import boto3
import json
from datetime import datetime

BUCKET_NAME = "arthur-financeiro-raw-data"
ATIVOS = ["PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBAS3.SA", "WEGE3.SA",
          "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]

s3 = boto3.client("s3")


def buscar_dados(ticker):
    acao = yf.Ticker(ticker)
    historico = acao.history(period="1mo")

    registros = []
    for data, linha in historico.iterrows():
        registros.append({
            "data": data.strftime("%Y-%m-%d"),
            "abertura": round(linha["Open"], 2),
            "fechamento": round(linha["Close"], 2),
            "maxima": round(linha["High"], 2),
            "minima": round(linha["Low"], 2),
            "volume": int(linha["Volume"])
        })

    return {"ticker": ticker, "registros": registros}


def subir_para_s3(dados, ticker):
    hoje = datetime.now().strftime("%Y-%m-%d")
    caminho = f"raw/{hoje}/{ticker}.json"

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=caminho,
        Body=json.dumps(dados, ensure_ascii=False, indent=2),
        ContentType="application/json"
    )
    print(f"Enviado: {caminho}")


def handler(event, context):
    for ticker in ATIVOS:
        print(f"Buscando dados de {ticker}...")
        dados = buscar_dados(ticker)
        subir_para_s3(dados, ticker)

    print("Concluído! Todos os ativos foram processados.")

    return {
        "statusCode": 200,
        "body": "Ingestão concluída com sucesso"
    }