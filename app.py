import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, date

# ============================================================
# 1. CONFIGURACIÓNo
# ============================================================
st.set_page_config(page_title="GESTION LIBRERIA LA PROFE", layout="wide", page_icon="📚")

COPIAS_META_MENSUAL = 20_000

# ============================================================
# 2. CONEXIÓN A GOOGLE SHEETS
# ============================================================
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

# ============================================================
# 3. FUNCIONES DE DATOS
# ============================================================
ORDEN_COLS = [
    "Fecha", "Venta_Efectivo", "Venta_MP", "Total_Ventas",
    "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta",
    "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
    "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
    "Ganancia_Neta", "Notas"
]

def load_data():
    sheet = get_connection()
    data  = sheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=ORDEN_COLS)
    df = pd.DataFrame(data)
    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'])
    cols_num = ['Total_Ventas', 'Ganancia_Neta', 'Total_Sueldos', 'Cant_Copias',
                'Costo_Copia_Unit', 'Gastos_Fijos', 'Total_Costo_Copias',
                'Valor_Hora', 'Margen_Porc', 'Costo_Mercaderia', 'Venta_Efectivo', 'Venta_MP']
    for col in cols_num:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'[$,]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df.sort_values(by="Fecha", ascending=False).reset_index(drop=True)

def _fila(record_dict):
    fila = []
    for col in ORDEN_COLS:
        val = record_dict.get(col, "")
        if isinstance(val, (datetime, date, pd.Timestamp)):
            val = val.strftime('%Y-%m-%d')
        fila.append(val)
    return fila

def save_new_record(record_dict):
    sheet = get_connection()
    try:
        if not sheet.row_values(1):
            sheet.append_row(ORDEN_COLS)
    except Exception as e:
        st.warning(f"No se pudieron leer los headers: {e}")
    sheet.append_row(_fila(record_dict))

def update_record_by_date(fecha_editar, record_dict):
    sheet = get_connection()
    try:
        cell = sheet.find(fecha_editar.strftime('%Y-%m-%d'))
        sheet.update(f'A{cell.row}', [_fila(record_dict)])
    except gspread.exceptions.CellNotFound:
        st.warning("No se encontró la fila para editar.")

def delete_record_by_date(fecha_borrar):
    sheet = get_connection()
    try:
        cell = sheet.find(fecha_borrar.strftime('%Y-%m-%d'))
        sheet.delete_rows(cell.row)
    except gspread.exceptions.CellNotFound:
        st.warning("No se encontró la fila.")

def recalculate_all_history():
    sheet = get_connection()
    data  = sheet.get_all_records()
    if not data:
        return
    def cf(v):
        return float(str(v).replace('$', '').replace(',', '')) if v else 0.0
    rows = [ORDEN_COLS]
    for _, row in pd.DataFrame(data).iterrows():
        tv = cf(row.get('Total_Ventas', 0));  mp = cf(row.get('Margen_Porc', 50))
        cc = cf(row.get('Cant_Copias', 0));   cu = cf(row.get('Costo_Copia_Unit', 0))
        gf = cf(row.get('Gastos_Fijos', 0));  ts = cf(row.get('Total_Sueldos', 0))
        cm = tv * (1 - mp/100); tc = cc * cu; gb = tv - cm; gn = gb - gf - ts
        rows.append([row.get('Fecha'), row.get('Venta_Efectivo'), row.get('Venta_MP'),
                     tv, mp, cm, gb, gf, row.get('Horas_Trabajadas'), row.get('Valor_Hora'),
                     ts, cc, cu, tc, gn, row.get('Notas', '')])
    sheet.clear()
    sheet.update(rows)

def get_periodo_copia(fecha):
    if fecha.day > 21:
        return (fecha.replace(day=28) + timedelta(days=4)).strftime("%Y-%m (Cierre 21)")
    return fecha.strftime("%Y-%m (Cierre 21)")

def get_semaforo(p):
    if p >= 20: return "🟢", "Excelente"
    if p >= 10: return "🟡", "Regular"
    return "🔴", "Por debajo"

def df_to_csv(df_export):
    return df_export.to_csv(index=False, sep=';').encode('utf-8-sig')

