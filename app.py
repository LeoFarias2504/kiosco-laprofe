import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, date

# ============================================================
# 1. CONFIGURACIÓN
# ============================================================
st.set_page_config(page_title="Librería La Profe", layout="wide", page_icon="📚")

COPIAS_META_MENSUAL = 20_000

# ============================================================
# 2. CSS GLOBAL
# ============================================================
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }

#MainMenu, footer, header { visibility: hidden; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
}
[data-testid="stSidebar"] * { color: #e8e8e8 !important; }
[data-testid="stSidebar"] .stButton button {
    background: #0f3460; color: #e8e8e8 !important;
    border: 1px solid #e94560; border-radius: 6px;
    width: 100%; transition: background 0.2s;
}
[data-testid="stSidebar"] .stButton button:hover { background: #e94560; }
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] select,
[data-testid="stSidebar"] textarea {
    background: #0f3460 !important; color: #e8e8e8 !important;
    border: 1px solid #e94560 !important; border-radius: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button {
    background: #e94560 !important; color: white !important;
    border: none !important; font-weight: 600;
}
[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:hover {
    background: #c73652 !important;
}

h1 { color: #1a1a2e !important; letter-spacing: -0.5px; }
h2, h3 { color: #1a1a2e !important; }

[data-testid="stTabs"] [role="tab"] { font-weight: 600; color: #555; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #e94560 !important; border-bottom: 2px solid #e94560 !important;
}

[data-testid="stMetric"] {
    background: #f8f9fa; border: 1px solid #e9ecef;
    border-radius: 10px; padding: 12px 16px;
}
[data-testid="stMetricLabel"] {
    font-size: 12px !important; color: #6c757d !important;
    font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
}
[data-testid="stMetricValue"] {
    font-size: 22px !important; color: #1a1a2e !important; font-weight: 700;
}

[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
hr { border-color: #e9ecef !important; }
.stButton button { border-radius: 8px; font-weight: 600; transition: all 0.2s; }

[data-testid="stDownloadButton"] button {
    background: #1a1a2e !important; color: white !important;
    border: none !important; border-radius: 8px !important; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# 3. HELPERS HTML
# ============================================================
def metric_card(icon, label, value, bg="#f8f9fa", color="#1a1a2e", border="#e9ecef"):
    return f"""
    <div style="background:{bg}; border:1px solid {border}; border-radius:12px;
                padding:16px 20px; text-align:center; height:100%;">
        <div style="font-size:22px; margin-bottom:4px;">{icon}</div>
        <div style="font-size:11px; color:#6c757d; font-weight:700;
                    text-transform:uppercase; letter-spacing:0.6px; margin-bottom:4px;">{label}</div>
        <div style="font-size:22px; font-weight:800; color:{color};">{value}</div>
    </div>"""

def pnl_banner(titulo, monto, utilidad, icono, texto_sem):
    pos        = monto >= 0
    color_bg   = "#d1fae5" if pos else "#fee2e2"
    color_bord = "#059669" if pos else "#dc2626"
    color_txt  = "#065f46" if pos else "#7f1d1d"
    color_val  = "#059669" if pos else "#dc2626"
    return f"""
    <div style="background:{color_bg}; border:2px solid {color_bord}; border-radius:16px;
                padding:24px; text-align:center; max-width:640px; margin:0 auto 24px auto;
                box-shadow:0 4px 12px rgba(0,0,0,0.08);">
        <div style="font-size:13px; font-weight:700; color:{color_txt};
                    text-transform:uppercase; letter-spacing:1px; margin-bottom:4px;">
            GANANCIA NETA · {titulo}
        </div>
        <div style="font-size:52px; font-weight:900; color:{color_val}; line-height:1.1;">
            ${monto:,.0f}
        </div>
        <div style="font-size:15px; color:{color_txt}; margin-top:6px;">
            Utilidad Real: <strong>{utilidad:.1f}%</strong> &nbsp;
            <span style="background:{color_bord}; color:white; border-radius:20px;
                         padding:2px 10px; font-size:12px; font-weight:700;">
                {icono} {texto_sem}
            </span>
        </div>
    </div>"""

def mejor_peor_cards(mejor, peor):
    return f"""
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:16px 0;">
        <div style="background:#d1fae5; border:1px solid #059669;
                    border-radius:10px; padding:14px 18px;">
            <div style="font-size:11px; font-weight:700; color:#065f46;
                        text-transform:uppercase; letter-spacing:0.5px;">📈 Mejor día</div>
            <div style="font-size:20px; font-weight:800; color:#059669;">
                ${mejor['Ganancia_Neta']:,.0f}
            </div>
            <div style="font-size:13px; color:#065f46;">
                {mejor['Fecha'].strftime('%A %d/%m').capitalize()}
            </div>
        </div>
        <div style="background:#fee2e2; border:1px solid #dc2626;
                    border-radius:10px; padding:14px 18px;">
            <div style="font-size:11px; font-weight:700; color:#7f1d1d;
                        text-transform:uppercase; letter-spacing:0.5px;">📉 Peor día</div>
            <div style="font-size:20px; font-weight:800; color:#dc2626;">
                ${peor['Ganancia_Neta']:,.0f}
            </div>
            <div style="font-size:13px; color:#7f1d1d;">
                {peor['Fecha'].strftime('%A %d/%m').capitalize()}
            </div>
        </div>
    </div>"""

# ============================================================
# 4. CONEXIÓN A GOOGLE SHEETS
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
# 5. FUNCIONES DE DATOS
# ============================================================
ORDEN_COLS = [
    "Fecha","Venta_Efectivo","Venta_MP","Total_Ventas","Margen_Porc",
    "Costo_Mercaderia","Ganancia_Bruta","Gastos_Fijos","Horas_Trabajadas",
    "Valor_Hora","Total_Sueldos","Cant_Copias","Costo_Copia_Unit",
    "Total_Costo_Copias","Ganancia_Neta","Notas"
]

def load_data():
    sheet = get_connection()
    data  = sheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=ORDEN_COLS)
    df = pd.DataFrame(data)
    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'])
    cols_num = ['Total_Ventas','Ganancia_Neta','Total_Sueldos','Cant_Copias',
                'Costo_Copia_Unit','Gastos_Fijos','Total_Costo_Copias',
                'Valor_Hora','Margen_Porc','Costo_Mercaderia','Venta_Efectivo','Venta_MP']
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
        st.warning(f"Headers: {e}")
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
        return float(str(v).replace('$','').replace(',','')) if v else 0.0
    rows = [ORDEN_COLS]
    for _, r in pd.DataFrame(data).iterrows():
        tv = cf(r.get('Total_Ventas',0));  mp = cf(r.get('Margen_Porc',50))
        cc = cf(r.get('Cant_Copias',0));   cu = cf(r.get('Costo_Copia_Unit',0))
        gf = cf(r.get('Gastos_Fijos',0));  ts = cf(r.get('Total_Sueldos',0))
        cm = tv*(1-mp/100);  tc = cc*cu;  gb = tv-cm;  gn = gb-gf-ts
        rows.append([r.get('Fecha'),r.get('Venta_Efectivo'),r.get('Venta_MP'),
                     tv,mp,cm,gb,gf,r.get('Horas_Trabajadas'),r.get('Valor_Hora'),
                     ts,cc,cu,tc,gn,r.get('Notas','')])
    sheet.clear()
    sheet.update(rows)

def get_periodo_copia(fecha):
    if fecha.day > 21:
        return (fecha.replace(day=28)+timedelta(days=4)).strftime("%Y-%m (Cierre 21)")
    return fecha.strftime("%Y-%m (Cierre 21)")

def get_semaforo(p):
    if p >= 20: return "✓", "Excelente"
    if p >= 10: return "~", "Regular"
    return "↓", "Por debajo"

def df_to_csv(df_export):
    return df_export.to_csv(index=False, sep=';').encode('utf-8-sig')

def calcular_record(venta_efvo, venta_mp, cant_copias, costo_copia,
                    horas_staff, valor_hora, gastos_fijos, margen_input, fecha, notas):
    tv = venta_efvo + venta_mp
    cm = tv * (1 - margen_input/100)
    tc = cant_copias * costo_copia
    gb = tv - cm
    ts = horas_staff * valor_hora
    gn = gb - gastos_fijos - ts
    return {"Fecha":fecha,"Venta_Efectivo":venta_efvo,"Venta_MP":venta_mp,
            "Total_Ventas":tv,"Margen_Porc":margen_input,"Costo_Mercaderia":cm,
            "Ganancia_Bruta":gb,"Gastos_Fijos":gastos_fijos,"Horas_Trabajadas":horas_staff,
            "Valor_Hora":valor_hora,"Total_Sueldos":ts,"Cant_Copias":cant_copias,
            "Costo_Copia_Unit":costo_copia,"Total_Costo_Copias":tc,
            "Ganancia_Neta":gn,"Notas":notas}

# ============================================================
# 6. LOGIN
# ============================================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.markdown("""
        <div style="text-align:center; padding:60px 0 20px 0;">
            <div style="font-size:52px;">📚</div>
            <h1 style="color:#1a1a2e; font-weight:900; margin:8px 0;">Librería La Profe</h1>
            <p style="color:#6c757d; font-size:16px;">Sistema de gestión interna</p>
        </div>
        """, unsafe_allow_html=True)
        _, col, _ = st.columns([1, 1, 1])
        with col:
            pw = st.text_input("Contraseña", type="password",
                               label_visibility="collapsed", placeholder="Ingresá tu contraseña")
            if st.button("Ingresar →", type="primary", use_container_width=True):
                if pw == "libreria2024":
                    st.session_state.password_correct = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")
        return False
    return True

# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================
if check_password():

    with st.spinner("Cargando datos..."):
        df       = load_data()
        ultima   = datetime.now().strftime('%H:%M:%S')

    # Defaults
    def_margen = 50; def_vh = 2000.0; def_cc = 55.0; def_gf = 0.0
    if not df.empty:
        r = df.iloc[0]
        def_margen = int(r.get('Margen_Porc',50))
        def_vh     = float(r.get('Valor_Hora',2000.0))
        def_cc     = float(r.get('Costo_Copia_Unit',55.0))
        def_gf     = float(r.get('Gastos_Fijos',0.0))

    if "preview_data" not in st.session_state:
        st.session_state.preview_data = None

    # ============================================================
    # SIDEBAR
    # ============================================================
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding:16px 0 8px 0;">
            <div style="font-size:32px;">📚</div>
            <div style="font-size:17px; font-weight:800; letter-spacing:0.5px;">LIBRERÍA LA PROFE</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"🟢 Sincronizado a las {ultima}")
        st.divider()

        with st.expander("📝 Nuevo Registro", expanded=True):
            with st.form("daily_form", clear_on_submit=True):
                fecha = st.date_input("Fecha", datetime.today())

                st.markdown("**💰 Ingresos**")
                c1, c2 = st.columns(2)
                venta_efvo  = c1.number_input("Efectivo",   min_value=0.0, format="%.0f")
                venta_mp    = c2.number_input("Merc. Pago", min_value=0.0, format="%.0f")

                st.markdown("**🖨️ Copias**")
                c3, c4 = st.columns(2)
                cant_copias = c3.number_input("Cantidad",   min_value=0, step=1)
                costo_copia = c4.number_input("Costo unit.",value=def_cc, format="%.0f")

                st.markdown("**👷 Personal**")
                c5, c6 = st.columns(2)
                horas_staff  = c5.number_input("Horas",  min_value=0.0, step=0.5)
                valor_hora   = c6.number_input("$/hora",  value=def_vh,  format="%.0f")
                gastos_fijos = st.number_input("Gastos fijos", value=def_gf, format="%.0f")

                margen_input = st.slider("Margen %", 10, 90, def_margen)
                notas        = st.text_input("Notas", placeholder="Opcional...")

                cp, cs = st.columns(2)
                prev_btn  = cp.form_submit_button("👁️ Ver")
                submitted = cs.form_submit_button("☁️ Guardar", type="primary")

                if prev_btn or submitted:
                    rec = calcular_record(venta_efvo, venta_mp, cant_copias, costo_copia,
                                          horas_staff, valor_hora, gastos_fijos,
                                          margen_input, fecha, notas)
                    if prev_btn:
                        st.session_state.preview_data = rec
                    if submitted:
                        with st.spinner("Guardando..."):
                            save_new_record(rec)
                        st.toast("¡Registro guardado!", icon="✅")
                        st.session_state.preview_data = None
                        st.rerun()

        if st.session_state.preview_data:
            p    = st.session_state.preview_data
            util = (p['Ganancia_Neta']/p['Total_Ventas']*100) if p['Total_Ventas'] > 0 else 0
            ic, tx = get_semaforo(util)
            col  = "#059669" if p['Ganancia_Neta'] >= 0 else "#dc2626"
            st.markdown(f"""
            <div style="background:#1e2a3a; border:1px solid #e94560; border-radius:10px;
                        padding:14px; font-size:13px; margin-top:4px;">
                <div style="color:#aaa; font-size:11px; font-weight:700; letter-spacing:0.5px;
                            text-transform:uppercase; margin-bottom:8px;">Vista Previa</div>
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span style="color:#aaa;">Ventas</span>
                    <span style="color:#fff;font-weight:600;">${p['Total_Ventas']:,.0f}</span>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span style="color:#aaa;">Costo Merc.</span>
                    <span style="color:#fff;">${p['Costo_Mercaderia']:,.0f}</span>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span style="color:#aaa;">Sueldos</span>
                    <span style="color:#fff;">${p['Total_Sueldos']:,.0f}</span>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
                    <span style="color:#aaa;">Gastos Fijos</span>
                    <span style="color:#fff;">${p['Gastos_Fijos']:,.0f}</span>
                </div>
                <div style="border-top:1px solid #333;padding-top:8px;
                            display:flex;justify-content:space-between;align-items:center;">
                    <span style="color:#aaa;font-weight:700;">Ganancia Neta</span>
                    <span style="color:{col};font-size:18px;font-weight:900;">
                        ${p['Ganancia_Neta']:,.0f}
                    </span>
                </div>
                <div style="text-align:right;margin-top:4px;font-size:12px;color:#aaa;">
                    {util:.1f}% utilidad · {ic} {tx}
                </div>
            </div>""", unsafe_allow_html=True)

        st.divider()
        with st.expander("⚙️ Mantenimiento"):
            if st.button("🔄 Recalcular historial", use_container_width=True):
                with st.spinner("Recalculando..."):
                    recalculate_all_history()
                st.toast("¡Historial actualizado!", icon="✅")
                st.rerun()

        st.divider()
        if st.button("🔒 Cerrar sesión", use_container_width=True):
            st.session_state.password_correct = False
            st.rerun()

    # ============================================================
    # DASHBOARD PRINCIPAL
    # ============================================================
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:space-between;
                padding:0 0 8px 0; border-bottom:2px solid #e9ecef; margin-bottom:24px;">
        <div>
            <h1 style="margin:0; font-size:28px; font-weight:900; color:#1a1a2e;">
                📊 Gestión Librería La Profe
            </h1>
            <span style="font-size:13px; color:#6c757d;">🟢 Datos al {ultima}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not df.empty:
        # ── FILTROS ──
        fc, pc = st.columns([1, 3])
        with fc:
            opcion_filtro = st.radio("Período",
                ["Hoy","Última Semana","Rango Personalizado","Mes (Ciclo Copias)"],
                label_visibility="collapsed")

        df_f = df.copy()
        df_f['Fecha_Solo'] = df_f['Fecha'].dt.date
        hoy  = datetime.today().date()
        tit  = "Todo"
        es_mes = False

        with pc:
            if opcion_filtro == "Hoy":
                df_f = df_f[df_f['Fecha_Solo'] == hoy]
                tit  = f"HOY · {hoy.strftime('%d/%m/%Y')}"

            elif opcion_filtro == "Última Semana":
                ini = hoy - timedelta(days=7)
                df_f = df_f[(df_f['Fecha_Solo'] >= ini) & (df_f['Fecha_Solo'] <= hoy)]
                tit  = "ÚLTIMOS 7 DÍAS"

            elif opcion_filtro == "Rango Personalizado":
                ci, cf_ = st.columns(2)
                fi = ci.date_input("Desde:", hoy - timedelta(days=30))
                ff = cf_.date_input("Hasta:", hoy)
                if fi <= ff:
                    df_f = df_f[(df_f['Fecha_Solo'] >= fi) & (df_f['Fecha_Solo'] <= ff)]
                    tit  = f"{fi.strftime('%d/%m')} → {ff.strftime('%d/%m/%Y')}"

            elif opcion_filtro == "Mes (Ciclo Copias)":
                df['Periodo_Fiscal'] = df['Fecha'].apply(get_periodo_copia)
                meses  = sorted(df['Periodo_Fiscal'].unique(), reverse=True)
                ms     = st.selectbox("Período:", meses)
                df_f   = df[df['Periodo_Fiscal'] == ms].copy()
                tit    = ms
                es_mes = True

        st.divider()

        if df_f.empty:
            st.info(f"Sin datos para: **{tit}**")
        else:
            # ── KPIs ──
            pnl   = df_f['Ganancia_Neta'].sum()
            vtas  = df_f['Total_Ventas'].sum()
            porc  = (pnl/vtas*100) if vtas > 0 else 0
            dias  = df_f['Fecha'].nunique()
            prom  = vtas/dias if dias > 0 else 0
            ic, tx = get_semaforo(porc)

            # Delta semana anterior
            va = pa = None
            if opcion_filtro == "Última Semana":
                dfa = df.copy()
                dfa['Fecha_Solo'] = dfa['Fecha'].dt.date
                dfa = dfa[(dfa['Fecha_Solo'] >= hoy-timedelta(days=14)) &
                           (dfa['Fecha_Solo'] <= hoy-timedelta(days=8))]
                if not dfa.empty:
                    va = dfa['Total_Ventas'].sum()
                    pa = dfa['Ganancia_Neta'].sum()

            # Banner
            st.markdown(pnl_banner(tit, pnl, porc, ic, tx), unsafe_allow_html=True)

            # Cards
            c1,c2,c3,c4,c5 = st.columns(5)
            c1.markdown(metric_card("💰","Ventas Totales", f"${vtas:,.0f}","#f0fdf4","#065f46","#bbf7d0"), unsafe_allow_html=True)
            c2.markdown(metric_card("📈","Ganancia Neta",  f"${pnl:,.0f}", "#f0fdf4","#065f46","#bbf7d0"), unsafe_allow_html=True)
            c3.markdown(metric_card("📅","Prom. / Día",    f"${prom:,.0f}","#eff6ff","#1e40af","#bfdbfe"), unsafe_allow_html=True)
            c4.markdown(metric_card("👷","Sueldos",        f"${df_f['Total_Sueldos'].sum():,.0f}","#fefce8","#854d0e","#fef08a"), unsafe_allow_html=True)
            c5.markdown(metric_card("🏢","Gastos Fijos",   f"${df_f['Gastos_Fijos'].sum():,.0f}", "#fef2f2","#7f1d1d","#fecaca"), unsafe_allow_html=True)

            if va or pa:
                dv = f"${vtas-va:+,.0f} vs sem. ant." if va else ""
                dp = f"${pnl-pa:+,.0f} vs sem. ant."  if pa else ""
                st.caption(f"📊 {dv}   |   {dp}")

            # Mejor / Peor
            if len(df_f) > 1:
                st.markdown(
                    mejor_peor_cards(
                        df_f.loc[df_f['Ganancia_Neta'].idxmax()],
                        df_f.loc[df_f['Ganancia_Neta'].idxmin()]
                    ), unsafe_allow_html=True)

            # Alerta días sin registrar
            if opcion_filtro in ("Última Semana","Rango Personalizado","Mes (Ciclo Copias)"):
                con   = set(df_f['Fecha'].dt.date)
                fmin_ = df_f['Fecha'].min().date()
                fmax_ = df_f['Fecha'].max().date()
                falt  = sorted(
                    fmin_ + timedelta(days=i)
                    for i in range((fmax_-fmin_).days+1)
                    if (fmin_+timedelta(days=i)) not in con
                    and (fmin_+timedelta(days=i)).weekday() < 6
                )
                if falt:
                    st.warning(f"⚠️ Días sin registrar: **{', '.join(d.strftime('%d/%m') for d in falt)}**")

            # ── GRÁFICOS ──
            if len(df_f) > 1:
                st.divider()
                st.markdown("### 📈 Evolución")
                tg, tv_, tm = st.tabs(["Ganancia Neta","Ventas por Día","Efectivo vs Mercado Pago"])

                dc = df_f.sort_values('Fecha')[['Fecha','Ganancia_Neta','Total_Ventas']].copy().set_index('Fecha')

                with tg:
                    st.line_chart(dc[['Ganancia_Neta']], color="#059669")
                with tv_:
                    st.bar_chart(dc[['Total_Ventas']], color="#1e40af")
                with tm:
                    tef = df_f['Venta_Efectivo'].sum()
                    tmp = df_f['Venta_MP'].sum()
                    if tef + tmp > 0:
                        pef = tef/(tef+tmp)*100; pmp = tmp/(tef+tmp)*100
                        ca,cb,cc = st.columns([1,1,2])
                        ca.markdown(metric_card("💵","Efectivo",    f"${tef:,.0f}\n{pef:.1f}%","#f0fdf4","#065f46","#bbf7d0"), unsafe_allow_html=True)
                        cb.markdown(metric_card("📱","Mercado Pago",f"${tmp:,.0f}\n{pmp:.1f}%","#eff6ff","#1e40af","#bfdbfe"), unsafe_allow_html=True)
                        df_mp = pd.DataFrame({"Efectivo":[tef],"Mercado Pago":[tmp]})
                        cc.bar_chart(df_mp, color=["#059669","#1e40af"])
                    else:
                        st.info("Sin datos de medios de pago.")

            # ── COPIAS ──
            if es_mes:
                st.divider()
                st.markdown("### 🖨️ Análisis de Copias")
                tot = df_f['Cant_Copias'].sum()
                prog = min(tot/COPIAS_META_MENSUAL, 1.0)

                ca,cb,cc = st.columns(3)
                ca.markdown(metric_card("🖨️","Acumulado",f"{tot:,.0f}","#f8f9fa","#1a1a2e","#dee2e6"), unsafe_allow_html=True)
                cb.markdown(metric_card("🎯","Meta",f"{COPIAS_META_MENSUAL:,}","#f8f9fa","#1a1a2e","#dee2e6"), unsafe_allow_html=True)
                if tot >= COPIAS_META_MENSUAL:
                    cc.markdown(metric_card("✅","Estado","Meta superada","#d1fae5","#065f46","#6ee7b7"), unsafe_allow_html=True)
                else:
                    cc.markdown(metric_card("⚡","Faltan",f"{COPIAS_META_MENSUAL-tot:,.0f}","#fee2e2","#7f1d1d","#fca5a5"), unsafe_allow_html=True)

                st.progress(prog, text=f"{tot:,.0f} / {COPIAS_META_MENSUAL:,} copias  ·  {prog*100:.1f}%")

                st.markdown("##### 📅 Resumen por semana")
                ds = df_f.copy()
                ds['Semana'] = ds['Fecha'].dt.to_period('W').apply(
                    lambda r: f"{r.start_time.strftime('%d/%m')} – {r.end_time.strftime('%d/%m')}")
                rs = (ds.groupby('Semana', sort=False)
                      .agg(Ventas=('Total_Ventas','sum'), Ganancia=('Ganancia_Neta','sum'),
                           Copias=('Cant_Copias','sum'), Días=('Fecha','nunique'))
                      .reset_index())
                rs['Ventas']   = rs['Ventas'].apply(lambda x: f"${x:,.0f}")
                rs['Ganancia'] = rs['Ganancia'].apply(lambda x: f"${x:,.0f}")
                rs['Copias']   = rs['Copias'].apply(lambda x: f"{x:,.0f}")
                st.dataframe(rs, use_container_width=True, hide_index=True)

            # ── TABLA ──
            st.divider()
            tc_col, ec_col = st.columns([3,1])
            tc_col.markdown("### 📋 Registros del período")
            with ec_col:
                cols_e = ['Fecha','Total_Ventas','Ganancia_Neta','Costo_Mercaderia',
                          'Total_Sueldos','Gastos_Fijos','Cant_Copias','Notas']
                dfe = df_f[[c for c in cols_e if c in df_f.columns]].copy()
                if 'Fecha' in dfe.columns:
                    dfe['Fecha'] = dfe['Fecha'].dt.strftime('%d/%m/%Y')
                st.download_button("📥 Exportar CSV", data=df_to_csv(dfe),
                                   file_name=f"libreria_{tit.replace(' ','_')}.csv",
                                   mime="text/csv", use_container_width=True)

            df_t = df_f[['Fecha','Total_Ventas','Costo_Mercaderia','Total_Costo_Copias',
                          'Total_Sueldos','Gastos_Fijos','Ganancia_Neta','Notas']].copy()
            df_t = df_t.rename(columns={
                'Total_Ventas':'Ventas','Costo_Mercaderia':'Costo Rep.',
                'Total_Costo_Copias':'Costo Copias','Total_Sueldos':'Sueldos',
                'Gastos_Fijos':'Gastos Fijos','Ganancia_Neta':'Ganancia Neta','Notas':'Notas'})

            st.dataframe(
                df_t, use_container_width=True, hide_index=True,
                column_config={
                    "Fecha":         st.column_config.DateColumn("📅 Fecha",       format="DD/MM/YYYY"),
                    "Ventas":        st.column_config.NumberColumn("💰 Ventas",     format="$%.0f"),
                    "Costo Rep.":    st.column_config.NumberColumn("📦 Costo Rep.", format="$%.0f"),
                    "Costo Copias":  st.column_config.NumberColumn("🖨️ Copias",    format="$%.0f"),
                    "Sueldos":       st.column_config.NumberColumn("👷 Sueldos",    format="$%.0f"),
                    "Gastos Fijos":  st.column_config.NumberColumn("🏢 G. Fijos",  format="$%.0f"),
                    "Ganancia Neta": st.column_config.NumberColumn("📈 Gan. Neta", format="$%.0f"),
                    "Notas":         st.column_config.TextColumn("📝 Notas"),
                })

            # ── EDITAR / BORRAR ──
            st.markdown("##### ✏️ Editar o eliminar un registro")
            fechas_disp = df_f['Fecha'].dt.strftime('%d/%m/%Y').tolist()
            sel = st.selectbox("Seleccioná la fecha:", fechas_disp, label_visibility="collapsed")

            if sel:
                idx = df_f[df_f['Fecha'].dt.strftime('%d/%m/%Y') == sel].index[0]
                row = df_f.loc[idx]
                te, td = st.tabs(["✏️ Editar","🗑️ Eliminar"])

                with te:
                    with st.form("edit_form"):
                        e1,e2 = st.columns(2)
                        eef = e1.number_input("Efectivo ($)",     value=float(row.get('Venta_Efectivo',0)),   format="%.0f")
                        emp = e2.number_input("Mercado Pago ($)", value=float(row.get('Venta_MP',0)),         format="%.0f")
                        e3,e4 = st.columns(2)
                        ecc = e3.number_input("Copias",           value=int(row.get('Cant_Copias',0)),        step=1)
                        ecu = e4.number_input("Costo copia",      value=float(row.get('Costo_Copia_Unit',55)),format="%.0f")
                        e5,e6 = st.columns(2)
                        ehs = e5.number_input("Horas staff",      value=float(row.get('Horas_Trabajadas',0)), step=0.5)
                        evh = e6.number_input("Valor hora",       value=float(row.get('Valor_Hora',2000)),    format="%.0f")
                        egf = st.number_input("Gastos fijos",     value=float(row.get('Gastos_Fijos',0)),     format="%.0f")
                        emg = st.slider("Margen %", 10, 90,       int(row.get('Margen_Porc',50)))
                        eno = st.text_input("Notas",              value=str(row.get('Notas','')))
                        if st.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True):
                            upd = calcular_record(eef,emp,ecc,ecu,ehs,evh,egf,emg,row['Fecha'],eno)
                            with st.spinner("Guardando..."):
                                update_record_by_date(row['Fecha'], upd)
                            st.toast("¡Registro actualizado!", icon="✅")
                            st.rerun()

                with td:
                    st.warning(f"Vas a eliminar el registro del **{sel}**. Esta acción no se puede deshacer.")
                    if st.button("🗑️ Confirmar eliminación", type="primary", use_container_width=True):
                        with st.spinner("Eliminando..."):
                            delete_record_by_date(row['Fecha'])
                        st.toast("Registro eliminado.", icon="🗑️")
                        st.rerun()

    else:
        st.markdown("""
        <div style="text-align:center; padding:80px 0; color:#6c757d;">
            <div style="font-size:48px; margin-bottom:12px;">📭</div>
            <h3>La base de datos está vacía</h3>
            <p>Cargá el primer registro desde el panel izquierdo.</p>
        </div>
        """, unsafe_allow_html=True)
