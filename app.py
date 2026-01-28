import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, date

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="GESTION LIBRERIA LA PROFE", layout="wide", page_icon="📚")

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
        sheet = client.open("Base_Datos_Kiosco").sheet1 
        return sheet
    except Exception as e:
        st.error(f"Error de conexión: {e}")
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
            "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
            "Ganancia_Neta", "Notas"
        ])
    
    df = pd.DataFrame(data)
    
    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'])
        
    cols_numericas = ['Total_Ventas', 'Ganancia_Neta', 'Total_Sueldos', 'Cant_Copias', 
                      'Costo_Copia_Unit', 'Gastos_Fijos', 'Total_Costo_Copias', 
                      'Valor_Hora', 'Margen_Porc', 'Costo_Mercaderia']
    
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

    fila_a_subir = []
    # Ordenamos basado en una lista fija para evitar errores si cambia el dict
    orden_cols = [
        "Fecha", "Venta_Efectivo", "Venta_MP", "Total_Ventas", 
        "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta", 
        "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
        "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
        "Ganancia_Neta", "Notas"
    ]
    
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
        st.warning("No se encontró la fila en la hoja de cálculo.")

def get_periodo_copia(fecha):
    if fecha.day > 21:
        next_month = fecha.replace(day=28) + timedelta(days=4)
        return next_month.strftime("%Y-%m (Cierre 21)")
    else:
        return fecha.strftime("%Y-%m (Cierre 21)")