def calcular_record(venta_efvo, venta_mp, cant_copias, costo_copia,
                    horas_staff, valor_hora, gastos_fijos, margen_input, fecha, notas):
    tv = venta_efvo + venta_mp
    cm = tv * (1 - margen_input / 100)
    tc = cant_copias * costo_copia
    gb = tv - cm
    ts = horas_staff * valor_hora
    gn = gb - gastos_fijos - ts
    return {
        "Fecha": fecha, "Venta_Efectivo": venta_efvo, "Venta_MP": venta_mp,
        "Total_Ventas": tv, "Margen_Porc": margen_input, "Costo_Mercaderia": cm,
        "Ganancia_Bruta": gb, "Gastos_Fijos": gastos_fijos, "Horas_Trabajadas": horas_staff,
        "Valor_Hora": valor_hora, "Total_Sueldos": ts, "Cant_Copias": cant_copias,
        "Costo_Copia_Unit": costo_copia, "Total_Costo_Copias": tc,
        "Ganancia_Neta": gn, "Notas": notas
    }

# ============================================================
# 4. LOGIN
# ============================================================
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
    def_margen      = 50
    def_valor_hora  = 2000.0
    def_costo_copia = 55.0
    def_gastos      = 0.0
    if not df.empty:
        last_row = df.iloc[0]
        def_margen      = int(last_row.get('Margen_Porc', 50))
        def_valor_hora  = float(last_row.get('Valor_Hora', 2000.0))
        def_costo_copia = float(last_row.get('Costo_Copia_Unit', 55.0))
        def_gastos      = float(last_row.get('Gastos_Fijos', 0.0))

    if "preview_data" not in st.session_state:
        st.session_state.preview_data = None

    # ============================================================
    # SIDEBAR
    # ============================================================
    with st.sidebar:
        st.title("📚 LIBRERIA LA PROFE")
        st.caption(f"🟢 Datos cargados a las {ultima_actualizacion}")
        st.markdown("---")

        with st.form("daily_form", clear_on_submit=True):
            st.subheader("📝 Nuevo Registro")
            fecha = st.date_input("Fecha", datetime.today())

            st.markdown("##### 1. Ingresos (Caja)")
            c1, c2 = st.columns(2)
            venta_efvo  = c1.number_input("Efectivo Total ($)", min_value=0.0, format="%.2f")
            venta_mp    = c2.number_input("Mercado Pago ($)",   min_value=0.0, format="%.2f")

            st.markdown("##### 2. Copias (Solo Informativo)")
            c3, c4 = st.columns(2)
            cant_copias = c3.number_input("Cantidad Copias", min_value=0, step=1)
            costo_copia = c4.number_input("Costo Insumo ($)", value=def_costo_copia, format="%.2f",
                                           help="Costo de papel+toner. NO se restará de la ganancia.")

            st.markdown("##### 3. Gastos")
            c5, c6 = st.columns(2)
            horas_staff  = c5.number_input("Horas Staff",    min_value=0.0, step=0.5)
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
                rec = calcular_record(venta_efvo, venta_mp, cant_copias, costo_copia,
                                      horas_staff, valor_hora, gastos_fijos, margen_input, fecha, notas)
                if preview_btn:
                    st.session_state.preview_data = rec
                if submitted:
                    with st.spinner("Subiendo datos..."):
                        save_new_record(rec)
                    st.toast("¡Guardado exitosamente!", icon="✅")
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
            st.toast("¡Base actualizada!", icon="✅")
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
        es_vista_mes   = False

        with periodo_col:
            st.write("")
            if opcion_filtro == "Hoy":
                df_filtrado    = df_filtrado[df_filtrado['Fecha_Solo'] == hoy]
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
            pnl_total     = df_filtrado['Ganancia_Neta'].sum()
            ventas_total  = df_filtrado['Total_Ventas'].sum()
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

            # === MÉTRICAS ===
            ventas_anterior = pnl_anterior = None
            if opcion_filtro == "Última Semana":
                df_ant = df.copy()
                df_ant['Fecha_Solo'] = df_ant['Fecha'].dt.date
                df_ant = df_ant[
                    (df_ant['Fecha_Solo'] >= hoy - timedelta(days=14)) &
                    (df_ant['Fecha_Solo'] <= hoy - timedelta(days=8))
                ]
                if not df_ant.empty:
                    ventas_anterior = df_ant['Total_Ventas'].sum()
                    pnl_anterior    = df_ant['Ganancia_Neta'].sum()

            delta_ventas = f"${ventas_total - ventas_anterior:,.0f} vs sem. ant." if ventas_anterior is not None else None
            delta_pnl    = f"${pnl_total - pnl_anterior:,.0f} vs sem. ant."       if pnl_anterior    is not None else None

            dias_con_datos  = df_filtrado['Fecha'].nunique()
            promedio_diario = ventas_total / dias_con_datos if dias_con_datos > 0 else 0

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Ventas Totales",  f"${ventas_total:,.0f}",  delta_ventas)
            col2.metric("Ganancia Neta",   f"${pnl_total:,.0f}",     delta_pnl)
            col3.metric("Promedio / Día",  f"${promedio_diario:,.0f}")
            col4.metric("Sueldos",         f"${df_filtrado['Total_Sueldos'].sum():,.0f}")
            col5.metric("Gastos Fijos",    f"${df_filtrado['Gastos_Fijos'].sum():,.0f}")

            # === MEJOR Y PEOR DÍA ===
            if len(df_filtrado) > 1:
                idx_mejor = df_filtrado['Ganancia_Neta'].idxmax()
                idx_peor  = df_filtrado['Ganancia_Neta'].idxmin()
                mejor_dia = df_filtrado.loc[idx_mejor]
                peor_dia  = df_filtrado.loc[idx_peor]
                rm, rp = st.columns(2)
                rm.success(f"📈 **Mejor día:** {mejor_dia['Fecha'].strftime('%d/%m')} — ${mejor_dia['Ganancia_Neta']:,.0f} netos")
                rp.error(f"📉 **Peor día:** {peor_dia['Fecha'].strftime('%d/%m')} — ${peor_dia['Ganancia_Neta']:,.0f} netos")

            # === ALERTA DÍAS SIN REGISTRAR ===
            if opcion_filtro in ("Última Semana", "Rango Personalizado", "Mes (Ciclo Copias)"):
                con_datos = set(df_filtrado['Fecha'].dt.date)
                fmin = df_filtrado['Fecha'].min().date()
                fmax = df_filtrado['Fecha'].max().date()
                faltantes = sorted(
                    fmin + timedelta(days=i)
                    for i in range((fmax - fmin).days + 1)
                    if (fmin + timedelta(days=i)) not in con_datos
                    and (fmin + timedelta(days=i)).weekday() < 6
                )
                if faltantes:
                    st.warning(f"⚠️ **Días sin registrar en el período:** {', '.join(d.strftime('%d/%m') for d in faltantes)}")

            # === GRÁFICO DE EVOLUCIÓN ===
            if len(df_filtrado) > 1:
                st.divider()
                st.markdown("### 📈 Evolución")
                tab_gan, tab_ven, tab_mp = st.tabs(["Ganancia Neta", "Ventas", "Efectivo vs MP"])

                df_chart = (df_filtrado.sort_values('Fecha')
                            [['Fecha', 'Ganancia_Neta', 'Total_Ventas']].copy().set_index('Fecha'))

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
                        col_ef.metric("💵 Efectivo",     f"${total_efvo:,.0f}", f"{porc_efvo:.1f}%")
                        col_mp.metric("📱 Mercado Pago", f"${total_mp:,.0f}",   f"{porc_mp:.1f}%")
                        df_pie = pd.DataFrame({"Efectivo": [total_efvo], "Mercado Pago": [total_mp]})
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
                c2.metric("Progreso",      f"{progreso * 100:.1f}%")
                if tot_copias < COPIAS_META_MENSUAL:
                    c3.error(f"Faltan {COPIAS_META_MENSUAL - tot_copias:,.0f}")
                else:
                    c3.success("✅ Meta superada")

                st.progress(progreso, text=f"{tot_copias:,.0f} / {COPIAS_META_MENSUAL:,} copias")

                st.markdown("##### 📅 Resumen por semana")
                df_sem = df_filtrado.copy()
                df_sem['Semana'] = df_sem['Fecha'].dt.to_period('W').apply(
                    lambda r: f"{r.start_time.strftime('%d/%m')} – {r.end_time.strftime('%d/%m')}")
                resumen_sem = (
                    df_sem.groupby('Semana', sort=False)
                    .agg(Ventas=('Total_Ventas','sum'), Ganancia=('Ganancia_Neta','sum'),
                         Copias=('Cant_Copias','sum'), Días=('Fecha','nunique'))
                    .reset_index()
                )
                resumen_sem['Ventas']   = resumen_sem['Ventas'].apply(lambda x: f"${x:,.0f}")
                resumen_sem['Ganancia'] = resumen_sem['Ganancia'].apply(lambda x: f"${x:,.0f}")
                resumen_sem['Copias']   = resumen_sem['Copias'].apply(lambda x: f"{x:,.0f}")
                st.dataframe(resumen_sem, use_container_width=True, hide_index=True)

            st.divider()

            # === TABLA + EXPORTAR ===
            title_col, export_col = st.columns([3, 1])
            title_col.markdown("### 📋 Gestión de Registros")
            with export_col:
                cols_exp = ['Fecha','Total_Ventas','Ganancia_Neta','Costo_Mercaderia',
                            'Total_Sueldos','Gastos_Fijos','Cant_Copias','Notas']
                df_exp = df_filtrado[[c for c in cols_exp if c in df_filtrado.columns]].copy()
                if 'Fecha' in df_exp.columns:
                    df_exp['Fecha'] = df_exp['Fecha'].dt.strftime('%d/%m/%Y')
                st.download_button("📥 Exportar CSV", data=df_to_csv(df_exp),
                                   file_name=f"libreria_{titulo_periodo.replace(' ','_')}.csv",
                                   mime="text/csv", use_container_width=True)

            # Encabezados tabla
            h1,h2,h3,h4,h5,h6,h7,h8,h9 = st.columns([1.2,1.2,1.2,1.2,1.2,1.2,1.2,0.6,0.6])
            h1.markdown("**Fecha**");      h2.markdown("**Ventas**")
            h3.markdown("**Costo Rep.**"); h4.markdown("**C. Copias**")
            h5.markdown("**Sueldos**");    h6.markdown("**Gastos Fijos**")
            h7.markdown("**Neta**");       h8.markdown("**✏️**"); h9.markdown("**🗑️**")
            st.markdown("---")

            for index, row in df_filtrado.iterrows():
                c1,c2,c3,c4,c5,c6,c7,c8,c9 = st.columns([1.2,1.2,1.2,1.2,1.2,1.2,1.2,0.6,0.6])
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
                    st.toast("Borrado.", icon="🗑️")
                    st.rerun()

                if st.session_state.get(f"editing_{index}", False):
                    with st.expander(f"✏️ Editando registro del {row['Fecha'].strftime('%d/%m/%Y')}", expanded=True):
                        with st.form(key=f"edit_form_{index}"):
                            ec1, ec2 = st.columns(2)
                            e_ef = ec1.number_input("Efectivo ($)",      value=float(row.get('Venta_Efectivo',0)),    format="%.2f")
                            e_mp = ec2.number_input("Mercado Pago ($)",  value=float(row.get('Venta_MP',0)),          format="%.2f")
                            ec3, ec4 = st.columns(2)
                            e_cc = ec3.number_input("Copias",            value=int(row.get('Cant_Copias',0)),         step=1)
                            e_cu = ec4.number_input("Costo Copia ($)",   value=float(row.get('Costo_Copia_Unit',55)), format="%.2f")
                            ec5, ec6 = st.columns(2)
                            e_hs = ec5.number_input("Horas Staff",       value=float(row.get('Horas_Trabajadas',0)),  step=0.5)
                            e_vh = ec6.number_input("Valor Hora ($)",    value=float(row.get('Valor_Hora',2000)),     format="%.2f")
                            e_gf = st.number_input("Gastos Fijos ($)",   value=float(row.get('Gastos_Fijos',0)),      format="%.2f")
                            e_mg = st.slider("Margen (%)", 10, 90,       int(row.get('Margen_Porc',50)))
                            e_no = st.text_input("Notas",                value=str(row.get('Notas','')))

                            if st.form_submit_button("💾 Guardar Cambios"):
                                upd = calcular_record(e_ef, e_mp, e_cc, e_cu, e_hs, e_vh, e_gf, e_mg,
                                                      row['Fecha'], e_no)
                                with st.spinner("Guardando cambios..."):
                                    update_record_by_date(row['Fecha'], upd)
                                st.toast("¡Registro actualizado!", icon="✅")
                                st.session_state[f"editing_{index}"] = False
                                st.rerun()

    else:
        st.info("👋 La base de datos está vacía. Carga el primer registro a la izquierda.")
