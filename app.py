import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, date

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="GESTION LIBRERIA LA PROFE", layout="wide", page_icon="📚")

# --- 2. CONEXIÓN A GOOGLE SHEETS (HIBRIDA Y ROBUSTA) ---
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_connection():
    """Conecta con Google Sheets (Compatible con PC y Nube)"""
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            
            # Convierte los "\\n" literales en saltos de línea reales (Fix clave privada)
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

# --- 3. FUNCIONES DE DATOS (NUBE) ---
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
    
    # Limpieza de fechas
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
            headers = [
                "Fecha", "Venta_Efectivo", "Venta_MP", "Total_Ventas", 
                "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta", 
                "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
                "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
                "Ganancia_Neta", "Notas"
            ]
            sheet.append_row(headers)
    except:
        headers = list(record_dict.keys())

    fila_a_subir = []
    for col in headers:
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

# --- 4. SISTEMA DE LOGIN ---
def check_password():
    clave_real = "libreria2024" 
    
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        st.markdown("<h1 style='text-align: center;'>🔒 Acceso La Profe</h1>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,2,1])
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

# --- EJECUCIÓN PRINCIPAL ---
if check_password():
    
    with st.spinner('Conectando con Google Drive...'):
        df = load_data()

    # --- MEMORIA (Defaults) ---
    default_margen = 50
    default_valor_hora = 2000.0
    default_costo_copia = 10.0
    default_gastos_fijos = 0.0

    if not df.empty:
        last_row = df.iloc[0]
        default_margen = int(last_row.get('Margen_Porc', 50))
        default_valor_hora = float(last_row.get('Valor_Hora', 2000.0))
        default_costo_copia = float(last_row.get('Costo_Copia_Unit', 10.0))
        default_gastos_fijos = float(last_row.get('Gastos_Fijos', 0.0))

    # --- SIDEBAR ---
    with st.sidebar:
        st.title("📚 LIBRERIA LA PROFE")
        st.success("🟢 Conectado a Nube")
        st.markdown("---")
        
        with st.form("daily_form", clear_on_submit=True):
            st.subheader("📝 Nuevo Registro")
            fecha = st.date_input("Fecha", datetime.today())
            
            st.markdown("##### 1. Ventas")
            c1, c2 = st.columns(2)
            venta_efvo = c1.number_input("Efectivo ($)", min_value=0.0, format="%.2f")
            venta_mp = c2.number_input("Mercado Pago ($)", min_value=0.0, format="%.2f")
            
            st.markdown("##### 2. Copias")
            c3, c4 = st.columns(2)
            cant_copias = c3.number_input("Cantidad", min_value=0, step=1)
            costo_copia = c4.number_input("Costo Unit. ($)", min_value=0.0, value=default_costo_copia, format="%.2f")
            
            st.markdown("##### 3. Gastos")
            c5, c6 = st.columns(2)
            horas_staff = c5.number_input("Horas Staff", min_value=0.0, step=0.5)
            valor_hora = c6.number_input("Valor Hora ($)", min_value=0.0, value=default_valor_hora, format="%.2f")
            gastos_fijos = st.number_input("Otros Gastos Fijos", min_value=0.0, value=default_gastos_fijos, format="%.2f")
            
            st.markdown("##### 4. Config")
            margen_input = st.slider("Margen (%)", 10, 90, default_margen)
            notas = st.text_input("Notas")
            
            submitted = st.form_submit_button("☁️ Guardar en Drive")

            if submitted:
                total_ventas = venta_efvo + venta_mp
                costo_mercaderia = total_ventas * (1 - (margen_input / 100))
                ganancia_bruta = total_ventas - costo_mercaderia
                total_sueldos = horas_staff * valor_hora
                total_costo_copias = cant_copias * costo_copia
                ganancia_neta = ganancia_bruta - gastos_fijos - total_sueldos - total_costo_copias
                
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
                
                with st.spinner("Subiendo datos a Google..."):
                    save_new_record(new_record)
                
                st.success("¡Guardado exitosamente!")
                st.rerun()
        
        if st.button("🔒 Cerrar Sesión"):
            st.session_state.password_correct = False
            st.rerun()

    # --- DASHBOARD PRINCIPAL ---
    st.title("📊 GESTION LIBRERIA LA PROFE")

    if not df.empty:
        # --- FILTROS ---
        st.markdown("### 🔍 Visualización")
        filtro_col, periodo_col = st.columns([1, 3])
        with filtro_col:
            # === AGREGADA OPCIÓN "RANGO PERSONALIZADO" ===
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
                df_filtrado = df_filtrado[(df_filtrado['Fecha_Solo'] >= inicio) & (df_filtrado['Fecha_Solo'] <= hoy)]
                titulo_periodo = "ÚLTIMOS 7 DÍAS"
                
            # === LÓGICA DE RANGO PERSONALIZADO ===
            elif opcion_filtro == "Rango Personalizado":
                c_inicio, c_fin = st.columns(2)
                f_inicio = c_inicio.date_input("Desde:", hoy - timedelta(days=30))
                f_fin = c_fin.date_input("Hasta:", hoy)
                
                if f_inicio <= f_fin:
                    df_filtrado = df_filtrado[(df_filtrado['Fecha_Solo'] >= f_inicio) & (df_filtrado['Fecha_Solo'] <= f_fin)]
                    titulo_periodo = f"DEL {f_inicio.strftime('%d/%m')} AL {f_fin.strftime('%d/%m')}"
                else:
                    st.error("La fecha de inicio debe ser anterior a la fecha de fin.")
                    df_filtrado = pd.DataFrame() # Vacío si hay error
                
            elif opcion_filtro == "Mes (Ciclo Copias)":
                df['Periodo_Fiscal'] = df['Fecha'].apply(get_periodo_copia)
                meses = sorted(df['Periodo_Fiscal'].unique(), reverse=True)
                mes_sel = st.selectbox("Selecciona Periodo:", meses)
                df_filtrado = df[df['Periodo_Fiscal'] == mes_sel].copy()
                titulo_periodo = f"PERIODO {mes_sel}"
                es_vista_mes = True

        st.divider()

        if df_filtrado.empty:
            st.info(f"No hay datos para: {titulo_periodo}")
        else:
            # === CARTEL PNL ===
            pnl_total = df_filtrado['Ganancia_Neta'].sum()
            st.markdown(f"""
            <div style="background-color: #d1e7dd; border: 1px solid #198754; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; max-width: 600px; margin: 0 auto;">
                <h3 style="color: #0f5132; margin:0; font-size: 18px;">GANANCIA NETA ({titulo_periodo})</h3>
                <h1 style="color: #198754; font-size: 45px; margin:0; font-weight: bold;">${pnl_total:,.0f}</h1>
            </div><br>
            """, unsafe_allow_html=True)

            # === MÉTRICAS ===
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Ventas", f"${df_filtrado['Total_Ventas'].sum():,.0f}")
            col2.metric("Sueldos", f"${df_filtrado['Total_Sueldos'].sum():,.0f}")
            col3.metric("Gastos Fijos", f"${df_filtrado['Gastos_Fijos'].sum():,.0f}")
            col4.metric("Copias (Cant)", f"{df_filtrado['Cant_Copias'].sum():,.0f}")

            if es_vista_mes:
                st.divider()
                st.subheader("🖨️ Análisis Mensual Copias")
                c1, c2, c3 = st.columns(3)
                tot_copias = df_filtrado['Cant_Copias'].sum()
                MINIMO = 20000
                costo_avg = df_filtrado['Costo_Copia_Unit'].mean() if tot_copias > 0 else 0
                
                c1.metric("Acumulado Mes", f"{tot_copias:,.0f}", f"Meta: {MINIMO}")
                if tot_copias < MINIMO:
                    pagar = MINIMO * costo_avg
                    c2.metric("A Pagar (Base)", f"${pagar:,.0f}")
                    c3.error(f"Faltan {MINIMO - tot_copias:,.0f}")
                else:
                    pagar = tot_copias * costo_avg
                    c2.metric("A Pagar (Real)", f"${pagar:,.0f}")
                    c3.success("Meta superada")

            st.divider()
            st.markdown("### 📋 Gestión de Registros")
            
            # === TABLA ===
            h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 0.8])
            h1.markdown("**Fecha**")
            h2.markdown("**Ventas**")
            h3.markdown("**Costo Rep.**")
            h4.markdown("**Sueldos**")
            h5.markdown("**Gastos**")
            h6.markdown("**Copias**")
            h7.markdown("**Neta**")
            h8.markdown("**Borrar**")
            
            st.markdown("---")

            for index, row in df_filtrado.iterrows():
                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 0.8])
                c1.write(row['Fecha'].strftime('%d/%m/%Y'))
                c2.write(f"${row['Total_Ventas']:,.0f}")
                
                costo_rep = row.get('Costo_Mercaderia', 0)
                c3.write(f"${costo_rep:,.0f}")
                
                c4.write(f"${row['Total_Sueldos']:,.0f}")
                c5.write(f"${row['Gastos_Fijos']:,.0f}")
                c6.write(f"${row['Total_Costo_Copias']:,.0f}")
                
                color = "green" if row['Ganancia_Neta'] > 0 else "red"
                c7.markdown(f":{color}[**${row['Ganancia_Neta']:,.0f}**]")
                
                key_btn = f"del_{row['Fecha'].strftime('%Y%m%d')}_{index}"
                
                if c8.button("🗑️", key=key_btn, help="Borrar de Google Drive"):
                    with st.spinner("Borrando de la nube..."):
                        delete_record_by_date(row['Fecha'])
                    st.success("Borrado.")
                    st.rerun()

    else:
        st.info("👋 La base de datos está vacía. Carga el primer registro a la izquierda.")
