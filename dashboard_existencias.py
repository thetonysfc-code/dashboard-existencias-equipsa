import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# =========================
# CONFIGURACION
# =========================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zbw_mEEZeoh3Qxy-2d20Qhaogo_tTX3kbC7oHOqKLBg/edit?gid=0#gid=0"
CREDENCIALES = "credenciales_google.json"
HOJA_REGISTROS = "Registros"

st.set_page_config(
    page_title="Dashboard Existencias EQUIPSA",
    page_icon="📊",
    layout="wide"
)

# =========================
# ESTILOS
# =========================
st.markdown("""
<style>
    .main-title {
        font-size: 38px;
        font-weight: 800;
        margin-bottom: 0px;
    }
    .subtitle {
        font-size: 16px;
        color: #666;
        margin-bottom: 25px;
    }
    .metric-card {
        background: #f7f7f7;
        padding: 18px;
        border-radius: 14px;
        border: 1px solid #e6e6e6;
    }
</style>
""", unsafe_allow_html=True)

# =========================
# GOOGLE SHEETS
# =========================
@st.cache_data(ttl=60)
def cargar_datos():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file(CREDENCIALES, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet(HOJA_REGISTROS)
    datos = ws.get_all_records()

    df = pd.DataFrame(datos)

    if df.empty:
        return df

    # Normalizar nombres de columnas esperados
    df.columns = [str(c).strip() for c in df.columns]

    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
        df["Mes"] = df["Fecha"].dt.strftime("%Y-%m")
        df["Dia"] = df["Fecha"].dt.date

    if "Numero Parte" in df.columns:
        df["Numero Parte"] = df["Numero Parte"].astype(str).str.strip().str.upper()

    if "Agente" in df.columns:
        df["Agente"] = df["Agente"].astype(str).str.strip()

    if "Tipo" in df.columns:
        df["Tipo"] = df["Tipo"].astype(str).str.strip()

    return df


def tabla_top(df, n=20):
    if df.empty:
        return pd.DataFrame(columns=["Ranking", "Numero Parte", "Veces", "Tipo"])

    top = (
        df.groupby(["Numero Parte", "Tipo"])
        .size()
        .reset_index(name="Veces")
        .sort_values("Veces", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )
    top.insert(0, "Ranking", range(1, len(top) + 1))
    return top


def resumen_mensual(df):
    if df.empty or "Mes" not in df.columns:
        return pd.DataFrame(columns=["Mes", "Numero Parte", "Tipo", "Veces"])

    return (
        df.groupby(["Mes", "Numero Parte", "Tipo"])
        .size()
        .reset_index(name="Veces")
        .sort_values(["Mes", "Veces"], ascending=[False, False])
    )


def resumen_agentes(df):
    if df.empty:
        return pd.DataFrame(columns=["Agente", "Solicitudes"])

    return (
        df.groupby("Agente")
        .size()
        .reset_index(name="Solicitudes")
        .sort_values("Solicitudes", ascending=False)
    )


# =========================
# UI
# =========================
st.markdown('<div class="main-title">📊 Dashboard de Faltantes EQUIPSA</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Resumen de números de parte solicitados y sin stock desde Google Sheets.</div>', unsafe_allow_html=True)

try:
    df = cargar_datos()
except FileNotFoundError:
    st.error("No encontré credenciales_google.json. Pon ese archivo en la misma carpeta que este dashboard.")
    st.stop()
except Exception as e:
    st.error(f"No pude cargar datos desde Google Sheets: {e}")
    st.stop()

if df.empty:
    st.warning("Todavía no hay registros en la hoja Registros.")
    st.stop()

# Sidebar filtros
st.sidebar.header("Filtros")

meses = sorted(df["Mes"].dropna().unique(), reverse=True) if "Mes" in df.columns else []
mes_sel = st.sidebar.multiselect("Mes", meses, default=meses[:1] if meses else [])

agentes = sorted(df["Agente"].dropna().unique()) if "Agente" in df.columns else []
agente_sel = st.sidebar.multiselect("Agente", agentes)

tipos = sorted(df["Tipo"].dropna().unique()) if "Tipo" in df.columns else []
tipo_sel = st.sidebar.multiselect("Tipo", tipos)

busqueda_np = st.sidebar.text_input("Buscar NP")

filtrado = df.copy()

if mes_sel:
    filtrado = filtrado[filtrado["Mes"].isin(mes_sel)]

if agente_sel:
    filtrado = filtrado[filtrado["Agente"].isin(agente_sel)]

if tipo_sel:
    filtrado = filtrado[filtrado["Tipo"].isin(tipo_sel)]

if busqueda_np:
    filtrado = filtrado[filtrado["Numero Parte"].str.contains(busqueda_np.upper(), na=False)]

# Metricas
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Solicitudes totales", len(filtrado))

with col2:
    st.metric("NP únicos", filtrado["Numero Parte"].nunique())

with col3:
    st.metric("Agentes", filtrado["Agente"].nunique())

with col4:
    top_np = tabla_top(filtrado, 1)
    st.metric("NP más pedido", top_np.iloc[0]["Numero Parte"] if not top_np.empty else "-")

st.divider()

# Top 20
st.subheader("🔥 Top 20 piezas más pedidas y sin stock")
top20 = tabla_top(filtrado, 20)
st.dataframe(top20, use_container_width=True, hide_index=True)

if not top20.empty:
    st.bar_chart(top20.set_index("Numero Parte")["Veces"])

st.divider()

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("👤 Solicitudes por agente")
    agentes_df = resumen_agentes(filtrado)
    st.dataframe(agentes_df, use_container_width=True, hide_index=True)
    if not agentes_df.empty:
        st.bar_chart(agentes_df.set_index("Agente")["Solicitudes"])

with col_b:
    st.subheader("❌ Solicitudes por tipo")
    tipo_df = (
        filtrado.groupby("Tipo")
        .size()
        .reset_index(name="Solicitudes")
        .sort_values("Solicitudes", ascending=False)
    )
    st.dataframe(tipo_df, use_container_width=True, hide_index=True)
    if not tipo_df.empty:
        st.bar_chart(tipo_df.set_index("Tipo")["Solicitudes"])

st.divider()

st.subheader("📅 Resumen mensual")
mensual = resumen_mensual(filtrado)
st.dataframe(mensual, use_container_width=True, hide_index=True)

st.divider()

st.subheader("📋 Registros filtrados")
columnas = [c for c in ["Fecha", "Agente", "Numero Parte", "Tipo"] if c in filtrado.columns]
st.dataframe(filtrado[columnas].sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)

st.caption("Tip: el dashboard se actualiza cada 60 segundos. También puedes presionar Rerun/Recargar en Streamlit.")
