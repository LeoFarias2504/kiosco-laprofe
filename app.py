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
        st.warning("No se encontró la fila.")

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
    
    with st.spinner('Conectando...'):
        df = load_data()

    # --- VALORES POR DEFECTO (CONFIGURADOS A TUS PRECIOS ACTUALES) ---
    def_margen = 50
    def_valor_hora = 2000.0
    def_costo_copia = 55.0  # Costo insumo
    def_venta_copia = 200.0 # Precio venta
    def_gastos = 0.0

    if not df.empty:
        last_row = df.iloc[0]
        def_margen = int(last_row.get('Margen_Porc', 50))
        def_valor_hora = float(last_row.get('Valor_Hora', 2000.0))
        # Mantenemos tus costos fijos nuevos aunque el historial tenga viejos
        # def_costo_copia = float(last_row.get('Costo_Copia_Unit', 55.0))
        def_gastos = float(last_row.get('Gastos_Fijos', 0.0))

    # --- SIDEBAR (DISEÑO VIEJO/SIMPLE) ---
    with st.sidebar:
        st.title("📚 LIBRERIA LA PROFE")
        st.markdown("---")
        
        with st.form("daily_form", clear_on_submit=True):
            st.subheader("📝 Nuevo Registro")
            fecha = st.date_input("Fecha", datetime.today())
            
            st.markdown("##### 1. Ingresos (Caja)")
            c1, c2 = st.columns(2)
            venta_efvo = c1.number_input("Efectivo Total ($)", min_value=0.0, format="%.2f", help="Suma total de billetes (Copias + Librería)")
            venta_mp = c2.number_input("Mercado Pago ($)", min_value=0.0, format="%.2f")
            
            st.markdown("##### 2. Copias (Detalle)")
            c3, c4 = st.columns(2)
            cant_copias = c3.number_input("Cantidad Copias", min_value=0, step=1)
            costo_copia = c4.number_input("Costo Insumo ($)", value=def_costo_copia, format="%.2f")
            
            precio_venta_cop = st.number_input("Precio Venta Copia ($)", value=def_venta_copia, format="%.2f", help="Precio al público")
            
            st.markdown("##### 3. Gastos")
            c5, c6 = st.columns(2)
            horas_staff = c5.number_input("Horas Staff", min_value=0.0, step=0.5)
            valor_hora = c6.number_input("Valor Hora ($)", value=def_valor_hora, format="%.2f")
            gastos_fijos = st.number_input("Otros Gastos Fijos", value=def_gastos, format="%.2f")
            
            st.markdown("##### 4. Config")
            margen_input = st.slider("Margen (%)", 10, 90, def_margen)
            notas = st.text_input("Notas")
            
            submitted = st.form_submit_button("☁️ Guardar en Drive")

            if submitted:
                # === LÓGICA CORREGIDA (SE MANTIENE) ===
                total_ventas = venta_efvo + venta_mp
                
                # 1. Separar venta de copias
                ingreso_copias = cant_copias * precio_venta_cop
                
                # 2. Venta Librería Pura (evitamos negativos)
                venta_libreria_pura = max(0, total_ventas - ingreso_copias)
                
                # 3. Costos
                costo_mercaderia = venta_libreria_pura * (1 - (margen_input / 100))
                total_costo_copias = cant_copias * costo_copia
                
                # 4. Ganancias
                ganancia_bruta = total_ventas - costo_mercaderia - total_costo_copias
                total_sueldos = horas_staff * valor_hora
                ganancia_neta = ganancia_bruta - gastos_fijos - total_sueldos
                
                new_record = {
                    "Fecha": fecha,
                    "Venta_Efectivo": venta_efvo, "Venta_MP": venta_mp, "Total_Ventas": total_ventas, 
                    "Margen_Porc": margen_input,
                    "Costo_Mercaderia": costo_mercaderia, 
                    "Ganancia_Bruta": ganancia_bruta,
                    "Gastos_Fijos": gastos_fijos, "Horas_Trabajadas": horas_staff, "Valor_Hora": valor_hora, "Total_Sueldos": total_sueldos,
                    "Cant_Copias": cant_copias, "Costo_Copia_Unit": costo_copia, 
                    "Precio_Venta_Copia": precio_venta_cop, # Guardamos el precio
                    "Total_Costo_Copias": total_costo_copias,
                    "Ganancia_Neta": ganancia_neta, "Notas": notas
                }
                
                with st.spinner("Subiendo datos..."):
                    save_new_record(new_record)
                
                st.success("¡Guardado exitosamente!")
                st.rerun()
        
        if st.button("🔒 Cerrar Sesión"):
            st.session_state.password_correct = False
            st.rerun()

    # --- DASHBOARD PRINCIPAL (DISEÑO VIEJO) ---
    st.title("📊 GESTION LIBRERIA LA PROFE")

    if not df.empty:
        # --- FILTROS (Radio buttons simples) ---
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
                df_filtrado = df_filtrado[(df_filtrado['Fecha_Solo'] >= inicio) & (df_filtrado['Fecha_Solo'] <= hoy)]
                titulo_periodo = "ÚLTIMOS 7 DÍAS"
                
            elif opcion_filtro == "Rango Personalizado":
                c_inicio, c_fin = st.columns(2)
                f_inicio = c_inicio.date_input("Desde:", hoy - timedelta(days=30))
                f_fin = c_fin.date_input("Hasta:", hoy)
                
                if f_inicio <= f_fin:
                    df_filtrado = df_filtrado[(df_filtrado['Fecha_Solo'] >= f_inicio) & (df_filtrado['Fecha_Solo'] <= f_fin)]
                    titulo_periodo = f"DEL {f_inicio.strftime('%d/%m')} AL {f_fin.strftime('%d/%m')}"
                
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
            # === CARTEL PNL VERDE (CLÁSICO) ===
            pnl_total = df_filtrado['Ganancia_Neta'].sum()
            ventas_total = df_filtrado['Total_Ventas'].sum()
            porc_utilidad = (pnl_total / ventas_total * 100) if ventas_total > 0 else 0

            st.markdown(f"""
            <div style="background-color: #d1e7dd; border: 1px solid #198754; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; max-width: 600px; margin: 0 auto;">
                <h3 style="color: #0f5132; margin:0; font-size: 18px;">GANANCIA NETA ({titulo_periodo})</h3>
                <h1 style="color: #198754; font-size: 45px; margin:0; font-weight: bold;">${pnl_total:,.0f}</h1>
                <p style="color: #0f5132; margin:0; font-size: 16px; margin-top: 5px;">Utilidad Real: <strong>{porc_utilidad:.1f}%</strong></p>
            </div><br>
            """, unsafe_allow_html=True)

            # === MÉTRICAS SIMPLES ===
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Ventas", f"${ventas_total:,.0f}")
            col2.metric("Sueldos", f"${df_filtrado['Total_Sueldos'].sum():,.0f}")
            
            gastos_totales = df_filtrado['Gastos_Fijos'].sum() + df_filtrado['Total_Costo_Copias'].sum()
            col3.metric("Gastos + Copias", f"${gastos_totales:,.0f}")
            col4.metric("Copias (Cant)", f"{df_filtrado['Cant_Copias'].sum():,.0f}")

            if es_vista_mes:
                st.divider()
                st.subheader("🖨️ Análisis Mensual Copias")
                c1, c2, c3 = st.columns(3)
                tot_copias = df_filtrado['Cant_Copias'].sum()
                MINIMO = 20000
                c1.metric("Acumulado Mes", f"{tot_copias:,.0f}", f"Meta: {MINIMO}")
                if tot_copias < MINIMO:
                    c3.error(f"Faltan {MINIMO - tot_copias:,.0f}")
                else:
                    c3.success("Meta superada")

            st.divider()
            
            # === TABLA SIMPLE (SIN DATAFRAME PRO) ===
            st.markdown("### 📋 Gestión de Registros")
            
            h1, h2, h3, h4, h5, h6 = st.columns([1.5, 1.5, 1.5, 1.5, 1.5, 1])
            h1.markdown("**Fecha**")
            h2.markdown("**Ventas**")
            h3.markdown("**Costo Rep.**")
            h4.markdown("**Gastos Tot.**")
            h5.markdown("**Neta**")
            h6.markdown("**Acción**")
            
            st.markdown("---")

            for index, row in df_filtrado.iterrows():
                c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1.5, 1.5, 1.5, 1.5, 1])
                c1.write(row['Fecha'].strftime('%d/%m'))
                c2.write(f"${row['Total_Ventas']:,.0f}")
                c3.write(f"${row['Costo_Mercaderia']:,.0f}")
                
                gastos_row = row['Total_Sueldos'] + row['Gastos_Fijos'] + row['Total_Costo_Copias']
                c4.write(f"${gastos_row:,.0f}")
                
                color = "green" if row['Ganancia_Neta'] > 0 else "red"
                c5.markdown(f":{color}[**${row['Ganancia_Neta']:,.0f}**]")
                
                key_btn = f"del_{row['Fecha'].strftime('%Y%m%d')}_{index}"
                if c6.button("🗑️", key=key_btn):
                    with st.spinner("Borrando..."):
                        delete_record_by_date(row['Fecha'])
                    st.success("Borrado.")
                    st.rerun()

    else:
        st.info("👋 La base de datos está vacía. Carga el primer registro a la izquierda.")
