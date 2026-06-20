import pandas as pd
import streamlit as st
import gspread
import plotly.express as px
from google.oauth2.service_account import Credentials

# =========================
# CONFIGURACIÓN
# =========================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zbw_mEEZeoh3Qxy-2d20Qhaogo_tTX3kbC7oHOqKLBg/edit?gid=0#gid=0"
CREDENCIALES_LOCALES = "credenciales_google.json"
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
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    .main-title {
        font-size: 38px;
        font-weight: 800;
        margin-bottom: 0px;
        color: #111827;
    }
    .subtitle {
        font-size: 16px;
        color: #6b7280;
        margin-bottom: 25px;
    }
    .section-title {
        font-size: 22px;
        font-weight: 700;
        margin-top: 10px;
        margin-bottom: 8px;
    }
    div[data-testid="stMetric"] {
        background: #f8fafc;
        padding: 18px;
        border-radius: 16px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
</style>
""", unsafe_allow_html=True)

# =========================
# GOOGLE SHEETS
# =========================
def obtener_credenciales(scopes):
    """
    En local usa credenciales_google.json.
    En Streamlit Cloud usa st.secrets["gcp_service_account"].
    """
    try:
        if "gcp_service_account" in st.secrets:
            return Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]),
                scopes=scopes
            )
    except Exception:
        pass

    return Credentials.from_service_account_file(
        CREDENCIALES_LOCALES,
        scopes=scopes
    )


@st.cache_data(ttl=60)
def cargar_datos():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = obtener_credenciales(scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet(HOJA_REGISTROS)

    datos = ws.get_all_records()
    df = pd.DataFrame(datos)

    if df.empty:
        return df

    df.columns = [str(c).strip() for c in df.columns]

    columnas_requeridas = ["Fecha", "Agente", "Numero Parte", "Tipo"]
    faltantes = [c for c in columnas_requeridas if c not in df.columns]
    if faltantes:
        st.error(f"Faltan columnas en la hoja Registros: {faltantes}")
        st.stop()

    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df = df.dropna(subset=["Fecha"])

    df["Mes"] = df["Fecha"].dt.strftime("%Y-%m")
    df["Dia"] = df["Fecha"].dt.date

    df["Numero Parte"] = df["Numero Parte"].astype(str).str.strip().str.upper()
    df["Agente"] = df["Agente"].astype(str).str.strip()
    df["Tipo"] = df["Tipo"].astype(str).str.strip()

    df = df[df["Numero Parte"].ne("")]
    df = df[df["Agente"].ne("")]
    df = df[df["Tipo"].ne("")]

    return df


# =========================
# TABLAS / RESÚMENES
# =========================
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
    if df.empty:
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


def resumen_tipo(df):
    if df.empty:
        return pd.DataFrame(columns=["Tipo", "Solicitudes"])

    return (
        df.groupby("Tipo")
        .size()
        .reset_index(name="Solicitudes")
        .sort_values("Solicitudes", ascending=False)
    )


def solicitudes_por_dia(df):
    if df.empty:
        return pd.DataFrame(columns=["Dia", "Solicitudes"])

    return (
        df.groupby("Dia")
        .size()
        .reset_index(name="Solicitudes")
        .sort_values("Dia")
    )


# =========================
# UI PRINCIPAL
# =========================
st.markdown('<div class="main-title">📊 Dashboard de Faltantes EQUIPSA</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Monitoreo de números de parte solicitados y sin stock desde Google Sheets. '
    'Actualización automática cada 60 segundos.</div>',
    unsafe_allow_html=True
)

try:
    df = cargar_datos()
except FileNotFoundError:
    st.error(
        "No encontré credenciales_google.json. En local pon ese archivo junto a este dashboard. "
        "En Streamlit Cloud configura los Secrets."
    )
    st.stop()
except Exception as e:
    st.error(f"No pude cargar datos desde Google Sheets: {e}")
    st.stop()

if df.empty:
    st.warning("Todavía no hay registros en la hoja Registros.")
    st.stop()

# =========================
# FILTROS
# =========================
st.sidebar.header("🔎 Filtros")

meses = sorted(df["Mes"].dropna().unique(), reverse=True)
mes_sel = st.sidebar.multiselect("Mes", meses, default=meses[:1] if meses else [])

agentes = sorted(df["Agente"].dropna().unique())
agente_sel = st.sidebar.multiselect("Agente", agentes)

tipos = sorted(df["Tipo"].dropna().unique())
tipo_sel = st.sidebar.multiselect("Tipo", tipos)

busqueda_np = st.sidebar.text_input("Buscar número de parte")

filtrado = df.copy()

if mes_sel:
    filtrado = filtrado[filtrado["Mes"].isin(mes_sel)]

if agente_sel:
    filtrado = filtrado[filtrado["Agente"].isin(agente_sel)]

if tipo_sel:
    filtrado = filtrado[filtrado["Tipo"].isin(tipo_sel)]

if busqueda_np:
    filtrado = filtrado[
        filtrado["Numero Parte"].str.contains(busqueda_np.upper().strip(), na=False)
    ]

# =========================
# KPIs
# =========================
top20 = tabla_top(filtrado, 20)
agentes_df = resumen_agentes(filtrado)
tipo_df = resumen_tipo(filtrado)

total_solicitudes = len(filtrado)
np_unicos = filtrado["Numero Parte"].nunique()
top_np = top20.iloc[0]["Numero Parte"] if not top20.empty else "-"
top_np_veces = int(top20.iloc[0]["Veces"]) if not top20.empty else 0
top_agente = agentes_df.iloc[0]["Agente"] if not agentes_df.empty else "-"
top_agente_veces = int(agentes_df.iloc[0]["Solicitudes"]) if not agentes_df.empty else 0

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📦 Solicitudes", total_solicitudes)

with col2:
    st.metric("🔩 NP únicos", np_unicos)

with col3:
    st.metric("👑 NP más pedido", top_np, f"{top_np_veces} solicitudes")

with col4:
    st.metric("🏆 Agente top", top_agente, f"{top_agente_veces} solicitudes")

st.divider()

# =========================
# TOP 20
# =========================
st.markdown('<div class="section-title">🔥 Top 20 piezas más pedidas y sin stock</div>', unsafe_allow_html=True)

col_top_table, col_top_chart = st.columns([1.1, 1.4])

with col_top_table:
    st.dataframe(top20, use_container_width=True, hide_index=True)

with col_top_chart:
    if not top20.empty:
        fig_top = px.bar(
            top20.sort_values("Veces"),
            x="Veces",
            y="Numero Parte",
            color="Tipo",
            orientation="h",
            text="Veces",
            title="Ranking por solicitudes"
        )
        fig_top.update_layout(
            height=520,
            yaxis_title="Número de parte",
            xaxis_title="Solicitudes",
            legend_title="Tipo"
        )
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("No hay datos para mostrar.")

st.divider()

# =========================
# AGENTES Y TIPOS
# =========================
col_a, col_b = st.columns(2)

with col_a:
    st.markdown('<div class="section-title">👤 Solicitudes por agente</div>', unsafe_allow_html=True)
    st.dataframe(agentes_df, use_container_width=True, hide_index=True)

    if not agentes_df.empty:
        fig_agentes = px.bar(
            agentes_df.sort_values("Solicitudes"),
            x="Solicitudes",
            y="Agente",
            orientation="h",
            text="Solicitudes",
            title="Solicitudes capturadas por agente"
        )
        fig_agentes.update_layout(height=420, yaxis_title="Agente", xaxis_title="Solicitudes")
        st.plotly_chart(fig_agentes, use_container_width=True)

with col_b:
    st.markdown('<div class="section-title">❌ Solicitudes por tipo</div>', unsafe_allow_html=True)
    st.dataframe(tipo_df, use_container_width=True, hide_index=True)

    if not tipo_df.empty:
        fig_tipo = px.pie(
            tipo_df,
            names="Tipo",
            values="Solicitudes",
            title="Distribución por tipo de faltante",
            hole=0.42
        )
        fig_tipo.update_layout(height=420)
        st.plotly_chart(fig_tipo, use_container_width=True)

st.divider()

# =========================
# TENDENCIA DIARIA
# =========================
st.markdown('<div class="section-title">📈 Tendencia diaria</div>', unsafe_allow_html=True)

dia_df = solicitudes_por_dia(filtrado)

if not dia_df.empty:
    fig_dia = px.line(
        dia_df,
        x="Dia",
        y="Solicitudes",
        markers=True,
        title="Solicitudes por día"
    )
    fig_dia.update_layout(height=380, xaxis_title="Día", yaxis_title="Solicitudes")
    st.plotly_chart(fig_dia, use_container_width=True)
else:
    st.info("No hay datos para tendencia diaria.")

st.divider()

# =========================
# RESUMEN MENSUAL
# =========================
st.markdown('<div class="section-title">📅 Resumen mensual</div>', unsafe_allow_html=True)
mensual = resumen_mensual(filtrado)
st.dataframe(mensual, use_container_width=True, hide_index=True)

st.divider()

# =========================
# REGISTROS
# =========================
st.markdown('<div class="section-title">📋 Registros filtrados</div>', unsafe_allow_html=True)

columnas = [c for c in ["Fecha", "Agente", "Numero Parte", "Tipo"] if c in filtrado.columns]
registros_filtrados = filtrado[columnas].sort_values("Fecha", ascending=False)

st.dataframe(registros_filtrados, use_container_width=True, hide_index=True)

csv = registros_filtrados.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="⬇️ Descargar registros filtrados CSV",
    data=csv,
    file_name="registros_faltantes_equipsa.csv",
    mime="text/csv"
)

st.caption("Dashboard conectado a Google Sheets. Cache de lectura: 60 segundos.")
