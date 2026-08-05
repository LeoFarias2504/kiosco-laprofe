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
            "Fecha", "Local", "Venta_Efectivo", "Venta_MP", "Total_Ventas", 
            "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta", 
            "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
            "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
            "Ganancia_Neta", "Notas"
        ])
    
    df = pd.DataFrame(data)
    
    if "Local" not in df.columns:
        df.insert(1, "Local", "Librería Principal")
    else:
        df["Local"] = df["Local"].replace("", "Librería Principal").fillna("Librería Principal")
    
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
    except:
        pass

    orden_cols = [
        "Fecha", "Local", "Venta_Efectivo", "Venta_MP", "Total_Ventas", 
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

def delete_record_by_date_and_local(fecha_a_borrar, local_a_borrar):
    sheet = get_connection()
    fecha_str = fecha_a_borrar.strftime('%Y-%m-%d') if not isinstance(fecha_a_borrar, str) else fecha_a_borrar
    
    data = sheet.get_all_records()
    row_to_delete = None
    
    for i, row in enumerate(data):
        if str(row.get('Fecha', ''))[:10] == fecha_str[:10] and str(row.get('Local', 'Librería Principal')) == local_a_borrar:
            row_to_delete = i + 2
            break
            
    if row_to_delete:
        sheet.delete_rows(row_to_delete)
    else:
        st.warning("No se encontró el registro exacto.")

def update_record_in_sheet(original_fecha, original_local, new_record_dict):
    sheet = get_connection()
    fecha_str = original_fecha.strftime('%Y-%m-%d') if not isinstance(original_fecha, str) else original_fecha
    
    data = sheet.get_all_records()
    row_to_update = None
    
    for i, row in enumerate(data):
        if str(row.get('Fecha', ''))[:10] == fecha_str[:10] and str(row.get('Local', 'Librería Principal')) == original_local:
            row_to_update = i + 2
            break
            
    if row_to_update:
        orden_cols = [
            "Fecha", "Local", "Venta_Efectivo", "Venta_MP", "Total_Ventas", 
            "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta", 
            "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
            "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
            "Ganancia_Neta", "Notas"
        ]
        fila_a_subir = []
        for col in orden_cols:
            val = new_record_dict.get(col, "")
            if isinstance(val, (datetime, date, pd.Timestamp)):
                val = val.strftime('%Y-%m-%d')
            fila_a_subir.append(val)
            
        sheet.update(values=[fila_a_subir], range_name=f"A{row_to_update}:Q{row_to_update}")
    else:
        st.error("No se pudo encontrar la fila original para actualizar.")

def recalculate_all_history():
    sheet = get_connection()
    data = sheet.get_all_records()
    if not data: return

    df = pd.DataFrame(data)
    updated_rows = []
    
    headers = [
        "Fecha", "Local", "Venta_Efectivo", "Venta_MP", "Total_Ventas", 
        "Margen_Porc", "Costo_Mercaderia", "Ganancia_Bruta", 
        "Gastos_Fijos", "Horas_Trabajadas", "Valor_Hora", "Total_Sueldos",
        "Cant_Copias", "Costo_Copia_Unit", "Total_Costo_Copias",
        "Ganancia_Neta", "Notas"
    ]
    updated_rows.append(headers)

    for i, row in df.iterrows():
        def clean_float(val):
            return float(str(val).replace('$','').replace(',','')) if val else 0.0

        total_ventas = clean_float(row.get('Total_Ventas', 0))
        margen_porc = clean_float(row.get('Margen_Porc', 50))
        cant_copias = clean_float(row.get('Cant_Copias', 0))
        costo_copia_unit = clean_float(row.get('Costo_Copia_Unit', 0))
        gastos_fijos = clean_float(row.get('Gastos_Fijos', 0))
        total_sueldos = clean_float(row.get('Total_Sueldos', 0))
        
        local = str(row.get('Local', '')).strip()
        if not local:
            local = "Librería Principal"
        
        costo_mercaderia = total_ventas * (1 - (margen_porc / 100))
        total_costo_copias = cant_copias * costo_copia_unit
        ganancia_bruta = total_ventas - costo_mercaderia
        ganancia_neta = ganancia_bruta - gastos_fijos - total_sueldos
        
        new_row = [
            row.get('Fecha'), local, row.get('Venta_Efectivo'), row.get('Venta_MP'),
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

    # --- MEMORIA DE VALORES POR DEFECTO PARA CADA LOCAL ---
    # Valores base por si no hay registros previos
    def_m_lib, def_vh_lib, def_cc_lib, def_gf_lib = 50, 2000.0, 55.0, 0.0
    def_m_col, def_vh_col, def_cc_col, def_gf_col = 50, 2000.0, 55.0, 0.0

    if not df.empty:
        # Extraemos los últimos datos de la Librería
        df_lib = df[df['Local'] == "Librería Principal"]
        if not df_lib.empty:
            last_lib = df_lib.iloc[0]
            def_m_lib = int(last_lib.get('Margen_Porc', 50))
            def_vh_lib = float(last_lib.get('Valor_Hora', 2000.0))
            def_cc_lib = float(last_lib.get('Costo_Copia_Unit', 55.0))
            def_gf_lib = float(last_lib.get('Gastos_Fijos', 0.0))
            
        # Extraemos los últimos datos del Colegio
        df_col = df[df['Local'] == "Colegio"]
        if not df_col.empty:
            last_col = df_col.iloc[0]
            def_m_col = int(last_col.get('Margen_Porc', 50))
            def_vh_col = float(last_col.get('Valor_Hora', 2000.0))
            def_cc_col = float(last_col.get('Costo_Copia_Unit', 55.0))
            def_gf_col = float(last_col.get('Gastos_Fijos', 0.0))

    # --- SIDEBAR (CARGA POR PESTAÑAS) ---
    with st.sidebar:
        st.title("📚 LIBRERIA LA PROFE")
        st.markdown("---")
        
        tab_lib, tab_col = st.tabs(["🏠 Librería", "🏫 Colegio"])
        
        # --- FORMULARIO 1: LIBRERÍA ---
        with tab_lib:
            with st.form("form_lib", clear_on_submit=True):
                st.subheader("📝 Cierre Librería")
                fecha_lib = st.date_input("Fecha", datetime.today(), key="fecha_lib")
                
                st.markdown("##### 1. Ingresos (Caja)")
                c1, c2 = st.columns(2)
                venta_efvo_lib = c1.number_input("Efectivo Total ($)", min_value=0.0, format="%.2f", key="efvo_lib")
                venta_mp_lib = c2.number_input("Mercado Pago ($)", min_value=0.0, format="%.2f", key="mp_lib")
                
                st.markdown("##### 2. Copias (Solo Informativo)")
                c3, c4 = st.columns(2)
                cant_copias_lib = c3.number_input("Cantidad Copias", min_value=0, step=1, key="cant_lib")
                costo_copia_lib = c4.number_input("Costo Insumo ($)", value=def_cc_lib, format="%.2f", key="costo_c_lib")
                
                st.markdown("##### 3. Gastos")
                c5, c6 = st.columns(2)
                horas_staff_lib = c5.number_input("Horas Staff", min_value=0.0, step=0.5, key="horas_lib")
                valor_hora_lib = c6.number_input("Valor Hora ($)", value=def_vh_lib, format="%.2f", key="v_hora_lib")
                gastos_fijos_lib = st.number_input("Otros Gastos Fijos", value=def_gf_lib, format="%.2f", key="g_fijos_lib")
                
                st.markdown("##### 4. Config")
                margen_input_lib = st.slider("Margen (%)", 10, 90, def_m_lib, key="margen_lib")
                notas_lib = st.text_input("Notas", key="notas_lib")
                
                if st.form_submit_button("☁️ Guardar Librería"):
                    total_ventas = venta_efvo_lib + venta_mp_lib
                    costo_mercaderia = total_ventas * (1 - (margen_input_lib / 100))
                    total_costo_copias = cant_copias_lib * costo_copia_lib
                    ganancia_bruta = total_ventas - costo_mercaderia
                    total_sueldos = horas_staff_lib * valor_hora_lib
                    ganancia_neta = ganancia_bruta - gastos_fijos_lib - total_sueldos
                    
                    new_record = {
                        "Fecha": fecha_lib, "Local": "Librería Principal",
                        "Venta_Efectivo": venta_efvo_lib, "Venta_MP": venta_mp_lib, "Total_Ventas": total_ventas, 
                        "Margen_Porc": margen_input_lib, "Costo_Mercaderia": costo_mercaderia, 
                        "Ganancia_Bruta": ganancia_bruta, "Gastos_Fijos": gastos_fijos_lib, 
                        "Horas_Trabajadas": horas_staff_lib, "Valor_Hora": valor_hora_lib, "Total_Sueldos": total_sueldos,
                        "Cant_Copias": cant_copias_lib, "Costo_Copia_Unit": costo_copia_lib, 
                        "Total_Costo_Copias": total_costo_copias, "Ganancia_Neta": ganancia_neta, "Notas": notas_lib
                    }
                    with st.spinner("Subiendo datos..."):
                        save_new_record(new_record)
                    st.success("¡Librería guardada!")
                    st.rerun()

        # --- FORMULARIO 2: COLEGIO ---
        with tab_col:
            with st.form("form_col", clear_on_submit=True):
                st.subheader("📝 Cierre Colegio")
                fecha_col = st.date_input("Fecha", datetime.today(), key="fecha_col")
                
                st.markdown("##### 1. Ingresos (Caja)")
                c1, c2 = st.columns(2)
                venta_efvo_col = c1.number_input("Efectivo Total ($)", min_value=0.0, format="%.2f", key="efvo_col")
                venta_mp_col = c2.number_input("Mercado Pago ($)", min_value=0.0, format="%.2f", key="mp_col")
                
                st.markdown("##### 2. Copias (Solo Informativo)")
                c3, c4 = st.columns(2)
                cant_copias_col = c3.number_input("Cantidad Copias", min_value=0, step=1, key="cant_col")
                costo_copia_col = c4.number_input("Costo Insumo ($)", value=def_cc_col, format="%.2f", key="costo_c_col")
                
                st.markdown("##### 3. Gastos")
                c5, c6 = st.columns(2)
                horas_staff_col = c5.number_input("Horas Staff", min_value=0.0, step=0.5, key="horas_col")
                valor_hora_col = c6.number_input("Valor Hora ($)", value=def_vh_col, format="%.2f", key="v_hora_col")
                gastos_fijos_col = st.number_input("Otros Gastos Fijos", value=def_gf_col, format="%.2f", key="g_fijos_col")
                
                st.markdown("##### 4. Config")
                margen_input_col = st.slider("Margen (%)", 10, 90, def_m_col, key="margen_col")
                notas_col = st.text_input("Notas", key="notas_col")
                
                if st.form_submit_button("☁️ Guardar Colegio"):
                    total_ventas = venta_efvo_col + venta_mp_col
                    costo_mercaderia = total_ventas * (1 - (margen_input_col / 100))
                    total_costo_copias = cant_copias_col * costo_copia_col
                    ganancia_bruta = total_ventas - costo_mercaderia
                    total_sueldos = horas_staff_col * valor_hora_col
                    ganancia_neta = ganancia_bruta - gastos_fijos_col - total_sueldos
                    
                    new_record = {
                        "Fecha": fecha_col, "Local": "Colegio",
                        "Venta_Efectivo": venta_efvo_col, "Venta_MP": venta_mp_col, "Total_Ventas": total_ventas, 
                        "Margen_Porc": margen_input_col, "Costo_Mercaderia": costo_mercaderia, 
                        "Ganancia_Bruta": ganancia_bruta, "Gastos_Fijos": gastos_fijos_col, 
                        "Horas_Trabajadas": horas_staff_col, "Valor_Hora": valor_hora_col, "Total_Sueldos": total_sueldos,
                        "Cant_Copias": cant_copias_col, "Costo_Copia_Unit": costo_copia_col, 
                        "Total_Costo_Copias": total_costo_copias, "Ganancia_Neta": ganancia_neta, "Notas": notas_col
                    }
                    with st.spinner("Subiendo datos..."):
                        save_new_record(new_record)
                    st.success("¡Colegio guardado!")
                    st.rerun()

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

    # --- DASHBOARD PRINCIPAL ---
    st.title("📊 GESTION LIBRERIA LA PROFE")

    if not df.empty:
        # --- FILTROS GLOBALES ---
        st.markdown("### 🔍 Visualización")
        
        filtro_local = st.radio("📍 Seleccionar Local:", ["Ambos Locales", "Librería Principal", "Colegio"], horizontal=True)
        
        filtro_col, periodo_col = st.columns([1, 3])
        with filtro_col:
            opcion_filtro = st.radio("Filtrar por Fecha:", ["Hoy", "Última Semana", "Rango Personalizado", "Mes (Ciclo Copias)"])

        # Aplicamos filtro de Local
        df_filtrado = df.copy()
        if filtro_local != "Ambos Locales":
            df_filtrado = df_filtrado[df_filtrado["Local"] == filtro_local]

        # Aplicamos filtro de Fecha
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
                if meses:
                    mes_sel = st.selectbox("Selecciona Periodo:", meses)
                    df_filtrado = df_filtrado[df_filtrado['Periodo_Fiscal'] == mes_sel].copy()
                    titulo_periodo = f"PERIODO {mes_sel}"
                    es_vista_mes = True

        st.divider()

        # === MODO EDICIÓN ===
        if "edit_record" in st.session_state:
            st.markdown("### ✏️ Modificar Registro")
            rec = st.session_state.edit_record
            
            with st.form("form_edit"):
                st.info(f"Editando registro del **{rec['Fecha'].strftime('%d/%m/%Y')}** - **{rec['Local']}**")
                
                c_e1, c_e2 = st.columns(2)
                edit_efvo = c_e1.number_input("Efectivo ($)", value=float(rec['Venta_Efectivo']))
                edit_mp = c_e2.number_input("Mercado Pago ($)", value=float(rec['Venta_MP']))
                
                c_e3, c_e4, c_e5 = st.columns(3)
                edit_copias = c_e3.number_input("Cant. Copias", value=int(rec['Cant_Copias']))
                edit_costo_c = c_e4.number_input("Costo Insumo", value=float(rec['Costo_Copia_Unit']))
                edit_margen = c_e5.slider("Margen (%)", 10, 90, int(rec['Margen_Porc']))
                
                c_e6, c_e7, c_e8 = st.columns(3)
                edit_horas = c_e6.number_input("Horas Staff", value=float(rec['Horas_Trabajadas']))
                edit_v_hora = c_e7.number_input("Valor Hora ($)", value=float(rec['Valor_Hora']))
                edit_fijos = c_e8.number_input("Gastos Fijos", value=float(rec['Gastos_Fijos']))
                
                edit_notas = st.text_input("Notas", value=str(rec['Notas']))
                
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                        total_ventas = edit_efvo + edit_mp
                        costo_mercaderia = total_ventas * (1 - (edit_margen / 100))
                        total_costo_copias = edit_copias * edit_costo_c
                        ganancia_bruta = total_ventas - costo_mercaderia
                        total_sueldos = edit_horas * edit_v_hora
                        ganancia_neta = ganancia_bruta - edit_fijos - total_sueldos
                        
                        updated_rec = {
                            "Fecha": rec['Fecha'], "Local": rec['Local'],
                            "Venta_Efectivo": edit_efvo, "Venta_MP": edit_mp, "Total_Ventas": total_ventas, 
                            "Margen_Porc": edit_margen, "Costo_Mercaderia": costo_mercaderia, 
                            "Ganancia_Bruta": ganancia_bruta, "Gastos_Fijos": edit_fijos, 
                            "Horas_Trabajadas": edit_horas, "Valor_Hora": edit_v_hora, "Total_Sueldos": total_sueldos,
                            "Cant_Copias": edit_copias, "Costo_Copia_Unit": edit_costo_c, 
                            "Total_Costo_Copias": total_costo_copias, "Ganancia_Neta": ganancia_neta, "Notas": edit_notas
                        }
                        
                        with st.spinner("Actualizando en la nube..."):
                            update_record_in_sheet(rec['Fecha'], rec['Local'], updated_rec)
                        
                        del st.session_state.edit_record
                        st.success("¡Registro actualizado con éxito!")
                        st.rerun()
                        
                with col_cancel:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state.edit_record
                        st.rerun()
            st.divider()

        if df_filtrado.empty:
            st.info(f"No hay datos para mostrar.")
        else:
            # === CARTEL PNL VERDE ===
            pnl_total = df_filtrado['Ganancia_Neta'].sum()
            ventas_total = df_filtrado['Total_Ventas'].sum()
            porc_utilidad = (pnl_total / ventas_total * 100) if ventas_total > 0 else 0
            
            titulo_cartel = f"GANANCIA NETA ({titulo_periodo})"
            if filtro_local != "Ambos Locales":
                titulo_cartel += f" - {filtro_local.upper()}"

            st.markdown(f"""
            <div style="background-color: #d1e7dd; border: 1px solid #198754; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; max-width: 600px; margin: 0 auto;">
                <h3 style="color: #0f5132; margin:0; font-size: 18px;">{titulo_cartel}</h3>
                <h1 style="color: #198754; font-size: 45px; margin:0; font-weight: bold;">${pnl_total:,.0f}</h1>
                <p style="color: #0f5132; margin:0; font-size: 16px; margin-top: 5px;">Utilidad Real: <strong>{porc_utilidad:.1f}%</strong></p>
            </div><br>
            """, unsafe_allow_html=True)

            # === MÉTRICAS ===
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Ventas Totales", f"${ventas_total:,.0f}")
            col2.metric("Sueldos", f"${df_filtrado['Total_Sueldos'].sum():,.0f}")
            col3.metric("Gastos Fijos", f"${df_filtrado['Gastos_Fijos'].sum():,.0f}")
            tot_cost_copias = df_filtrado['Total_Costo_Copias'].sum()
            col4.metric("Costo Copias (Info)", f"${tot_cost_copias:,.0f}", help="Incluido en Costo Mercadería.")

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
            
            # === TABLA DE REGISTROS ===
            st.markdown("### 📋 Gestión de Registros")
            
            h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2])
            h1.markdown("**Fecha**")
            h2.markdown("**Ventas**")
            h3.markdown("**Costo Rep.**")
            h4.markdown("**C. Copias**") 
            h5.markdown("**Sueldos**")
            h6.markdown("**Gastos Fijos**") 
            h7.markdown("**Neta**")
            h8.markdown("**Acción**")
            
            st.markdown("---")

            for index, row in df_filtrado.iterrows():
                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2])
                
                icono_local = "🏠" if row['Local'] == "Librería Principal" else "🏫"
                c1.write(f"{row['Fecha'].strftime('%d/%m')} {icono_local}")
                
                c2.write(f"${row['Total_Ventas']:,.0f}")
                c3.write(f"${row['Costo_Mercaderia']:,.0f}")
                c4.write(f"${row['Total_Costo_Copias']:,.0f}")
                c5.write(f"${row['Total_Sueldos']:,.0f}")
                c6.write(f"${row['Gastos_Fijos']:,.0f}") 
                
                color = "green" if row['Ganancia_Neta'] >= 0 else "red"
                c7.markdown(f":{color}[**${row['Ganancia_Neta']:,.0f}**]")
                
                # Botones de Edición y Borrado
                col_btn1, col_btn2 = c8.columns(2)
                
                key_edit = f"edit_{row['Fecha'].strftime('%Y%m%d')}_{row['Local']}_{index}"
                if col_btn1.button("✏️", key=key_edit):
                    st.session_state.edit_record = row.to_dict()
                    st.rerun()

                key_del = f"del_{row['Fecha'].strftime('%Y%m%d')}_{row['Local']}_{index}"
                if col_btn2.button("🗑️", key=key_del):
                    with st.spinner("Borrando..."):
                        delete_record_by_date_and_local(row['Fecha'], row['Local'])
                    st.success("Borrado.")
                    st.rerun()

    else:
        st.info("👋 La base de datos está vacía. Carga el primer registro a la izquierda.")
        st.info("👋 La base de datos está vacía. Carga el primer registro a la izquierda.")