# --- 4. LOGIN ---
def check_password():
    clave_real = "libreria2024" 
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.markdown("<h1 style='text-align: center;'>🔒 Acceso La Profe</h1>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            pass_input = st.text_input("Contraseña", type="password")
            if st.button("Ingresar", type="primary"):
                if pass_input == clave_real:
                    st.session_state.password_correct = True
                    st.rerun()
                else:
                    st.error("❌ Incorrecta")
        return False
    return True

# --- APP ---
if check_password():
    with st.spinner('Cargando datos...'):
        df = load_data()

    # Defaults
    default_margen, default_valor_hora, default_costo_copia, default_gastos = 50, 2000.0, 10.0, 0.0
    if not df.empty:
        last = df.iloc[0]
        default_margen = int(last.get('Margen_Porc', 50))
        default_valor_hora = float(last.get('Valor_Hora', 2000.0))
        default_costo_copia = float(last.get('Costo_Copia_Unit', 10.0))
        default_gastos = float(last.get('Gastos_Fijos', 0.0))

    # --- SIDEBAR (Entrada) ---
    with st.sidebar:
        st.title("📚 LIBRERIA LA PROFE")
        st.markdown("---")
        with st.form("daily", clear_on_submit=True):
            st.subheader("📝 Nuevo Registro")
            fecha = st.date_input("Fecha", datetime.today())
            st.markdown("##### 1. Ventas")
            c1, c2 = st.columns(2)
            v_efec = c1.number_input("Efectivo ($)", min_value=0.0, format="%.2f")
            v_mp = c2.number_input("MP ($)", min_value=0.0, format="%.2f")
            st.markdown("##### 2. Copias")
            c3, c4 = st.columns(2)
            cant_cop = c3.number_input("Cant. Copias", min_value=0, step=1)
            cost_cop = c4.number_input("Costo Unit.", value=default_costo_copia, format="%.2f")
            st.markdown("##### 3. Gastos")
            c5, c6 = st.columns(2)
            h_staff = c5.number_input("Horas Staff", min_value=0.0, step=0.5)
            v_hora = c6.number_input("Valor Hora", value=default_valor_hora, format="%.2f")
            g_fijos = st.number_input("Gastos Fijos", value=default_gastos, format="%.2f")
            st.markdown("##### 4. Config")
            margen = st.slider("Margen (%)", 10, 90, default_margen)
            notas = st.text_input("Notas")
            
            if st.form_submit_button("💾 Guardar"):
                tot_ventas = v_efec + v_mp
                cost_merc = tot_ventas * (1 - (margen / 100))
                g_bruta = tot_ventas - cost_merc
                tot_sueldos = h_staff * v_hora
                tot_cost_cop = cant_cop * cost_cop
                g_neta = g_bruta - g_fijos - tot_sueldos - tot_cost_cop
                
                new_rec = {
                    "Fecha": fecha, "Venta_Efectivo": v_efec, "Venta_MP": v_mp,
                    "Total_Ventas": tot_ventas, "Margen_Porc": margen,
                    "Costo_Mercaderia": cost_merc, "Ganancia_Bruta": g_bruta,
                    "Gastos_Fijos": g_fijos, "Horas_Trabajadas": h_staff,
                    "Valor_Hora": v_hora, "Total_Sueldos": tot_sueldos,
                    "Cant_Copias": cant_cop, "Costo_Copia_Unit": cost_cop,
                    "Total_Costo_Copias": tot_cost_cop, "Ganancia_Neta": g_neta, "Notas": notas
                }
                save_new_record(new_rec)
                st.success("Guardado!")
                st.rerun()

    # --- DASHBOARD ---
    st.title("📊 GESTION LIBRERIA LA PROFE")

    if not df.empty:
        # Filtros
        c_filt, c_per = st.columns([1, 3])
        with c_filt:
            filtro = st.radio("Ver:", ["Hoy", "Semana", "3 Meses", "Personalizado", "Ciclo Copias"])
        
        df_f = df.copy()
        df_f['Fecha_Solo'] = df_f['Fecha'].dt.date
        hoy = datetime.today().date()
        tit = "Todo"
        es_mes = False

        with c_per:
            st.write("")
            if filtro == "Hoy":
                df_f = df_f[df_f['Fecha_Solo'] == hoy]
                tit = "HOY"
            elif filtro == "Semana":
                ini = hoy - timedelta(days=7)
                df_f = df_f[(df_f['Fecha_Solo'] >= ini) & (df_f['Fecha_Solo'] <= hoy)]
                tit = "ÚLTIMOS 7 DÍAS"
            elif filtro == "3 Meses":
                ini = hoy - timedelta(days=90)
                df_f = df_f[(df_f['Fecha_Solo'] >= ini) & (df_f['Fecha_Solo'] <= hoy)]
                tit = "ÚLTIMOS 3 MESES"
            elif filtro == "Personalizado":
                c1, c2 = st.columns(2)
                f1 = c1.date_input("Desde", hoy - timedelta(days=30))
                f2 = c2.date_input("Hasta", hoy)
                if f1 <= f2:
                    df_f = df_f[(df_f['Fecha_Solo'] >= f1) & (df_f['Fecha_Solo'] <= f2)]
                    tit = f"{f1.strftime('%d/%m')} - {f2.strftime('%d/%m')}"
            elif filtro == "Ciclo Copias":
                df['P_Fiscal'] = df['Fecha'].apply(get_periodo_copia)
                mes = st.selectbox("Periodo:", sorted(df['P_Fiscal'].unique(), reverse=True))
                df_f = df[df['P_Fiscal'] == mes].copy()
                tit = f"PERIODO {mes}"
                es_mes = True

        st.markdown("---")
        
        if df_f.empty:
            st.warning("No hay datos en este periodo.")
        else:
            # KPIS
            pnl = df_f['Ganancia_Neta'].sum()
            ventas = df_f['Total_Ventas'].sum()
            utilidad = (pnl / ventas * 100) if ventas > 0 else 0
            
            st.markdown(f"""
            <div style="background-color: #d1e7dd; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #198754;">
                <h3 style="color: #0f5132; margin:0;">GANANCIA NETA ({tit})</h3>
                <h1 style="color: #198754; font-size: 40px; margin:0;">${pnl:,.0f}</h1>
                <p style="color: #0f5132; margin:0;">Margen Real: <strong>{utilidad:.1f}%</strong></p>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Ventas Totales", f"${ventas:,.0f}")
            c2.metric("Sueldos", f"${df_f['Total_Sueldos'].sum():,.0f}")
            c3.metric("Gastos Fijos", f"${df_f['Gastos_Fijos'].sum():,.0f}")
            c4.metric("Copias (Cant)", f"{df_f['Cant_Copias'].sum():,.0f}")

            # --- NUEVA SECCIÓN: GRÁFICOS ---
            st.markdown("### 📈 Tendencias")
            tab1, tab2 = st.tabs(["💰 Ventas vs Ganancia", "📉 Análisis Gastos"])
            
            with tab1:
                # Preparamos datos para gráfico de línea
                chart_data = df_f.groupby('Fecha')[['Total_Ventas', 'Ganancia_Neta']].sum()
                st.line_chart(chart_data, color=["#0000FF", "#00FF00"]) # Azul Ventas, Verde Ganancia
            
            with tab2:
                # Preparamos datos para gráfico de barras apiladas
                gastos_data = df_f.groupby('Fecha')[['Total_Sueldos', 'Gastos_Fijos', 'Total_Costo_Copias']].sum()
                st.bar_chart(gastos_data)

            # --- SECCIÓN COPIADORAS ---
            if es_mes:
                st.divider()
                st.subheader("🖨️ Control Copias")
                tot_cop = df_f['Cant_Copias'].sum()
                meta = 20000
                cost_avg = df_f['Costo_Copia_Unit'].mean() if tot_cop > 0 else 0
                k1, k2, k3 = st.columns(3)
                k1.metric("Acumulado", f"{tot_cop:,.0f}", f"Meta: {meta}")
                pagar = tot_cop * cost_avg if tot_cop > meta else meta * cost_avg
                k2.metric("A Pagar", f"${pagar:,.0f}")
                if tot_cop < meta:
                    k3.error(f"Faltan {meta - tot_cop:,.0f}")
                else:
                    k3.success("¡Meta Superada!")

            st.divider()
            
            # --- TABLA Y DESCARGA ---
            c_izq, c_der = st.columns([3, 1])
            c_izq.markdown("### 📋 Detalle de Movimientos")
            
            # Botón de Descarga Excel (CSV)
            csv = df_f.to_csv(index=False).encode('utf-8')
            c_der.download_button(
                label="📥 Descargar Excel",
                data=csv,
                file_name=f"reporte_kiosco_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

            # Encabezados tabla
            cols = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 0.8])
            titulos = ["Fecha", "Ventas", "Costo Rep.", "Sueldos", "Gastos", "Copias", "Neta", "Borrar"]
            for col, tit in zip(cols, titulos):
                col.markdown(f"**{tit}**")
            
            st.markdown("---")

            for idx, row in df_f.iterrows():
                cols = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 0.8])
                cols[0].write(row['Fecha'].strftime('%d/%m'))
                cols[1].write(f"${row['Total_Ventas']:,.0f}")
                cols[2].write(f"${row.get('Costo_Mercaderia',0):,.0f}")
                cols[3].write(f"${row['Total_Sueldos']:,.0f}")
                cols[4].write(f"${row['Gastos_Fijos']:,.0f}")
                cols[5].write(f"${row['Total_Costo_Copias']:,.0f}")
                color = "green" if row['Ganancia_Neta'] > 0 else "red"
                cols[6].markdown(f":{color}[**${row['Ganancia_Neta']:,.0f}**]")
                
                if cols[7].button("🗑️", key=f"d_{idx}"):
                    delete_record_by_date(row['Fecha'])
                    st.success("Borrado")
                    st.rerun()
    else:
        st.info("👋 Carga tu primer dato en el menú de la izquierda.")
