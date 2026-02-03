import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, date

# --- 1. CONFIGURACIÓN ---
st.set_page_config(
    page_title="Librería La Profe | Dashboard",
    layout="wide",
    page_icon="📚",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 24px; }
    .main-header { font-size: 40px; color: #1E3A8A; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
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
        st.error(f"⚠️ Error de conexión: {e}")
        st.stop()

# --- 3. FUNCIONES ---
def load_data():
    sheet = get_connection()
    data = sheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=[
            "Fecha", "Venta_Efectivo", "Venta_MP", "Total_Ventas", 
            "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta", 
            "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
            "Cant_Copias", "Costo_Copia_Unit", "Precio_Venta_Copia", "Total_Costo_Copias",
            "Ganancia_Neta", "Notas"
        ])
    
    df = pd.DataFrame(data)
    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'])
        
    cols_numericas = ['Total_Ventas', 'Ganancia_Neta', 'Total_Sueldos', 'Cant_Copias', 
                      'Costo_Copia_Unit', 'Precio_Venta_Copia', 'Gastos_Fijos', 'Total_Costo_Copias', 
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
    except:
        pass

    orden_cols = [
        "Fecha", "Venta_Efectivo", "Venta_MP", "Total_Ventas", 
        "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta", 
        "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
        "Cant_Copias", "Costo_Copia_Unit", "Precio_Venta_Copia", "Total_Costo_Copias",
        "Ganancia_Neta", "Notas"
    ]
    
    fila = []
    for col in orden_cols:
        val = record_dict.get(col, "")
        if isinstance(val, (datetime, date, pd.Timestamp)):
            val = val.strftime('%Y-%m-%d')
        fila.append(val)
    sheet.append_row(fila)

def delete_record_by_date(fecha_a_borrar):
    sheet = get_connection()
    fecha_str = fecha_a_borrar.strftime('%Y-%m-%d')
    try:
        cell = sheet.find(fecha_str)
        sheet.delete_rows(cell.row)
    except gspread.exceptions.CellNotFound:
        st.warning("No se encontró el registro.")

def get_periodo_copia(fecha):
    if fecha.day > 21:
        next_month = fecha.replace(day=28) + timedelta(days=4)
        return next_month.strftime("%Y-%m (Cierre 21)")
    else:
        return fecha.strftime("%Y-%m (Cierre 21)")

# --- 4. ACCESO ---
def check_password():
    clave_real = "libreria2024" 
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    
    if not st.session_state.password_correct:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.markdown("<br><br><h2 style='text-align: center;'>🔐 Acceso Seguro</h2>", unsafe_allow_html=True)
            pass_input = st.text_input("Contraseña", type="password")
            if st.button("Iniciar Sesión", type="primary", use_container_width=True):
                if pass_input == clave_real:
                    st.session_state.password_correct = True
                    st.rerun()
                else:
                    st.error("Incorrecta")
        return False
    return True

# --- 5. APP PRINCIPAL ---
if check_password():
    df = load_data()

    # === VALORES POR DEFECTO ACTUALIZADOS ===
    # Costo Hoja: $55 | Venta Hoja: $200
    def_margen = 50
    def_valor_hora = 2000.0
    def_costo_copia = 55.0  # <--- ACTUALIZADO A $55
    def_venta_copia = 200.0 # <--- ACTUALIZADO A $200
    def_gastos = 0.0

    # Si hay datos anteriores, intenta mantener la config del último día, 
    # pero si el último día tenía precios viejos, priorizamos tus nuevos costos fijos.
    if not df.empty:
        last = df.iloc[0]
        def_margen = int(last.get('Margen_Porc', 50))
        def_valor_hora = float(last.get('Valor_Hora', 2000.0))
        # Nota: Podríamos leer del historial, pero mejor forzamos tus nuevos costos
        # para que se actualicen en el formulario a partir de hoy.
        # def_costo_copia = float(last.get('Costo_Copia_Unit', 55.0)) 
        def_gastos = float(last.get('Gastos_Fijos', 0.0))

    # === SIDEBAR ===
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3330/3330314.png", width=50)
        st.title("Librería La Profe")
        st.markdown("---")
        
        with st.form("form_carga", clear_on_submit=True):
            st.subheader("📝 Nuevo Registro")
            fecha_input = st.date_input("Fecha", datetime.today())
            
            with st.expander("💰 Ingresos (Caja Total)", expanded=True):
                c1, c2 = st.columns(2)
                v_efec = c1.number_input("Efectivo Total ($)", min_value=0.0, format="%.2f", help="Poné TODO el efectivo que contaste en la caja (Librería + Copias)")
                v_mp = c2.number_input("Mercado Pago ($)", min_value=0.0, format="%.2f")
            
            with st.expander("🖨️ Fotocopiadora (Detalle)", expanded=True):
                c3, c4 = st.columns(2)
                cant_cop = c3.number_input("Cant. Copias", min_value=0, step=1)
                cost_cop = c4.number_input("Costo Insumos ($)", value=def_costo_copia, format="%.2f", help="Tu costo (Papel + Toner)")
                
                precio_venta_cop = st.number_input("Precio Venta ($)", value=def_venta_copia, format="%.2f", help="A cuánto vendés la copia promedio")
            
            with st.expander("📉 Gastos y Config"):
                c5, c6 = st.columns(2)
                h_staff = c5.number_input("Horas Ayuda", min_value=0.0, step=0.5)
                v_hora = c6.number_input("Valor Hora", value=def_valor_hora, format="%.2f")
                g_fijos = st.number_input("Gastos Varios", value=def_gastos, format="%.2f")
                margen = st.slider("Margen Librería (%)", 10, 90, def_margen)
                notas = st.text_input("Notas")
            
            if st.form_submit_button("💾 Guardar Cierre", type="primary"):
                # === LÓGICA DE CÁLCULO ===
                tot_ventas_caja = v_efec + v_mp
                
                # 1. Separamos la venta de copias
                ingreso_por_copias = cant_cop * precio_venta_cop
                
                # 2. Venta Librería = Caja Total - Venta Copias
                # (Usamos max(0, ...) para evitar números negativos si hubo un error de tipeo)
                ventas_libreria_real = max(0, tot_ventas_caja - ingreso_por_copias)
                
                # 3. Costo Mercadería (Solo sobre lápices, cuadernos, etc)
                cost_merc_libreria = ventas_libreria_real * (1 - (margen / 100))
                
                # 4. Costo Copias (Cantidad * $55)
                tot_cost_cop = cant_cop * cost_cop
                
                # 5. Ganancia Bruta
                g_bruta = tot_ventas_caja - cost_merc_libreria - tot_cost_cop
                
                # 6. Ganancia Neta
                tot_sueldos = h_staff * v_hora
                g_neta = g_bruta - g_fijos - tot_sueldos
                
                new_rec = {
                    "Fecha": fecha_input, 
                    "Venta_Efectivo": v_efec, "Venta_MP": v_mp, "Total_Ventas": tot_ventas_caja, 
                    "Margen_Porc": margen, 
                    "Costo_Mercaderia": cost_merc_libreria,
                    "Ganancia_Bruta": g_bruta,
                    "Gastos_Fijos": g_fijos, "Horas_Trabajadas": h_staff, "Valor_Hora": v_hora, "Total_Sueldos": tot_sueldos,
                    "Cant_Copias": cant_cop, "Costo_Copia_Unit": cost_cop, 
                    "Precio_Venta_Copia": precio_venta_cop,
                    "Total_Costo_Copias": tot_cost_cop, 
                    "Ganancia_Neta": g_neta, "Notas": notas
                }
                
                with st.spinner("Guardando..."):
                    save_new_record(new_rec)
                st.success("✅ Guardado correctamente.")
                st.rerun()
                
        if st.sidebar.button("🔒 Salir"):
            st.session_state.password_correct = False
            st.rerun()

    # === DASHBOARD ===
    st.markdown('<p class="main-header">Panel Financiero</p>', unsafe_allow_html=True)

    if not df.empty:
        col_f1, col_f2 = st.columns([1, 3])
        with col_f1:
            filtro = st.selectbox("📅 Ver:", ["Hoy", "7 Días", "Mes Actual", "Personalizado", "Ciclo Copias"])
        
        df_f = df.copy()
        df_f['Fecha_Solo'] = df_f['Fecha'].dt.date
        hoy = datetime.today().date()
        tit_rango = "Histórico"
        es_copias = False

        with col_f2:
            if filtro == "Hoy":
                df_f = df_f[df_f['Fecha_Solo'] == hoy]
                tit_rango = "HOY"
            elif filtro == "7 Días":
                ini = hoy - timedelta(days=7)
                df_f = df_f[(df_f['Fecha_Solo'] >= ini) & (df_f['Fecha_Solo'] <= hoy)]
                tit_rango = "ÚLTIMOS 7 DÍAS"
            elif filtro == "Mes Actual":
                ini = hoy.replace(day=1)
                df_f = df_f[(df_f['Fecha_Solo'] >= ini) & (df_f['Fecha_Solo'] <= hoy)]
                tit_rango = "ESTE MES"
            elif filtro == "Ciclo Copias":
                df['P_Fiscal'] = df['Fecha'].apply(get_periodo_copia)
                sel = st.selectbox("Periodo:", sorted(df['P_Fiscal'].unique(), reverse=True))
                df_f = df[df['P_Fiscal'] == sel].copy()
                tit_rango = f"CICLO {sel}"
                es_copias = True
            elif filtro == "Personalizado":
                c1, c2 = st.columns(2)
                f1 = c1.date_input("Desde", hoy - timedelta(days=30))
                f2 = c2.date_input("Hasta", hoy)
                if f1 <= f2: df_f = df_f[(df_f['Fecha_Solo'] >= f1) & (df_f['Fecha_Solo'] <= f2)]

        st.markdown("---")

        if df_f.empty:
            st.info("No hay datos.")
        else:
            pnl = df_f['Ganancia_Neta'].sum()
            ventas = df_f['Total_Ventas'].sum()
            utilidad = (pnl / ventas * 100) if ventas > 0 else 0
            
            st.markdown(f"""
            <div style="background-color: #EFF6FF; padding: 20px; border-radius: 12px; border-left: 6px solid #1E3A8A; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4 style="margin:0; color: #555;">GANANCIA NETA ({tit_rango})</h4>
                        <h1 style="margin:0; font-size: 45px; color: #1E3A8A;">${pnl:,.0f}</h1>
                    </div>
                    <div style="text-align: right;">
                        <h4 style="margin:0; color: #555;">RENTABILIDAD</h4>
                        <h2 style="margin:0; color: {'#16a34a' if utilidad > 20 else '#ca8a04'};">{utilidad:.1f}%</h2>
                    </div>
                </div>
            </div><br>
            """, unsafe_allow_html=True)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💰 Caja Total", f"${ventas:,.0f}")
            m2.metric("📦 Costo Mercadería", f"${df_f['Costo_Mercaderia'].sum():,.0f}", help="Costo reposición (sólo librería)")
            gastos_totales = df_f['Total_Sueldos'].sum() + df_f['Gastos_Fijos'].sum() + df_f['Total_Costo_Copias'].sum()
            m3.metric("💸 Gastos + Copias", f"${gastos_totales:,.0f}")
            m4.metric("📄 Cant. Copias", f"{df_f['Cant_Copias'].sum():,.0f}")

            tab1, tab2 = st.tabs(["📊 Gráficos", "📋 Datos"])
            
            with tab1:
                c_g1, c_g2 = st.columns(2)
                with c_g1:
                    st.subheader("Ventas vs Ganancia")
                    st.area_chart(df_f.groupby('Fecha')[['Total_Ventas', 'Ganancia_Neta']].sum(), color=["#93C5FD", "#1E3A8A"])
                with c_g2:
                    st.subheader("Composición de Gastos")
                    st.bar_chart(df_f[['Total_Sueldos', 'Gastos_Fijos', 'Total_Costo_Copias']].sum(), color="#64748B")
                
                if es_copias:
                    st.divider()
                    tot_c = df_f['Cant_Copias'].sum()
                    meta = 20000
                    st.metric("Progreso Meta Copias", f"{tot_c:,.0f} / {meta}", delta=tot_c-meta)

            with tab2:
                csv = df_f.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Descargar CSV", csv, "reporte.csv", "text/csv")
                
                cols_view = ["Fecha", "Total_Ventas", "Costo_Mercaderia", "Total_Costo_Copias", "Ganancia_Neta", "Notas"]
                st.dataframe(df_f[cols_view], use_container_width=True, hide_index=True)
                
                with st.expander("Borrar Registros"):
                    for i, r in df_f.iterrows():
                        c_txt, c_btn = st.columns([4,1])
                        c_txt.text(f"{r['Fecha'].date()} - ${r['Ganancia_Neta']:,.0f}")
                        if c_btn.button("Eliminar", key=f"d_{i}"):
                            delete_record_by_date(r['Fecha'])
                            st.success("Eliminado"); st.rerun()
