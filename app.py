import re
import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Financeiro", page_icon="💰", layout="wide")
st.title("💰 Controlo Financeiro")
st.markdown("---")

# --- 2. CONEXÃO E FUNÇÕES DE APOIO ---
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

def limpar_valor(valor):
    """Converte 'R$ 1.200,50' ou '$-' para float 1200.50"""
    if isinstance(valor, str):
        # Remove caracteres de moeda e espaços
        valor = valor.replace('R$', '').replace('$', '').replace(' ', '')
        # Remove pontos de milhar e troca vírgula por ponto
        valor = valor.replace('.', '').replace(',', '.')
        # Trata traços ou vazios como zero
        if not valor or valor == '-' or valor.strip() == '': 
            return 0.0
    return float(valor) if valor else 0.0

# --- 3. CARREGAMENTO ESTRUTURADO (CONTAS) ---
def carregar_contas():
    try:
        client = conectar_gsheets()
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = client.open_by_url(sheet_url)
        worksheet = sh.worksheet("CONTAS_A_PAGAR")
        data = worksheet.get_all_values()
        
        # Limpeza padrão para tabela vertical
        headers = data[0]
        indices = [i for i, h in enumerate(headers) if h.strip() != ""]
        headers_validos = [headers[i] for i in indices]
        dados_limpos = [[linha[i] for i in indices] for linha in data[1:]]
        
        df = pd.DataFrame(dados_limpos, columns=headers_validos)
        
        if 'Valor' in df.columns:
            df['Valor'] = df['Valor'].apply(limpar_valor)
            df = df[df['Valor'] > 0]
            
        return df
    except Exception as e:
        st.error(f"Erro ao ler CONTAS_A_PAGAR: {e}")
        return pd.DataFrame()

# --- 4. CARREGAMENTO MATRICIAL (VR) - VERSÃO SMART ---
def carregar_vr():
    """
    Lê a aba VR, procura automaticamente onde estão os meses
    e transforma em lista vertical.
    """
    try:
        client = conectar_gsheets()
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = client.open_by_url(sheet_url)
        worksheet = sh.worksheet("VR") # Certifique-se que a aba chama "VR"
        
        # Pega todos os dados brutos
        data = worksheet.get_all_values()
        
        if not data:
            return pd.DataFrame()

        # 1. TENTA DESCOBRIR O ANO NO TÍTULO (LINHA 1)
        titulo = str(data[0]).join(" ") # Junta tudo da primeira linha
        match_ano = re.search(r'202\d', str(data[0])) # Procura 2020 a 2029
        ano_detectado = match_ano.group(0) if match_ano else "2026" # Padrão 2026 se não achar

        # 2. PROCURA A LINHA DOS MESES (CABEÇALHO)
        header_index = -1
        headers = []
        
        # Procura nas primeiras 10 linhas onde está "Janeiro"
        for i, row in enumerate(data[:10]):
            row_str = [str(c).strip() for c in row] # Limpa espaços
            if "Janeiro" in row_str:
                header_index = i
                headers = row_str
                break
        
        if header_index == -1:
            st.error("Não encontrei a coluna 'Janeiro' na aba VR. Verifique se o nome está correto.")
            return pd.DataFrame()

        # Filtra colunas de Meses
        meses_validos = [
            "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
        ]
        
        # Mapeia onde está cada mês (Ex: Janeiro é coluna 0, Fevereiro é coluna 1...)
        mapa_colunas = {h: i for i, h in enumerate(headers) if h in meses_validos}
        
        registros = []
        
        # 3. EXTRAI OS DADOS
        # Começa a ler na linha seguinte ao cabeçalho
        for linha in data[header_index + 1:]:
            # Pula linha de Totais ou vazias
            primeira_celula = str(linha[0]).lower()
            if "total" in primeira_celula or "totais" in primeira_celula:
                continue
                
            # Varre cada mês encontrado
            for mes, col_idx in mapa_colunas.items():
                if col_idx < len(linha):
                    valor_bruto = linha[col_idx]
                    valor_limpo = limpar_valor(valor_bruto)
                    
                    if valor_limpo > 0:
                        registros.append({
                            "Mês": mes,
                            "Ano": ano_detectado,
                            "Valor": valor_limpo,
                            "Categoria": "Refeição", # Categoria padrão para VR
                            "Descrição": "Gasto VR",
                            "Status": "Pago" # VR é débito, então está pago
                        })
        
        df = pd.DataFrame(registros)
        return df

    except Exception as e:
        st.error(f"Erro técnico ao ler aba VR: {e}")
        return pd.DataFrame()

# --- CARREGAMENTO GERAL ---
df_contas = carregar_contas()
df_vr = carregar_vr()

# --- FILTROS GLOBAIS ---
st.sidebar.header("Filtros")

# Unificação de anos e meses para o filtro
anos_unicos = sorted(list(set(df_contas.get('Ano', [])).union(set(df_vr.get('Ano', [])))), reverse=True)
if not anos_unicos:
    st.warning("Nenhum dado encontrado.")
    st.stop()

