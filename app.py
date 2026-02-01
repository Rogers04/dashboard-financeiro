import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Financeiro", page_icon="💰", layout="wide")
st.title("💰 Controlo Financeiro Inteligente")
st.markdown("---")

# --- 2. CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource
def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = {
        "type": st.secrets["connections"]["gsheets"]["type"],
        "project_id": st.secrets["connections"]["gsheets"]["project_id"],
        "private_key_id": st.secrets["connections"]["gsheets"]["private_key_id"],
        "private_key": st.secrets["connections"]["gsheets"]["private_key"],
        "client_email": st.secrets["connections"]["gsheets"]["client_email"],
        "client_id": st.secrets["connections"]["gsheets"]["client_id"],
        "auth_uri": st.secrets["connections"]["gsheets"]["auth_uri"],
        "token_uri": st.secrets["connections"]["gsheets"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["connections"]["gsheets"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["connections"]["gsheets"]["client_x509_cert_url"]
    }
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

try:
    client = conectar_gsheets()
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sh = client.open_by_url(sheet_url)
    worksheet = sh.worksheet("CONTAS_A_PAGAR")
    
    data = worksheet.get_all_values()
    
    # CRIAÇÃO DO DATAFRAME COM LIMPEZA DE COLUNAS VAZIAS
    # Pega a primeira linha como cabeçalho
    headers = data[0]
    # Remove colunas que têm cabeçalho vazio ""
    indices_validos = [i for i, h in enumerate(headers) if h.strip() != ""]
    headers_validos = [headers[i] for i in indices_validos]
    
    # Filtra os dados para pegar apenas as colunas válidas
    dados_limpos = [[linha[i] for i in indices_validos] for linha in data[1:]]
    
    df = pd.DataFrame(dados_limpos, columns=headers_validos)
    
except Exception as e:
    st.error(f"Erro ao conectar: {e}")
    st.stop()

# --- 3. LIMPEZA DE DADOS (ETL) ---
def limpar_valor(valor):
    if isinstance(valor, str):
        valor = valor.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
        if not valor or valor == '-': return 0.0
    return float(valor) if valor else 0.0

try:
    # Verifica colunas essenciais
    required_cols = ['Valor', 'Mês', 'Ano', 'Status', 'Categoria']
    missing = [col for col in required_cols if col not in df.columns]
    
    if missing:
        st.error(f"Colunas faltando na planilha: {missing}. Verifique se os nomes na linha 1 estão exatos.")
        st.stop()

    df['Valor'] = df['Valor'].apply(limpar_valor)
    # Remove linhas onde o Valor é zero (linhas vazias que sobraram)
    df = df[df['Valor'] > 0] 

except Exception as e:
    st.error(f"Erro no tratamento: {e}")
    st.stop()

# --- 4. FILTROS ---
st.sidebar.header("Filtros")
lista_anos = sorted(df['Ano'].unique(), reverse=True)

if not lista_anos:
    st.warning("A planilha parece estar vazia ou sem anos preenchidos.")
    st.stop()
    
ano_sel = st.sidebar.selectbox("Ano", lista_anos)
df_ano = df[df['Ano'] == ano_sel]
mes_sel = st.sidebar.selectbox("Mês", df_ano['Mês'].unique())

# Filtra
df_filtrado = df[(df['Ano'] == ano_sel) & (df['Mês'] == mes_sel)]

if df_filtrado.empty:
    st.warning("Sem dados para este período.")
    st.stop()

# --- 5. DASHBOARD ---
total = df_filtrado['Valor'].sum()
pago = df_filtrado[df_filtrado['Status'].str.lower() == 'pago']['Valor'].sum()
pendente = df_filtrado[df_filtrado['Status'].str.lower() == 'pendente']['Valor'].sum()

c1, c2, c3 = st.columns(3)
c1.metric("Total", f"R$ {total:,.2f}")
c2.metric("Pago", f"R$ {pago:,.2f}")
c3.metric("Pendente", f"R$ {pendente:,.2f}")

st.markdown("---")

g1, g2 = st.columns(2)
with g1:
    # Agrupa antes de plotar para evitar duplicatas visuais
    df_pizza = df_filtrado.groupby('Categoria')['Valor'].sum().reset_index()
    fig = px.pie(df_pizza, values='Valor', names='Categoria', hole=0.4)
    st.plotly_chart(fig, use_container_width=True)

with g2:
    df_barras = df_filtrado.groupby('Status')['Valor'].sum().reset_index()
    fig2 = px.bar(df_barras, x='Status', y='Valor', color='Status')
    st.plotly_chart(fig2, use_container_width=True)

with st.expander("Ver Dados Detalhados"):
    st.dataframe(df_filtrado)


### O que mudou? (A lógica da correção)

## dicionei este bloco de "Saneamento Básico" logo depois de ler os dados:


# Remove colunas que têm cabeçalho vazio ""
indices_validos = [i for i, h in enumerate(headers) if h.strip() != ""]
headers_validos = [headers[i] for i in indices_validos]
df = pd.DataFrame(dados_limpos, columns=headers_validos)