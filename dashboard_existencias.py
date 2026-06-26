import os
from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import gspread
import plotly.express as px
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials

# =========================
# CONFIGURACIÓN
# =========================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zbw_mEEZeoh3Qxy-2d20Qhaogo_tTX3kbC7oHOqKLBg/edit?gid=0#gid=0"
CREDENCIALES_LOCALES = "credenciales_google.json"
HOJA_REGISTROS = "Registros"

REFRESH_MS = 60000
CACHE_TTL = 120

st.set_page_config(
    page_title="Dashboard Existencias EQUIPSA",
    page_icon="📊",
    layout="wide"
)

st_autorefresh(
    interval=REFRESH_MS,
    key="actualizacion_dashboard"
)

# =========================
# ESTILOS V2 CORPORATIVO
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(34, 197, 94, 0.10), transparent 28%),
        radial-gradient(circle at top right, rgba(59, 130, 246, 0.12), transparent 30%),
        linear-gradient(135deg, #0b1120 0%, #111827 45%, #020617 100%);
    color: #f8fafc;
}

.block-container {
    padding-top: 1.4rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #020617 100%);
    border-right: 1px solid rgba(148, 163, 184, 0.20);
}

[data-testid="stSidebar"] * {
    color: #e5e7eb;
}

.hero {
    padding: 22px 26px;
    border-radius: 24px;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.76));
    border: 1px solid rgba(148, 163, 184, 0.22);
    box-shadow: 0 18px 60px rgba(0,0,0,0.35);
    margin-bottom: 20px;
}

.hero-title {
    font-size: 38px;
    font-weight: 900;
    letter-spacing: -0.04em;
    color: #ffffff;
    margin-bottom: 4px;
}

.hero-subtitle {
    font-size: 15px;
    color: #cbd5e1;
    margin-bottom: 0;
}

.status-pill {
    display: inline-block;
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(34,197,94,0.15);
    color: #86efac;
    border: 1px solid rgba(34,197,94,0.30);
    font-size: 13px;
    font-weight: 800;
    margin-top: 10px;
}

.kpi-card {
    min-height: 138px;
    padding: 20px 22px;
    border-radius: 22px;
    background: linear-gradient(145deg, rgba(248,250,252,0.98), rgba(226,232,240,0.92));
    border: 1px solid rgba(255,255,255,0.35);
    box-shadow: 0 18px 35px rgba(0,0,0,0.22);
    color: #0f172a;
}

.kpi-label {
    font-size: 14px;
    font-weight: 800;
    color: #334155;
    margin-bottom: 8px;
}

.kpi-value {
    font-size: 33px;
    line-height: 1.05;
    font-weight: 900;
    color: #020617;
    overflow-wrap: anywhere;
}

.kpi-delta {
    display: inline-block;
    margin-top: 12px;
    padding: 5px 10px;
    border-radius: 999px;
    background: #dcfce7;
    color: #15803d;
    font-size: 12px;
    font-weight: 800;
}

.section-card {
    padding: 18px 18px;
    border-radius: 22px;
    background: rgba(15, 23, 42, 0.76);
    border: 1px solid rgba(148, 163, 184, 0.20);
    box-shadow: 0 14px 40px rgba(0,0,0,0.23);
    margin-bottom: 20px;
}

.section-title {
    font-size: 21px;
    font-weight: 900;
    color: #ffffff;
    margin-bottom: 14px;
    letter-spacing: -0.02em;
}

.small-note {
    font-size: 13px;
    color: #94a3b8;
}

div[data-testid="stMetric"] {
    background: rgba(248,250,252,0.96);
    padding: 18px;
    border-radius: 16px;
    border: 1px solid #e5e7eb;
}

div[data-testid="stMetric"] label,
div[data-testid="stMetric"] label p,
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] div {
    color: #111827 !important;
}

[data-testid="stDataFrame"] {
    border-radius: 18px;
    overflow: hidden;
}

hr {
    border-color: rgba(148, 163, 184, 0.18);
}

