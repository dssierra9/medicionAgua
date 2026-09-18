import requests
import pandas as pd
import numpy as np
import streamlit as st
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Coordenadas fijas de la estación (Santo Domingo, Quebrada Santiago)
LAT_FIJO = 6.542
LON_FIJO = -75.1576

API_BASE_URL = "https://marco.cornare.gov.co/api/v1/estaciones"
LLAVE_FECHA = "level_date"
LLAVE_VALOR = "level"

st.set_page_config(page_title="Nivel de estación — CORNARE", page_icon="🌊", layout="wide")

# ------------------------------------------------------------------
# Funciones
# ------------------------------------------------------------------
def obtener_serie_nivel(codigo_estacion, desde, hasta, calidad=1, timeout=30):
    url = f"{API_BASE_URL}/{codigo_estacion}/nivel"
    params = {"desde": desde, "hasta": hasta, "calidad": calidad}
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout, verify=False)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"HTTP {resp.status_code}"
    except requests.exceptions.RequestException as e:
        return None, f"Error de red: {e}"

def obtener_todas_las_paginas(datos_json, timeout=30):
    registros = list(datos_json.get("values", []))
    siguiente_url = datos_json.get("next")
    while siguiente_url:
        try:
            resp = requests.get(siguiente_url, timeout=timeout, verify=False)
        except requests.exceptions.RequestException:
            break
        if resp.status_code != 200:
            break
        pagina = resp.json()
        registros.extend(pagina.get("values", []))
        siguiente_url = pagina.get("next")
    return registros

def calcular_indice_calidad(df):
    if df.empty or len(df) < 2:
        return 0.0, 0, 0
    df_idx = df.set_index("fecha")
    frecuencia_tipica = df["fecha"].diff().dropna().mode()
    if len(frecuencia_tipica) == 0:
        return 0.0, 0, 0
    frecuencia_tipica = frecuencia_tipica[0]
    rango_completo = pd.date_range(start=df_idx.index.min(), end=df_idx.index.max(), freq=frecuencia_tipica)
    esperados = len(rango_completo)
    huecos = esperados - len(df_idx)
    completitud = max(0.0, 1 - (huecos / esperados)) if esperados > 0 else 0.0
    Q1, Q3 = df["nivel"].quantile(0.25), df["nivel"].quantile(0.75)
    IQR = Q3 - Q1
    lim_inf, lim_sup = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
    es_outlier = (df["nivel"] < lim_inf) | (df["nivel"] > lim_sup) | (df["nivel"] < 0)
    proporcion_outliers = es_outlier.mean()
    indice = (completitud * 0.7 + (1 - proporcion_outliers) * 0.3) * 100
    return round(indice, 1), int(huecos), int(es_outlier.sum())

# ------------------------------------------------------------------
# Sidebar — parámetros
# ------------------------------------------------------------------
st.sidebar.header("Parámetros de tu consulta")
nombre_estudiante = st.sidebar.text_input("Nombre del estudiante", "David Santiago Sierra Cadavid")
codigo_estacion = "42"  # fijo
fecha_desde = st.sidebar.date_input("Desde", pd.to_datetime("2026-08-23")).strftime("%Y-%m-%d")
fecha_hasta = st.sidebar.date_input("Hasta", pd.to_datetime("2026-08-30")).strftime("%Y-%m-%d")
calidad = st.sidebar.selectbox("Calidad", [1, 0], index=0)
consultar = st.sidebar.button("🔍 Consultar", type="primary")

st.title("🌊 Santo Domingo, Quebrada Santiago  (Red Agua - Cód. 42)")
st.caption(f"Estudiante: **{nombre_estudiante}** · Estación fija: **{codigo_estacion}**")

# ------------------------------------------------------------------
# Consulta y Dashboard
# ------------------------------------------------------------------
if consultar:
    datos_crudos, error = obtener_serie_nivel(codigo_estacion, fecha_desde, fecha_hasta, calidad)
    if error:
        st.error(f"❌ {error}")
    else:
        registros = obtener_todas_las_paginas(datos_crudos)
        if not registros:
            st.warning("No hay registros para este rango de fechas.")
        else:
            df = pd.DataFrame(registros)
            df = df.rename(columns={LLAVE_FECHA: "fecha", LLAVE_VALOR: "nivel"})
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            df["nivel"] = pd.to_numeric(df["nivel"], errors="coerce")
            df = df.dropna(subset=["fecha", "nivel"]).sort_values("fecha").reset_index(drop=True)

            indice_calidad, huecos, n_outliers = calcular_indice_calidad(df)

            tab1, tab2, tab3, tab4 = st.tabs(["📊 Métricas", "📈 Gráfica de línea", "📉 Cuartiles", "🗺️ Mapa"])

          with tab1:
    st.subheader("Métricas principales")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Lecturas", len(df))
    col2.metric("Nivel promedio", f"{df['nivel'].mean():.2f}")
    col3.metric("Índice de calidad", f"{indice_calidad} / 100")
    col4.metric("Outliers detectados", n_outliers)

    # --- Gráfico de métricas ---
    st.subheader("Visualización de métricas")
    metricas_df = pd.DataFrame({
        "Métrica": ["Lecturas", "Nivel promedio", "Índice de calidad", "Outliers"],
        "Valor": [len(df), df["nivel"].mean(), indice_calidad, n_outliers]
    })
    st.bar_chart(metricas_df.set_index("Métrica"))


            with tab2:
                st.subheader("Serie de nivel (línea)")
                st.line_chart(df.set_index("fecha")["nivel"])

            with tab3:
                st.subheader("Distribución y cuartiles")
                df["fecha_dia"] = df["fecha"].dt.date
                fig, ax = plt.subplots(figsize=(8,4))
                df.boxplot(column="nivel", by="fecha_dia", ax=ax, rot=90)
                ax.set_title("Variabilidad diaria de niveles (cuartiles)")
                ax.set_ylabel("Nivel")
                st.pyplot(fig)

            with tab4:
                st.subheader("Ubicación de la estación")
                st.map(pd.DataFrame({"lat": [LAT_FIJO], "lon": [LON_FIJO]}), zoom=10)
                st.caption(f"Latitud: {LAT_FIJO}, Longitud: {LON_FIJO}")

                st.subheader("Datos crudos")
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Descargar CSV", csv, file_name=f"nivel_estacion_{codigo_estacion}.csv", mime="text/csv")
else:
    st.info("Ajusta las fechas en el sidebar y presiona **Consultar**.")
