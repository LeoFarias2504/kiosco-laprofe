import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, date

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="GESTION LIBRERIA LA PROFE", layout="wide", page_icon="📚")

COPIAS_META_MENSUAL = 20_000

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_connection():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
        client = gspread.authorize(creds)
        return client.open("Base_Datos_Kiosco").sheet1
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

# --- 3. FUNCIONES DE DATOS ---
def load_data():
    sheet = get_connection()
    data = sheet.get_all_records()

    if not data:
        return pd.DataFrame(columns=[
            "Fecha", "Venta_Efectivo", "Venta_MP", "Total_Ventas",
            "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta",
            "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
            "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
            "Ganancia_Neta", "Notas"
        ])

    df = pd.DataFrame(data)

    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'])

    cols_numericas = ['Total_Ventas', 'Ganancia_Neta', 'Total_Sueldos', 'Cant_Copias',
                      'Costo_Copia_Unit', 'Gastos_Fijos', 'Total_Costo_Copias',
                      'Valor_Hora', 'Margen_Porc', 'Costo_Mercaderia', 'Venta_Efectivo', 'Venta_MP']

    for col in cols_numericas:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'[$,]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    return df.sort_values(by="Fecha", ascending=False).reset_index(drop=True)

def save_new_record(record_dict):
    sheet = get_connection()
    try:
        headers = sheet.row_values(1)
        if not headers:
            headers = list(record_dict.keys())
            sheet.append_row(headers)
    except Exception as e:
        st.warning(f"No se pudieron leer los headers: {e}")

    orden_cols = [
        "Fecha", "Venta_Efectivo", "Venta_MP", "Total_Ventas",
        "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta",
        "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
        "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
        "Ganancia_Neta", "Notas"
    ]

    fila_a_subir = []
    for col in orden_cols:
        val = record_dict.get(col, "")
        if isinstance(val, (datetime, date, pd.Timestamp)):
            val = val.strftime('%Y-%m-%d')
        fila_a_subir.append(val)

    sheet.append_row(fila_a_subir)

def update_record_by_date(fecha_a_editar, record_dict):
    sheet = get_connection()
    fecha_str = fecha_a_editar.strftime('%Y-%m-%d')
    try:
        cell = sheet.find(fecha_str)
        row_num = cell.row
        orden_cols = [
            "Fecha", "Venta_Efectivo", "Venta_MP", "Total_Ventas",
            "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta",
            "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
            "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
            "Ganancia_Neta", "Notas"
        ]
        fila = []
        for col in orden_cols:
            val = record_dict.get(col, "")
            if isinstance(val, (datetime, date, pd.Timestamp)):
                val = val.strftime('%Y-%m-%d')
            fila.append(val)
        sheet.update(f'A{row_num}', [fila])
    except gspread.exceptions.CellNotFound:
        st.warning("No se encontró la fila para editar.")

def delete_record_by_date(fecha_a_borrar):
    sheet = get_connection()
    fecha_str = fecha_a_borrar.strftime('%Y-%m-%d')
    try:
        cell = sheet.find(fecha_str)
        sheet.delete_rows(cell.row)
    except gspread.exceptions.CellNotFound:
        st.warning("No se encontró la fila.")

def recalculate_all_history():
    sheet = get_connection()
    data = sheet.get_all_records()
    if not data:
        return

    df = pd.DataFrame(data)
    updated_rows = []

    headers = [
        "Fecha", "Venta_Efectivo", "Venta_MP", "Total_Ventas",
        "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta",
        "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
        "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
        "Ganancia_Neta", "Notas"
    ]
    updated_rows.append(headers)

    def clean_float(val):
        return float(str(val).replace('$', '').replace(',', '')) if val else 0.0

    for i, row in df.iterrows():
        total_ventas     = clean_float(row.get('Total_Ventas', 0))
        margen_porc      = clean_float(row.get('Margen_Porc', 50))
        cant_copias      = clean_float(row.get('Cant_Copias', 0))
        costo_copia_unit = clean_float(row.get('Costo_Copia_Unit', 0))
        gastos_fijos     = clean_float(row.get('Gastos_Fijos', 0))
        total_sueldos    = clean_float(row.get('Total_Sueldos', 0))

        costo_mercaderia  = total_ventas * (1 - (margen_porc / 100))
        total_costo_copias = cant_copias * costo_copia_unit
        ganancia_bruta    = total_ventas - costo_mercaderia
        ganancia_neta     = ganancia_bruta - gastos_fijos - total_sueldos

        new_row = [
            row.get('Fecha'), row.get('Venta_Efectivo'), row.get('Venta_MP'),
            total_ventas, margen_porc, costo_mercaderia, ganancia_bruta,
            gastos_fijos, row.get('Horas_Trabajadas'), row.get('Valor_Hora'),
            total_sueldos, cant_copias, costo_copia_unit, total_costo_copias,
            ganancia_neta, row.get('Notas', '')
        ]
        updated_rows.append(new_row)

    sheet.clear()
    sheet.update(updated_rows)