.stDownloadButton button {
    background: linear-gradient(135deg, #2563eb, #16a34a);
    color: white;
    border: none;
    border-radius: 14px;
    font-weight: 800;
}
</style>
""", unsafe_allow_html=True)


# =========================
# GOOGLE SHEETS
# =========================
def obtener_credenciales(scopes):
    """
    En Streamlit Cloud usa st.secrets["gcp_service_account"].
    En local usa credenciales_google.json.
    """
    if "gcp_service_account" in st.secrets:
        info = dict(st.secrets["gcp_service_account"])

        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")

        return Credentials.from_service_account_info(info, scopes=scopes)

    if os.path.exists(CREDENCIALES_LOCALES):
        return Credentials.from_service_account_file(CREDENCIALES_LOCALES, scopes=scopes)

    raise FileNotFoundError(
        "No encontré credenciales. En Streamlit Cloud configura Secrets como "
        "[gcp_service_account]. En local coloca credenciales_google.json junto al dashboard."
    )


@st.cache_data(ttl=CACHE_TTL)
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
    df["Hora"] = df["Fecha"].dt.hour
    df["Dia Semana"] = df["Fecha"].dt.day_name()

    df["Numero Parte"] = df["Numero Parte"].astype(str).str.strip().str.upper()
    df["Agente"] = df["Agente"].astype(str).str.strip()
    df["Tipo"] = df["Tipo"].astype(str).str.strip()

    df = df[df["Numero Parte"].ne("")]
    df = df[df["Agente"].ne("")]
    df = df[df["Tipo"].ne("")]

    return df


# =========================
# RESÚMENES
# =========================
def tabla_top(df, n=15):
    if df.empty:
        return pd.DataFrame(columns=["Ranking", "Numero Parte", "Veces", "Tipo"])

    top = (
        df.groupby(["Numero Parte", "Tipo"], as_index=False)
        .size()
        .rename(columns={"size": "Veces"})
        .sort_values("Veces", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )

    top["Numero Parte"] = top["Numero Parte"].astype(str)
    top.insert(0, "Ranking", range(1, len(top) + 1))
    return top


def resumen_mensual(df):
    if df.empty:
        return pd.DataFrame(columns=["Mes", "Numero Parte", "Tipo", "Veces"])

    out = (
        df.groupby(["Mes", "Numero Parte", "Tipo"], as_index=False)
        .size()
        .rename(columns={"size": "Veces"})
        .sort_values(["Mes", "Veces"], ascending=[False, False])
    )
    out["Numero Parte"] = out["Numero Parte"].astype(str)
    return out


def resumen_agentes(df):
    if df.empty:
        return pd.DataFrame(columns=["Agente", "Solicitudes"])

    return (
        df.groupby("Agente", as_index=False)
        .size()
        .rename(columns={"size": "Solicitudes"})
        .sort_values("Solicitudes", ascending=False)
    )


def resumen_tipo(df):
    if df.empty:
        return pd.DataFrame(columns=["Tipo", "Solicitudes"])

    return (
        df.groupby("Tipo", as_index=False)
        .size()
        .rename(columns={"size": "Solicitudes"})
        .sort_values("Solicitudes", ascending=False)
    )


def solicitudes_por_dia(df):
    if df.empty:
        return pd.DataFrame(columns=["Dia", "Solicitudes"])

    return (
        df.groupby("Dia", as_index=False)
        .size()
        .rename(columns={"size": "Solicitudes"})
        .sort_values("Dia")
    )


def solicitudes_por_hora(df):
    if df.empty:
        return pd.DataFrame(columns=["Hora", "Solicitudes"])

    base = (
        df.groupby("Hora", as_index=False)
        .size()
        .rename(columns={"size": "Solicitudes"})
        .sort_values("Hora")
    )
    return base


def kpi_card(icon, label, value, delta=None):
    delta_html = f'<div class="kpi-delta">↑ {delta}</div>' if delta else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{icon} {label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def aplicar_layout_plotly(fig, height=420):
    fig.update_layout(
        height=height,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e5e7eb", family="Inter"),
        margin=dict(l=10, r=10, t=55, b=20),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(255,255,255,0.1)",
            borderwidth=0
        )
    )
    return fig


# =========================
# UI PRINCIPAL
# =========================
try:
    df = cargar_datos()
except FileNotFoundError as e:
    st.error(str(e))
    st.info(
        "En Streamlit Cloud ve a App settings → Secrets y pega tus credenciales en formato TOML "
        "con el encabezado [gcp_service_account]."
    )
    st.stop()
except Exception as e:
    st.error(f"No pude cargar datos desde Google Sheets: {e}")
    st.stop()

if df.empty:
    st.warning("Todavía no hay registros en la hoja Registros.")
    st.stop()

ultima_fecha = df["Fecha"].max()
ahora = datetime.now()
minutos_desde_actualizacion = (ahora - ultima_fecha.to_pydatetime()).total_seconds() / 60 if pd.notna(ultima_fecha) else 999
estado_bot = "🟢 ACTIVO" if minutos_desde_actualizacion <= 30 else "🟡 SIN REGISTROS RECIENTES"

st.markdown(
    f"""
    <div class="hero">
        <div class="hero-title">📊 Dashboard de Faltantes EQUIPSA</div>
        <div class="hero-subtitle">
            Inteligencia de faltantes desde WhatsApp + Google Sheets.
            Actualización automática cada {int(REFRESH_MS/1000)} segundos.
        </div>
        <div class="status-pill">{estado_bot} · Último registro: {ultima_fecha.strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>
    """,
    unsafe_allow_html=True
)

# =========================
# FILTROS
# =========================
st.sidebar.markdown("## 🔎 Filtros ejecutivos")

meses = sorted(df["Mes"].dropna().unique(), reverse=True)
mes_sel = st.sidebar.multiselect("Mes", meses, default=meses[:1] if meses else [])

agentes = sorted(df["Agente"].dropna().unique())
agente_sel = st.sidebar.multiselect("Agente", agentes)

tipos = sorted(df["Tipo"].dropna().unique())
tipo_sel = st.sidebar.multiselect("Tipo", tipos)

busqueda_np = st.sidebar.text_input("Buscar número de parte")

fecha_min = df["Fecha"].min().date()
fecha_max = df["Fecha"].max().date()
rango_fechas = st.sidebar.date_input(
    "Rango de fechas",
    value=(fecha_min, fecha_max),
    min_value=fecha_min,
    max_value=fecha_max
)

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

if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
    inicio, fin = rango_fechas
    filtrado = filtrado[
        (filtrado["Fecha"].dt.date >= inicio) &
        (filtrado["Fecha"].dt.date <= fin)
    ]

# =========================
# KPIs
# =========================
top15 = tabla_top(filtrado, 15)
agentes_df = resumen_agentes(filtrado)
tipo_df = resumen_tipo(filtrado)

total_solicitudes = len(filtrado)
np_unicos = filtrado["Numero Parte"].nunique() if not filtrado.empty else 0
top_np = str(top15.iloc[0]["Numero Parte"]) if not top15.empty else "-"
top_np_veces = int(top15.iloc[0]["Veces"]) if not top15.empty else 0
top_agente = str(agentes_df.iloc[0]["Agente"]) if not agentes_df.empty else "-"
top_agente_veces = int(agentes_df.iloc[0]["Solicitudes"]) if not agentes_df.empty else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    kpi_card("📦", "Solicitudes", f"{total_solicitudes:,}", "periodo filtrado")
with col2:
    kpi_card("🔩", "NP únicos", f"{np_unicos:,}", "números distintos")
with col3:
    kpi_card("👑", "NP más solicitado", top_np, f"{top_np_veces} solicitudes")
with col4:
    kpi_card("🏆", "Agente top", top_agente, f"{top_agente_veces} solicitudes")

st.markdown("<br>", unsafe_allow_html=True)

# =========================
# FILA PRINCIPAL: TOP NP + AGENTES
# =========================
col_top, col_agentes = st.columns([1.35, 1])

with col_top:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🏆 Top 15 números de parte faltantes</div>', unsafe_allow_html=True)

    if not top15.empty:
        chart_top = top15.copy()
        chart_top["Numero Parte"] = chart_top["Numero Parte"].astype(str)
        chart_top = chart_top.sort_values("Veces", ascending=True)

        fig_top = px.bar(
            chart_top,
            x="Veces",
            y="Numero Parte",
            color="Tipo",
            orientation="h",
            text="Veces",
            title="Ranking por solicitudes"
        )
        fig_top.update_yaxes(type="category", title="")
        fig_top.update_xaxes(title="Solicitudes")
        fig_top.update_traces(textposition="outside", cliponaxis=False)
        fig_top = aplicar_layout_plotly(fig_top, 500)
        st.plotly_chart(fig_top, width="stretch")
    else:
        st.info("No hay datos para mostrar.")

    st.markdown('</div>', unsafe_allow_html=True)

with col_agentes:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">👥 Ranking por agente</div>', unsafe_allow_html=True)

    if not agentes_df.empty:
        agentes_chart = agentes_df.sort_values("Solicitudes", ascending=True).tail(12)
        fig_agentes = px.bar(
            agentes_chart,
            x="Solicitudes",
            y="Agente",
            orientation="h",
            text="Solicitudes",
            title="Solicitudes capturadas"
        )
        fig_agentes.update_yaxes(title="")
        fig_agentes.update_xaxes(title="Solicitudes")
        fig_agentes.update_traces(textposition="outside", cliponaxis=False)
        fig_agentes = aplicar_layout_plotly(fig_agentes, 500)
        st.plotly_chart(fig_agentes, width="stretch")
    else:
        st.info("No hay agentes para mostrar.")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# FILA 2: TIPO + TENDENCIA
# =========================
col_tipo, col_dia = st.columns([0.85, 1.45])

with col_tipo:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">❌ Distribución por tipo</div>', unsafe_allow_html=True)

    if not tipo_df.empty:
        fig_tipo = px.pie(
            tipo_df,
            names="Tipo",
            values="Solicitudes",
            hole=0.55,
            title="Causa del faltante"
        )
        fig_tipo = aplicar_layout_plotly(fig_tipo, 420)
        st.plotly_chart(fig_tipo, width="stretch")
    else:
        st.info("No hay datos por tipo.")

    st.markdown('</div>', unsafe_allow_html=True)

with col_dia:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📈 Tendencia diaria</div>', unsafe_allow_html=True)

    dia_df = solicitudes_por_dia(filtrado)
    if not dia_df.empty:
        fig_dia = px.area(
            dia_df,
            x="Dia",
            y="Solicitudes",
            markers=True,
            title="Solicitudes por día"
        )
        fig_dia.update_xaxes(title="Día")
        fig_dia.update_yaxes(title="Solicitudes")
        fig_dia = aplicar_layout_plotly(fig_dia, 420)
        st.plotly_chart(fig_dia, width="stretch")
    else:
        st.info("No hay datos para tendencia diaria.")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# FILA 3: ACTIVIDAD POR HORA + TABLAS EJECUTIVAS
# =========================
col_hora, col_tabla_top = st.columns([1, 1.35])

with col_hora:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">⏱️ Actividad por hora</div>', unsafe_allow_html=True)

    hora_df = solicitudes_por_hora(filtrado)
    if not hora_df.empty:
        fig_hora = px.bar(
            hora_df,
            x="Hora",
            y="Solicitudes",
            text="Solicitudes",
            title="Distribución horaria"
        )
        fig_hora.update_xaxes(title="Hora del día", dtick=1)
        fig_hora.update_yaxes(title="Solicitudes")
        fig_hora = aplicar_layout_plotly(fig_hora, 360)
        st.plotly_chart(fig_hora, width="stretch")
    else:
        st.info("No hay datos por hora.")

    st.markdown('</div>', unsafe_allow_html=True)

with col_tabla_top:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📋 Tabla Top 15</div>', unsafe_allow_html=True)
    st.dataframe(top15, width="stretch", hide_index=True, height=360)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# RESUMEN MENSUAL
# =========================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📅 Resumen mensual por NP</div>', unsafe_allow_html=True)
mensual = resumen_mensual(filtrado)
st.dataframe(mensual, width="stretch", hide_index=True, height=360)
st.markdown('</div>', unsafe_allow_html=True)

# =========================
# REGISTROS
# =========================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🔍 Registros filtrados</div>', unsafe_allow_html=True)

columnas = [c for c in ["Fecha", "Agente", "Numero Parte", "Tipo"] if c in filtrado.columns]
registros_filtrados = filtrado[columnas].sort_values("Fecha", ascending=False)

st.dataframe(registros_filtrados, width="stretch", hide_index=True, height=420)

csv = registros_filtrados.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="⬇️ Descargar registros filtrados CSV",
    data=csv,
    file_name="registros_faltantes_equipsa.csv",
    mime="text/csv"
)

st.markdown(
    f'<div class="small-note">Dashboard conectado a Google Sheets · Cache: {CACHE_TTL} segundos · Última lectura visual: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>',
    unsafe_allow_html=True
)
st.markdown('</div>', unsafe_allow_html=True)
