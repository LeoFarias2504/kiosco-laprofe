import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, date

# --- 1. CONFIGURACIÓN DE PÁGINA PROFESIONAL ---
st.set_page_config(
    page_title="Librería La Profe | Dashboard",
    layout="wide",
    page_icon="📚",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS PERSONALIZADOS (PARA EL LOOK "PRO") ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] {
        font-size: 24px;
    }
    .big-font {
        font-size:30px !important;
        font-weight: bold;
    }
    .main-header {
        font-size: 40px; 
        color: #1E3A8A; 
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN ROBUSTA A GOOGLE SHEETS ---
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
        sheet = client.open("Base_Datos_Kiosco").sheet1 
        return sheet
    except Exception as e:
        st.error(f"⚠️ Error de conexión: {e}")
        st.stop()

# --- 3. FUNCIONES DE LÓGICA DE NEGOCIO ---
def load_data():
    sheet = get_connection()
    data = sheet.get_all_records()
    
    if not data:
        # Estructura vacía si no hay datos
        return pd.DataFrame(columns=[
            "Fecha", "Venta_Efectivo", "Venta_MP", "Total_Ventas", 
            "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta", 
            "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
            "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
            "Ganancia_Neta", "Notas"
        ])
    
    df = pd.DataFrame(data)
    
    # Procesamiento de Fechas y Números
    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'])
        
    cols_numericas = ['Total_Ventas', 'Ganancia_Neta', 'Total_Sueldos', 'Cant_Copias', 
                      'Costo_Copia_Unit', 'Gastos_Fijos', 'Total_Costo_Copias', 
                      'Valor_Hora', 'Margen_Porc', 'Costo_Mercaderia', 'Venta_Efectivo', 'Venta_MP']
    
    for col in cols_numericas:
        if col in df.columns:
            # Limpiar símbolos de moneda si existen y convertir a float
            df[col] = df[col].astype(str).str.replace(r'[$,]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df.sort_values(by="Fecha", ascending=False).reset_index(drop=True)

def save_new_record(record_dict):
    sheet = get_connection()
    try:
        headers = sheet.row_values(1)
        if not headers:
            # Si es la primera vez, creamos encabezados
            headers = list(record_dict.keys())
            sheet.append_row(headers)
    except:
        pass

    # Orden estricto de columnas para evitar desorden en el Excel
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

def delete_record_by_date(fecha_a_borrar):
    sheet = get_connection()
    fecha_str = fecha_a_borrar.strftime('%Y-%m-%d')
    try:
        cell = sheet.find(fecha_str)
        sheet.delete_rows(cell.row)
    except gspread.exceptions.CellNotFound:
        st.warning("No se encontró el registro para borrar.")

def get_periodo_copia(fecha):
    # Lógica de cierre el día 21
    if fecha.day > 21:
        next_month = fecha.replace(day=28) + timedelta(days=4)
        return next_month.strftime("%Y-%m (Cierre 21)")
    else:
        return fecha.strftime("%Y-%m (Cierre 21)")

# --- 4. SISTEMA DE ACCESO ---
def check_password():
    clave_real = "libreria2024" 
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    
    if not st.session_state.password_correct:
        # Diseño de Login Centrado
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.markdown("<br><br><h2 style='text-align: center;'>🔐 Acceso Seguro</h2>", unsafe_allow_html=True)
            pass_input = st.text_input("Contraseña de Administrador", type="password")
            if st.button("Iniciar Sesión", type="primary", use_container_width=True):
                if pass_input == clave_real:
                    st.session_state.password_correct = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")
        return False
    return True

# --- 5. INTERFAZ PRINCIPAL ---
if check_password():
    
    # Carga de datos
    df = load_data()

    # Valores por defecto inteligentes (toman el último registro)
    def_margen, def_valor_hora, def_costo_copia, def_gastos = 50, 2000.0, 10.0, 0.0
    if not df.empty:
        last = df.iloc[0]
        def_margen = int(last.get('Margen_Porc', 50))
        def_valor_hora = float(last.get('Valor_Hora', 2000.0))
        def_costo_copia = float(last.get('Costo_Copia_Unit', 10.0))
        def_gastos = float(last.get('Gastos_Fijos', 0.0))

    # === BARRA LATERAL (MENÚ DE CARGA) ===
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3330/3330314.png", width=50) # Icono genérico libro
        st.title("Librería La Profe")
        st.markdown("---")
        
        with st.form("form_carga", clear_on_submit=True):
            st.subheader("📝 Nuevo Registro Diario")
            fecha_input = st.date_input("Fecha de Cierre", datetime.today())
            
            # Usamos expanders para mantener limpio el diseño
            with st.expander("💰 Ingresos (Ventas)", expanded=True):
                c1, c2 = st.columns(2)
                v_efec = c1.number_input("Efectivo ($)", min_value=0.0, format="%.2f")
                v_mp = c2.number_input("Mercado Pago ($)", min_value=0.0, format="%.2f")
            
            with st.expander("🖨️ Fotocopiadora"):
                c3, c4 = st.columns(2)
                cant_cop = c3.number_input("Cantidad Hojas", min_value=0, step=1)
                cost_cop = c4.number_input("Costo por Hoja ($)", value=def_costo_copia, format="%.2f")
            
            with st.expander("📉 Gastos Operativos"):
                c5, c6 = st.columns(2)
                h_staff = c5.number_input("Horas Ayudante", min_value=0.0, step=0.5)
                v_hora = c6.number_input("Valor Hora ($)", value=def_valor_hora, format="%.2f")
                g_fijos = st.number_input("Gastos Fijos/Varios ($)", value=def_gastos, format="%.2f")
            
            with st.expander("⚙️ Configuración Rentabilidad"):
                margen = st.slider("Margen de Ganancia (%)", 10, 90, def_margen)
                notas = st.text_input("Observaciones / Notas")
            
            guardar_btn = st.form_submit_button("💾 Registrar Cierre", type="primary", use_container_width=True)

            if guardar_btn:
                # Cálculos automáticos
                tot_ventas = v_efec + v_mp
                cost_merc = tot_ventas * (1 - (margen / 100))
                g_bruta = tot_ventas - cost_merc
                tot_sueldos = h_staff * v_hora
                tot_cost_cop = cant_cop * cost_cop
                g_neta = g_bruta - g_fijos - tot_sueldos - tot_cost_cop
                
                new_rec = {
                    "Fecha": fecha_input, "Venta_Efectivo": v_efec, "Venta_MP": v_mp,
                    "Total_Ventas": tot_ventas, "Margen_Porc": margen,
                    "Costo_Mercaderia": cost_merc, "Ganancia_Bruta": g_bruta,
                    "Gastos_Fijos": g_fijos, "Horas_Trabajadas": h_staff,
                    "Valor_Hora": v_hora, "Total_Sueldos": tot_sueldos,
                    "Cant_Copias": cant_cop, "Costo_Copia_Unit": cost_cop,
                    "Total_Costo_Copias": tot_cost_cop, "Ganancia_Neta": g_neta, "Notas": notas
                }
                
                with st.spinner("Guardando en la nube..."):
                    save_new_record(new_rec)
                st.success("✅ ¡Registro guardado correctamente!")
                st.rerun()

        if st.sidebar.button("🔒 Cerrar Sesión", use_container_width=True):
            st.session_state.password_correct = False
            st.rerun()

    # === DASHBOARD PRINCIPAL ===
    st.markdown('<p class="main-header">Panel de Control Financiero</p>', unsafe_allow_html=True)

    if not df.empty:
        # --- FILTROS INTELIGENTES ---
        col_f1, col_f2 = st.columns([1, 3])
        with col_f1:
            filtro = st.selectbox("📅 Período de Análisis", 
                                ["Hoy", "Últimos 7 Días", "Últimos 30 Días", "Este Mes", "Rango Personalizado", "Ciclo Copias"])
        
        # Lógica de Filtros
        df_f = df.copy()
        df_f['Fecha_Solo'] = df_f['Fecha'].dt.date
        hoy = datetime.today().date()
        titulo_rango = "Histórico Completo"
        es_vista_copias = False

        with col_f2:
            if filtro == "Hoy":
                df_f = df_f[df_f['Fecha_Solo'] == hoy]
                titulo_rango = f"Resultados de Hoy ({hoy.strftime('%d/%m')})"
            elif filtro == "Últimos 7 Días":
                inicio = hoy - timedelta(days=7)
                df_f = df_f[(df_f['Fecha_Solo'] >= inicio) & (df_f['Fecha_Solo'] <= hoy)]
                titulo_rango = "Última Semana"
            elif filtro == "Últimos 30 Días":
                inicio = hoy - timedelta(days=30)
                df_f = df_f[(df_f['Fecha_Solo'] >= inicio) & (df_f['Fecha_Solo'] <= hoy)]
                titulo_rango = "Último Mes"
            elif filtro == "Este Mes":
                inicio = hoy.replace(day=1)
                df_f = df_f[(df_f['Fecha_Solo'] >= inicio) & (df_f['Fecha_Solo'] <= hoy)]
                titulo_rango = "Mes en Curso"
            elif filtro == "Ciclo Copias":
                df['P_Fiscal'] = df['Fecha'].apply(get_periodo_copia)
                periodos = sorted(df['P_Fiscal'].unique(), reverse=True)
                periodo_sel = st.selectbox("Seleccione Ciclo:", periodos)
                df_f = df[df['P_Fiscal'] == periodo_sel].copy()
                titulo_rango = f"Ciclo {periodo_sel}"
                es_vista_copias = True
            elif filtro == "Rango Personalizado":
                c1, c2 = st.columns(2)
                f_inicio = c1.date_input("Desde", hoy - timedelta(days=30))
                f_fin = c2.date_input("Hasta", hoy)
                if f_inicio <= f_fin:
                    df_f = df_f[(df_f['Fecha_Solo'] >= f_inicio) & (df_f['Fecha_Solo'] <= f_fin)]
                    titulo_rango = f"Del {f_inicio.strftime('%d/%m')} al {f_fin.strftime('%d/%m')}"

        st.markdown("---")

        if df_f.empty:
            st.info("👋 No hay movimientos registrados en este período.")
        else:
            # === TARJETAS DE INDICADORES (KPIs) ===
            pnl = df_f['Ganancia_Neta'].sum()
            ventas = df_f['Total_Ventas'].sum()
            utilidad_porc = (pnl / ventas * 100) if ventas > 0 else 0
            
            # Estilo tipo "Tarjeta de Banco"
            st.markdown(f"""
            <div style="background-color: #EFF6FF; padding: 20px; border-radius: 12px; border-left: 6px solid #1E3A8A; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4 style="margin:0; color: #555;">GANANCIA NETA ({titulo_rango})</h4>
                        <h1 style="margin:0; font-size: 45px; color: #1E3A8A;">${pnl:,.0f}</h1>
                    </div>
                    <div style="text-align: right;">
                        <h4 style="margin:0; color: #555;">MARGEN REAL</h4>
                        <h2 style="margin:0; color: {'#16a34a' if utilidad_porc > 20 else '#ca8a04'};">{utilidad_porc:.1f}%</h2>
                    </div>
                </div>
            </div>
            <br>
            """, unsafe_allow_html=True)

            # Métricas secundarias
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💰 Ventas Totales", f"${ventas:,.0f}")
            m2.metric("📦 Costo Reposición", f"${df_f['Costo_Mercaderia'].sum():,.0f}")
            m3.metric("💸 Gastos + Sueldos", f"${(df_f['Total_Sueldos'].sum() + df_f['Gastos_Fijos'].sum()):,.0f}")
            m4.metric("📄 Copias Realizadas", f"{df_f['Cant_Copias'].sum():,.0f}")

            # === PESTAÑAS DE ANÁLISIS ===
            tab_graficos, tab_datos = st.tabs(["📊 Gráficos y Tendencias", "📋 Base de Datos Detallada"])

            with tab_graficos:
                c_graf1, c_graf2 = st.columns(2)
                
                with c_graf1:
                    st.subheader("Evolución de Ventas")
                    # Agrupamos por fecha para limpiar el gráfico
                    chart_ventas = df_f.groupby('Fecha')[['Total_Ventas', 'Ganancia_Neta']].sum()
                    st.area_chart(chart_ventas, color=["#93C5FD", "#1E3A8A"]) # Tonos azules
                
                with c_graf2:
                    st.subheader("Distribución de Gastos")
                    gastos_data = df_f[['Total_Sueldos', 'Gastos_Fijos', 'Total_Costo_Copias']].sum()
                    st.bar_chart(gastos_data, color="#64748B")

                if es_vista_copias:
                    st.divider()
                    st.info(f"🖨️ **Análisis de Copias:** Se hicieron {df_f['Cant_Copias'].sum():,.0f} copias en el ciclo {periodo_sel}.")

            with tab_datos:
                # Botón de descarga CSV
                csv = df_f.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Reporte en Excel (CSV)",
                    data=csv,
                    file_name=f"reporte_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    type="primary"
                )
                
                # TABLA INTERACTIVA PROFESIONAL
                # Preparamos el dataframe para mostrar (seleccionamos columnas clave y renombramos)
                df_display = df_f[[
                    "Fecha", "Total_Ventas", "Costo_Mercaderia", "Total_Sueldos", 
                    "Gastos_Fijos", "Total_Costo_Copias", "Ganancia_Neta", "Notas"
                ]].copy()
                
                # Formateamos la fecha solo para visualización
                df_display['Fecha'] = df_display['Fecha'].dt.strftime('%Y-%m-%d')

                # Usamos st.dataframe con config de columnas (NUEVO EN STREAMLIT)
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Total_Ventas": st.column_config.NumberColumn("Ventas", format="$%d"),
                        "Costo_Mercaderia": st.column_config.NumberColumn("Costo Rep.", format="$%d"),
                        "Total_Sueldos": st.column_config.NumberColumn("Sueldos", format="$%d"),
                        "Gastos_Fijos": st.column_config.NumberColumn("Gastos", format="$%d"),
                        "Total_Costo_Copias": st.column_config.NumberColumn("Costo Copias", format="$%d"),
                        "Ganancia_Neta": st.column_config.NumberColumn("Ganancia Neta", format="$%d"),
                    }
                )

                st.markdown("##### 🗑️ Gestión de Registros (Borrar)")
                with st.expander("Abrir zona de borrado"):
                    st.warning("Cuidado: Esta acción es permanente.")
                    for idx, row in df_f.iterrows():
                        col_text, col_btn = st.columns([4, 1])
                        col_text.text(f"{row['Fecha'].strftime('%d/%m/%Y')} - Ventas: ${row['Total_Ventas']:,.0f} - Neta: ${row['Ganancia_Neta']:,.0f}")
                        if col_btn.button("Borrar", key=f"del_{idx}"):
                            delete_record_by_date(row['Fecha'])
                            st.success("Registro eliminado.")
                            st.rerun()

    else:
        st.write("---")
        st.info("👈 Utiliza el menú lateral para cargar el primer registro del día.")