def get_periodo_copia(fecha):
    if fecha.day > 21:
        next_month = fecha.replace(day=28) + timedelta(days=4)
        return next_month.strftime("%Y-%m (Cierre 21)")
    else:
        return fecha.strftime("%Y-%m (Cierre 21)")

def get_semaforo(porc_utilidad):
    if porc_utilidad >= 20:
        return "🟢", "Excelente"
    elif porc_utilidad >= 10:
        return "🟡", "Regular"
    else:
        return "🔴", "Por debajo"

def df_to_csv(df_export):
    return df_export.to_csv(index=False, sep=';').encode('utf-8-sig')

# --- 4. LOGIN ---
def check_password():
    clave_real = "libreria2024"
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        st.markdown("<h1 style='text-align: center;'>🔒 Acceso La Profe</h1>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pass_input = st.text_input("Contraseña", type="password")
            if st.button("Ingresar", type="primary"):
                if pass_input == clave_real:
                    st.session_state.password_correct = True
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta")
        return False
    return True

# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================
if check_password():

    with st.spinner('Conectando...'):
        df = load_data()
        ultima_actualizacion = datetime.now().strftime('%H:%M:%S')

    # --- VALORES POR DEFECTO ---
    def_margen     = 50
    def_valor_hora = 2000.0
    def_costo_copia = 55.0
    def_gastos     = 0.0

    if not df.empty:
        last_row = df.iloc[0]
        def_margen      = int(last_row.get('Margen_Porc', 50))
        def_valor_hora  = float(last_row.get('Valor_Hora', 2000.0))
        def_costo_copia = float(last_row.get('Costo_Copia_Unit', 55.0))
        def_gastos      = float(last_row.get('Gastos_Fijos', 0.0))

    # ---- SIDEBAR ----
    with st.sidebar:
        st.title("📚 LIBRERIA LA PROFE")
        st.caption(f"🟢 Datos cargados a las {ultima_actualizacion}")
        st.markdown("---")

        # Estado de previsualización
        if "preview_data" not in st.session_state:
            st.session_state.preview_data = None

        with st.form("daily_form", clear_on_submit=True):
            st.subheader("📝 Nuevo Registro")
            fecha = st.date_input("Fecha", datetime.today())

            st.markdown("##### 1. Ingresos (Caja)")
            c1, c2 = st.columns(2)
            venta_efvo = c1.number_input("Efectivo Total ($)", min_value=0.0, format="%.2f")
            venta_mp   = c2.number_input("Mercado Pago ($)", min_value=0.0, format="%.2f")

            st.markdown("##### 2. Copias (Solo Informativo)")
            c3, c4 = st.columns(2)
            cant_copias = c3.number_input("Cantidad Copias", min_value=0, step=1)
            costo_copia = c4.number_input("Costo Insumo ($)", value=def_costo_copia, format="%.2f",
                                           help="Costo de papel+toner. NO se restará de la ganancia.")

            st.markdown("##### 3. Gastos")
            c5, c6 = st.columns(2)
            horas_staff  = c5.number_input("Horas Staff", min_value=0.0, step=0.5)
            valor_hora   = c6.number_input("Valor Hora ($)", value=def_valor_hora, format="%.2f")
            gastos_fijos = st.number_input("Otros Gastos Fijos", value=def_gastos, format="%.2f")

            st.markdown("##### 4. Config")
            margen_input = st.slider("Margen (%)", 10, 90, def_margen,
                                     help="Este margen define el Costo de Mercadería (Reposición).")
            notas = st.text_input("Notas")

            col_prev, col_save = st.columns(2)
            preview_btn = col_prev.form_submit_button("👁️ Previsualizar")
            submitted   = col_save.form_submit_button("☁️ Guardar")

            if preview_btn or submitted:
                total_ventas      = venta_efvo + venta_mp
                costo_mercaderia  = total_ventas * (1 - (margen_input / 100))
                total_costo_copias = cant_copias * costo_copia
                ganancia_bruta    = total_ventas - costo_mercaderia
                total_sueldos     = horas_staff * valor_hora
                ganancia_neta     = ganancia_bruta - gastos_fijos - total_sueldos

                new_record = {
                    "Fecha": fecha,
                    "Venta_Efectivo": venta_efvo, "Venta_MP": venta_mp,
                    "Total_Ventas": total_ventas, "Margen_Porc": margen_input,
                    "Costo_Mercaderia": costo_mercaderia, "Ganancia_Bruta": ganancia_bruta,
                    "Gastos_Fijos": gastos_fijos, "Horas_Trabajadas": horas_staff,
                    "Valor_Hora": valor_hora, "Total_Sueldos": total_sueldos,
                    "Cant_Copias": cant_copias, "Costo_Copia_Unit": costo_copia,
                    "Total_Costo_Copias": total_costo_copias,
                    "Ganancia_Neta": ganancia_neta, "Notas": notas
                }

                if preview_btn:
                    st.session_state.preview_data = new_record

                if submitted:
                    with st.spinner("Subiendo datos..."):
                        save_new_record(new_record)
                    st.success("¡Guardado exitosamente!")
                    st.session_state.preview_data = None
                    st.rerun()

        # --- VISTA PREVIA ---
        if st.session_state.preview_data:
            prev = st.session_state.preview_data
            porc_util = (prev['Ganancia_Neta'] / prev['Total_Ventas'] * 100) if prev['Total_Ventas'] > 0 else 0
            semaforo_icono, semaforo_texto = get_semaforo(porc_util)
            color_neta = "green" if prev['Ganancia_Neta'] >= 0 else "red"

            st.markdown("---")
            st.markdown("##### 📊 Vista Previa")
            st.markdown(f"""
            <div style="background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; padding:12px; font-size:13px;">
                <b>📅 Fecha:</b> {prev['Fecha']}<br>
                <b>💰 Ventas:</b> ${prev['Total_Ventas']:,.0f}<br>
                <b>📦 Costo Mercadería:</b> ${prev['Costo_Mercaderia']:,.0f}<br>
                <b>👷 Sueldos:</b> ${prev['Total_Sueldos']:,.0f}<br>
                <b>🏢 Gastos Fijos:</b> ${prev['Gastos_Fijos']:,.0f}<br>
                <hr style="margin:6px 0">
                <b>✅ Ganancia Neta:</b>
                <span style="color:{color_neta}; font-size:16px; font-weight:bold;">
                    ${prev['Ganancia_Neta']:,.0f}
                </span><br>
                <b>📈 Utilidad:</b> {porc_util:.1f}% &nbsp; {semaforo_icono} {semaforo_texto}
            </div>
            """, unsafe_allow_html=True)
            st.caption("Completá el formulario y presioná ☁️ Guardar para confirmar.")

        st.markdown("---")
        st.markdown("##### ⚠️ Mantenimiento")
        if st.button("🔄 RECALCULAR HISTORIAL"):
            with st.spinner("Recalculando..."):
                recalculate_all_history()
            st.success("¡Base actualizada!")
            st.rerun()

        st.markdown("---")
        if st.button("🔒 Cerrar Sesión"):
            st.session_state.password_correct = False
            st.rerun()

    # ============================================================
    # DASHBOARD PRINCIPAL
    # ============================================================
    st.title("📊 GESTION LIBRERIA LA PROFE")
    st.caption(f"🟢 Última sincronización con Google Sheets: {ultima_actualizacion}")

    if not df.empty:
        # --- FILTROS ---
        st.markdown("### 🔍 Visualización")
        filtro_col, periodo_col = st.columns([1, 3])
        with filtro_col:
            opcion_filtro = st.radio("Filtrar por:", ["Hoy", "Última Semana", "Rango Personalizado", "Mes (Ciclo Copias)"])

        df_filtrado = df.copy()
        df_filtrado['Fecha_Solo'] = df_filtrado['Fecha'].dt.date
        hoy = datetime.today().date()
        titulo_periodo = "Todo"
        es_vista_mes = False

        with periodo_col:
            st.write("")
            if opcion_filtro == "Hoy":
                df_filtrado = df_filtrado[df_filtrado['Fecha_Solo'] == hoy]
                titulo_periodo = f"HOY ({hoy.strftime('%d/%m')})"

            elif opcion_filtro == "Última Semana":
                inicio = hoy - timedelta(days=7)
                df_filtrado = df_filtrado[
                    (df_filtrado['Fecha_Solo'] >= inicio) & (df_filtrado['Fecha_Solo'] <= hoy)
                ]
                titulo_periodo = "ÚLTIMOS 7 DÍAS"

            elif opcion_filtro == "Rango Personalizado":
                c_inicio, c_fin = st.columns(2)
                f_inicio = c_inicio.date_input("Desde:", hoy - timedelta(days=30))
                f_fin    = c_fin.date_input("Hasta:", hoy)
                if f_inicio <= f_fin:
                    df_filtrado = df_filtrado[
                        (df_filtrado['Fecha_Solo'] >= f_inicio) & (df_filtrado['Fecha_Solo'] <= f_fin)
                    ]
                    titulo_periodo = f"DEL {f_inicio.strftime('%d/%m')} AL {f_fin.strftime('%d/%m')}"

            elif opcion_filtro == "Mes (Ciclo Copias)":
                df['Periodo_Fiscal'] = df['Fecha'].apply(get_periodo_copia)
                meses   = sorted(df['Periodo_Fiscal'].unique(), reverse=True)
                mes_sel = st.selectbox("Selecciona Periodo:", meses)
                df_filtrado    = df[df['Periodo_Fiscal'] == mes_sel].copy()
                titulo_periodo = f"PERIODO {mes_sel}"
                es_vista_mes   = True

        st.divider()

        if df_filtrado.empty:
            st.info(f"No hay datos para: {titulo_periodo}")
        else:
            # === CARTEL PNL ===
            pnl_total    = df_filtrado['Ganancia_Neta'].sum()
            ventas_total = df_filtrado['Total_Ventas'].sum()
            porc_utilidad = (pnl_total / ventas_total * 100) if ventas_total > 0 else 0
            semaforo_icono, semaforo_texto = get_semaforo(porc_utilidad)

            st.markdown(f"""
            <div style="background-color:#d1e7dd; border:1px solid #198754; padding:15px;
                        border-radius:10px; text-align:center; max-width:600px; margin:0 auto 20px auto;">
                <h3 style="color:#0f5132; margin:0; font-size:18px;">GANANCIA NETA ({titulo_periodo})</h3>
                <h1 style="color:#198754; font-size:45px; margin:0; font-weight:bold;">${pnl_total:,.0f}</h1>
                <p style="color:#0f5132; margin:5px 0 0 0; font-size:16px;">
                    Utilidad Real: <strong>{porc_utilidad:.1f}%</strong> &nbsp; {semaforo_icono} {semaforo_texto}
                </p>
            </div><br>
            """, unsafe_allow_html=True)

            # === MÉTRICAS CON DELTA (solo en vista Semana) ===
            ventas_anterior = None
            pnl_anterior    = None
            if opcion_filtro == "Última Semana":
                inicio_ant = hoy - timedelta(days=14)
                fin_ant    = hoy - timedelta(days=8)
                df_ant = df.copy()
                df_ant['Fecha_Solo'] = df_ant['Fecha'].dt.date
                df_ant = df_ant[(df_ant['Fecha_Solo'] >= inicio_ant) & (df_ant['Fecha_Solo'] <= fin_ant)]
                if not df_ant.empty:
                    ventas_anterior = df_ant['Total_Ventas'].sum()
                    pnl_anterior    = df_ant['Ganancia_Neta'].sum()

            delta_ventas = f"${ventas_total - ventas_anterior:,.0f} vs sem. ant." if ventas_anterior is not None else None
            delta_pnl    = f"${pnl_total - pnl_anterior:,.0f} vs sem. ant."    if pnl_anterior    is not None else None

            dias_con_datos = df_filtrado['Fecha'].nunique()
            promedio_diario = ventas_total / dias_con_datos if dias_con_datos > 0 else 0

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Ventas Totales",   f"${ventas_total:,.0f}",  delta_ventas)
            col2.metric("Ganancia Neta",    f"${pnl_total:,.0f}",     delta_pnl)
            col3.metric("Promedio / Día",   f"${promedio_diario:,.0f}")
            col4.metric("Sueldos",          f"${df_filtrado['Total_Sueldos'].sum():,.0f}")
            col5.metric("Gastos Fijos",     f"${df_filtrado['Gastos_Fijos'].sum():,.0f}")

            # === RESUMEN: MEJOR Y PEOR DÍA ===
            if len(df_filtrado) > 1:
                idx_mejor = df_filtrado['Ganancia_Neta'].idxmax()
                idx_peor  = df_filtrado['Ganancia_Neta'].idxmin()
                mejor_dia = df_filtrado.loc[idx_mejor]
                peor_dia  = df_filtrado.loc[idx_peor]

                rm, rp = st.columns(2)
                rm.success(
                    f"📈 **Mejor día:** {mejor_dia['Fecha'].strftime('%d/%m')} — "
                    f"${mejor_dia['Ganancia_Neta']:,.0f} netos"
                )
                rp.error(
                    f"📉 **Peor día:** {peor_dia['Fecha'].strftime('%d/%m')} — "
                    f"${peor_dia['Ganancia_Neta']:,.0f} netos"
                )

            # === ALERTA DÍAS SIN REGISTRAR ===
            if opcion_filtro in ("Última Semana", "Rango Personalizado", "Mes (Ciclo Copias)"):
                fechas_con_datos = set(df_filtrado['Fecha'].dt.date)
                fecha_min = df_filtrado['Fecha'].min().date()
                fecha_max = df_filtrado['Fecha'].max().date()
                rango_completo = set(
                    fecha_min + timedelta(days=i)
                    for i in range((fecha_max - fecha_min).days + 1)
                )
                dias_faltantes = sorted(
                    d for d in rango_completo
                    if d not in fechas_con_datos and d.weekday() < 6  # excluye domingos
                )
                if dias_faltantes:
                    lista = ", ".join(d.strftime('%d/%m') for d in dias_faltantes)
                    st.warning(f"⚠️ **Días sin registrar en el período:** {lista}")

            # === GRÁFICO DE EVOLUCIÓN ===
            if len(df_filtrado) > 1:
                st.divider()
                st.markdown("### 📈 Evolución")
                tab_gan, tab_ven, tab_mp = st.tabs(["Ganancia Neta", "Ventas", "Efectivo vs MP"])

                df_chart = (
                    df_filtrado.sort_values('Fecha')[['Fecha', 'Ganancia_Neta', 'Total_Ventas']]
                    .copy()
                    .set_index('Fecha')
                )

                with tab_gan:
                    st.line_chart(df_chart[['Ganancia_Neta']], color="#198754")
                with tab_ven:
                    st.bar_chart(df_chart[['Total_Ventas']], color="#0d6efd")
                with tab_mp:
                    total_efvo = df_filtrado['Venta_Efectivo'].sum()
                    total_mp   = df_filtrado['Venta_MP'].sum()
                    if total_efvo + total_mp > 0:
                        porc_efvo = total_efvo / (total_efvo + total_mp) * 100
                        porc_mp   = total_mp   / (total_efvo + total_mp) * 100
                        col_ef, col_mp, col_chart = st.columns([1, 1, 2])
                        col_ef.metric("💵 Efectivo",    f"${total_efvo:,.0f}", f"{porc_efvo:.1f}%")
                        col_mp.metric("📱 Mercado Pago", f"${total_mp:,.0f}",  f"{porc_mp:.1f}%")
                        df_pie = pd.DataFrame({
                            "Medio": ["Efectivo", "Mercado Pago"],
                            "Monto": [total_efvo, total_mp]
                        }).set_index("Medio")
                        col_chart.bar_chart(df_pie, color=["#198754", "#0d6efd"])
                    else:
                        st.info("Sin datos de medios de pago para este período.")

            # === ANÁLISIS MENSUAL COPIAS ===
            if es_vista_mes:
                st.divider()
                st.subheader("🖨️ Análisis Mensual Copias")
                tot_copias = df_filtrado['Cant_Copias'].sum()
                progreso   = min(tot_copias / COPIAS_META_MENSUAL, 1.0)

                c1, c2, c3 = st.columns(3)
                c1.metric("Acumulado Mes", f"{tot_copias:,.0f}", f"Meta: {COPIAS_META_MENSUAL:,}")
                c2.metric("Progreso", f"{progreso * 100:.1f}%")
                if tot_copias < COPIAS_META_MENSUAL:
                    c3.error(f"Faltan {COPIAS_META_MENSUAL - tot_copias:,.0f}")
                else:
                    c3.success("✅ Meta superada")

                st.progress(
                    progreso,
                    text=f"{tot_copias:,.0f} / {COPIAS_META_MENSUAL:,} copias"
                )

                # --- RESUMEN POR SEMANA ---
                st.markdown("##### 📅 Resumen por semana")
                df_sem = df_filtrado.copy()
                df_sem['Semana'] = df_sem['Fecha'].dt.to_period('W').apply(
                    lambda r: f"{r.start_time.strftime('%d/%m')} – {r.end_time.strftime('%d/%m')}"
                )
                resumen_sem = (
                    df_sem.groupby('Semana', sort=False)
                    .agg(
                        Ventas=('Total_Ventas', 'sum'),
                        Gan_Neta=('Ganancia_Neta', 'sum'),
                        Copias=('Cant_Copias', 'sum'),
                        Dias=('Fecha', 'nunique')
                    )
                    .reset_index()
                )
                resumen_sem.columns = ['Semana', 'Ventas', 'Ganancia Neta', 'Copias', 'Días']
                resumen_sem['Ventas']        = resumen_sem['Ventas'].apply(lambda x: f"${x:,.0f}")
                resumen_sem['Ganancia Neta'] = resumen_sem['Ganancia Neta'].apply(lambda x: f"${x:,.0f}")
                resumen_sem['Copias']        = resumen_sem['Copias'].apply(lambda x: f"{x:,.0f}")
                st.dataframe(resumen_sem, use_container_width=True, hide_index=True)

            st.divider()

            # === TABLA + EXPORTAR ===
            title_col, export_col = st.columns([3, 1])
            title_col.markdown("### 📋 Gestión de Registros")

            with export_col:
                cols_exp  = ['Fecha', 'Total_Ventas', 'Ganancia_Neta', 'Costo_Mercaderia',
                             'Total_Sueldos', 'Gastos_Fijos', 'Cant_Copias', 'Notas']
                cols_val  = [c for c in cols_exp if c in df_filtrado.columns]
                df_export = df_filtrado[cols_val].copy()
                if 'Fecha' in df_export.columns:
                    df_export['Fecha'] = df_export['Fecha'].dt.strftime('%d/%m/%Y')

                st.download_button(
                    label="📥 Exportar CSV",
                    data=df_to_csv(df_export),
                    file_name=f"libreria_{titulo_periodo.replace(' ', '_')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            # Encabezados tabla
            h1, h2, h3, h4, h5, h6, h7, h8, h9 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 0.6, 0.6])
            h1.markdown("**Fecha**");     h2.markdown("**Ventas**")
            h3.markdown("**Costo Rep.**"); h4.markdown("**C. Copias**")
            h5.markdown("**Sueldos**");   h6.markdown("**Gastos Fijos**")
            h7.markdown("**Neta**");      h8.markdown("**✏️**");  h9.markdown("**🗑️**")
            st.markdown("---")

            for index, row in df_filtrado.iterrows():
                c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 0.6, 0.6])
                c1.write(row['Fecha'].strftime('%d/%m'))
                c2.write(f"${row['Total_Ventas']:,.0f}")
                c3.write(f"${row['Costo_Mercaderia']:,.0f}")
                c4.write(f"${row['Total_Costo_Copias']:,.0f}")
                c5.write(f"${row['Total_Sueldos']:,.0f}")
                c6.write(f"${row['Gastos_Fijos']:,.0f}")

                color_neta = "green" if row['Ganancia_Neta'] > 0 else "red"
                c7.markdown(f":{color_neta}[**${row['Ganancia_Neta']:,.0f}**]")

                key_edit = f"edit_{row['Fecha'].strftime('%Y%m%d')}_{index}"
                key_del  = f"del_{row['Fecha'].strftime('%Y%m%d')}_{index}"

                if c8.button("✏️", key=key_edit):
                    st.session_state[f"editing_{index}"] = not st.session_state.get(f"editing_{index}", False)

                if c9.button("🗑️", key=key_del):
                    with st.spinner("Borrando..."):
                        delete_record_by_date(row['Fecha'])
                    st.success("Borrado.")
                    st.rerun()

                # --- FORMULARIO DE EDICIÓN INLINE ---
                if st.session_state.get(f"editing_{index}", False):
                    with st.expander(f"✏️ Editando registro del {row['Fecha'].strftime('%d/%m/%Y')}", expanded=True):
                        with st.form(key=f"edit_form_{index}"):
                            ec1, ec2 = st.columns(2)
                            e_venta_efvo = ec1.number_input("Efectivo ($)",      value=float(row.get('Venta_Efectivo', 0)),    format="%.2f")
                            e_venta_mp   = ec2.number_input("Mercado Pago ($)",  value=float(row.get('Venta_MP', 0)),          format="%.2f")

                            ec3, ec4 = st.columns(2)
                            e_cant_copias = ec3.number_input("Copias",            value=int(row.get('Cant_Copias', 0)),          step=1)
                            e_costo_copia = ec4.number_input("Costo Copia ($)",   value=float(row.get('Costo_Copia_Unit', 55)), format="%.2f")

                            ec5, ec6 = st.columns(2)
                            e_horas      = ec5.number_input("Horas Staff",        value=float(row.get('Horas_Trabajadas', 0)),  step=0.5)
                            e_valor_hora = ec6.number_input("Valor Hora ($)",     value=float(row.get('Valor_Hora', 2000)),     format="%.2f")

                            e_gastos = st.number_input("Gastos Fijos ($)", value=float(row.get('Gastos_Fijos', 0)), format="%.2f")
                            e_margen = st.slider("Margen (%)", 10, 90, int(row.get('Margen_Porc', 50)))
                            e_notas  = st.text_input("Notas", value=str(row.get('Notas', '')))

                            if st.form_submit_button("💾 Guardar Cambios"):
                                e_total_ventas   = e_venta_efvo + e_venta_mp
                                e_costo_merc     = e_total_ventas * (1 - (e_margen / 100))
                                e_total_copias   = e_cant_copias * e_costo_copia
                                e_gan_bruta      = e_total_ventas - e_costo_merc
                                e_total_sueldos  = e_horas * e_valor_hora
                                e_gan_neta       = e_gan_bruta - e_gastos - e_total_sueldos

                                updated = {
                                    "Fecha": row['Fecha'],
                                    "Venta_Efectivo": e_venta_efvo,  "Venta_MP": e_venta_mp,
                                    "Total_Ventas": e_total_ventas,  "Margen_Porc": e_margen,
                                    "Costo_Mercaderia": e_costo_merc, "Ganancia_Bruta": e_gan_bruta,
                                    "Gastos_Fijos": e_gastos,        "Horas_Trabajadas": e_horas,
                                    "Valor_Hora": e_valor_hora,      "Total_Sueldos": e_total_sueldos,
                                    "Cant_Copias": e_cant_copias,    "Costo_Copia_Unit": e_costo_copia,
                                    "Total_Costo_Copias": e_total_copias,
                                    "Ganancia_Neta": e_gan_neta,     "Notas": e_notas
                                }
                                with st.spinner("Guardando cambios..."):
                                    update_record_by_date(row['Fecha'], updated)
                                st.success("¡Registro actualizado!")
                                st.session_state[f"editing_{index}"] = False
                                st.rerun()

    else:
        st.info("👋 La base de datos está vacía. Carga el primer registro a la izquierda.")