ano_sel = st.sidebar.selectbox("Ano", anos_unicos)

# Mapeamento para garantir ordem cronológica dos meses no filtro
ordem_meses = {
    'Janeiro': 1, 'Fevereiro': 2, 'Março': 3, 'Abril': 4, 'Maio': 5, 'Junho': 6,
    'Julho': 7, 'Agosto': 8, 'Setembro': 9, 'Outubro': 10, 'Novembro': 11, 'Dezembro': 12,
    'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12
}

meses_contas = df_contas[df_contas['Ano'] == ano_sel]['Mês'].unique() if 'Mês' in df_contas.columns else []
meses_vr = df_vr[df_vr['Ano'] == ano_sel]['Mês'].unique() if 'Mês' in df_vr.columns else []
meses_unicos = list(set(list(meses_contas) + list(meses_vr)))

# Ordena os meses usando o mapa
meses_unicos.sort(key=lambda x: ordem_meses.get(x, 99))

mes_sel = st.sidebar.selectbox("Mês", meses_unicos)

# --- INTERFACE DE ABAS ---
tab1, tab2 = st.tabs(["💸 Contas Bancárias", "🍔 Vale Refeição"])

# === ABA 1: CONTAS ===
with tab1:
    st.subheader("Finanças Pessoais")
    if not df_contas.empty:
        df_c_filtrado = df_contas[(df_contas['Ano'] == ano_sel) & (df_contas['Mês'] == mes_sel)]
        
        if not df_c_filtrado.empty:
            total = df_c_filtrado['Valor'].sum()
            # Tratamento robusto para Status (case insensitive)
            if 'Status' in df_c_filtrado.columns:
                pago = df_c_filtrado[df_c_filtrado['Status'].astype(str).str.lower() == 'pago']['Valor'].sum()
                pendente = df_c_filtrado[df_c_filtrado['Status'].astype(str).str.lower() == 'pendente']['Valor'].sum()
            else:
                pago, pendente = 0, 0

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Gasto", f"R$ {total:,.2f}")
            c2.metric("Pago", f"R$ {pago:,.2f}")
            c3.metric("Pendente", f"R$ {pendente:,.2f}")
            
            st.divider()
            
            g1, g2 = st.columns(2)
            with g1:
                if 'Categoria' in df_c_filtrado.columns:
                    fig = px.pie(df_c_filtrado, values='Valor', names='Categoria', hole=0.4)
                    st.plotly_chart(fig, use_container_width=True)
            with g2:
                if 'Status' in df_c_filtrado.columns:
                    fig2 = px.bar(df_c_filtrado, x='Status', y='Valor', color='Status')
                    st.plotly_chart(fig2, use_container_width=True)
            
            # Tabela com cores
            def estilo_status(val):
                if isinstance(val, str):
                    v = val.lower()
                    if 'pago' in v: return 'background-color: #c6efce; color: #006100'
                    if 'pendente' in v: return 'background-color: #ffeb9c; color: #9c5700'
                return ''
            
            cols_ver = [c for c in ['Data', 'Descrição', 'Categoria', 'Valor', 'Status'] if c in df_c_filtrado.columns]
            st.dataframe(df_c_filtrado[cols_ver].style.map(estilo_status, subset=['Status'] if 'Status' in df_c_filtrado.columns else None), use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados para este período.")

# === ABA 2: VR ===
with tab2:
    st.subheader(f"Gastos VR - {mes_sel}/{ano_sel}")
    
    if not df_vr.empty:
        # Filtro Específico para VR
        df_vr_filtrado = df_vr[(df_vr['Ano'] == str(ano_sel)) & (df_vr['Mês'] == mes_sel)]
        
        if not df_vr_filtrado.empty:
            total_vr = df_vr_filtrado['Valor'].sum()
            qtd_compras = len(df_vr_filtrado)
            media_vr = total_vr / qtd_compras if qtd_compras > 0 else 0
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Gasto", f"R$ {total_vr:,.2f}")
            k2.metric("Qtd. Refeições", f"{qtd_compras}")
            k3.metric("Ticket Médio", f"R$ {media_vr:,.2f}")
            
            st.divider()
            
            # Gráfico de barras simples para visualizar os gastos individuais
            # Como não temos "Dia" exato na sua tabela de VR (apenas valores soltos), 
            # criei um índice numérico para mostrar a sequência de gastos.
            df_vr_filtrado = df_vr_filtrado.reset_index()
            fig_vr = px.bar(df_vr_filtrado, y='Valor', title="Sequência de Gastos no Mês")
            st.plotly_chart(fig_vr, use_container_width=True)
            
            with st.expander("Ver Extrato Detalhado"):
                st.dataframe(df_vr_filtrado[['Mês', 'Valor', 'Categoria']], use_container_width=True)
        else:
            st.info(f"Sem gastos lançados no VR em {mes_sel}.")
    else:
        st.warning("Não foi possível carregar a tabela VR ou ela está vazia.")
