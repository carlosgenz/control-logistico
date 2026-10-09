import streamlit as st
from datetime import datetime
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# Configuración de la App en modo oscuro nativo de Streamlit
st.set_page_config(page_title="Control Logístico Maestro", layout="wide")

# Forzar el refresco de pantalla dinámico en espejo cada 3 segundos
st_autorefresh(interval=3000, key="datarefresh")

# Obtener la URL desde los Secrets de Streamlit de forma segura
try:
    URL_DE_MI_GOOGLE_SHEETS = st.secrets["connections"]["gsheets"]["spreadsheet"]
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("🚨 Falta configurar la URL en la pestaña de 'Secrets' de Streamlit Cloud.")
    st.stop()

def cargar_datos_web():
    try:
        df = conn.read(spreadsheet=URL_DE_MI_GOOGLE_SHEETS, ttl="0s")
        if df.empty or df.columns is None:
            return []
        # Limpiar filas y columnas completamente vacías de Google Sheets
        df = df.dropna(how='all')
        return df.to_dict(orient="records")
    except:
        return []

def guardar_datos_web(lista_registros):
    try:
        df_nuevo = pd.DataFrame(lista_registros)
        conn.update(spreadsheet=URL_DE_MI_GOOGLE_SHEETS, data=df_nuevo)
    except Exception as e:
        st.error(f"Error al guardar en la nube: {e}")

st.session_state.registros = cargar_datos_web()

def sincronizar_y_recargar():
    guardar_datos_web(st.session_state.registros)
    st.rerun()

def obtener_hora():
    return datetime.now().strftime("%H:%M:%S")

def calcular_minutos(hora_inicio, hora_fin):
    try:
        if not hora_inicio or not hora_fin: return 0
        fmt = "%H:%M:%S"
        td = datetime.strptime(hora_fin, fmt) - datetime.strptime(hora_inicio, fmt)
        return round(td.total_seconds() / 60, 2)
    except: return 0

st.title("📦 Sistema de Control Logístico Maestro (Espejo en Tiempo Real)")

# --- DISEÑO DE LOS 5 APARTADOS (PESTAÑAS) ---
tab_carga, tab_pc1, tab_pc2, tab_pc3, tab_pc4 = st.tabs([
    "⚡ CARGA MASIVA", "⏳ PC 1: SEPARACIÓN", "🚀 PC 2: CONTROL SALIDA", "✏️ PC 3: EDICIÓN / ENTREGA", "🏆 PC 4: TOP OPERARIOS"
])

# ==================== APARTADO 1: CARGA MASIVA ====================
with tab_carga:
    st.subheader("Carga Masiva de Datos desde Excel")
    fecha_seleccionada = st.date_input("Selecciona la fecha para este lote de notas:", value=datetime.now())
    fecha_formateada = fecha_seleccionada.strftime("%d-%m-%Y")
    
    col1, col2 = st.columns(2)
    with col1:
        txt_notas = st.text_area("Pega la columna de Notas de Excel (una por línea):", height=150, key="carga_notas")
    with col2:
        txt_cants = st.text_area("Pega la columna de Cantidades / Ítems de Excel:", height=150, key="carga_cants")
        
    if st.button("⚡ Inyectar Datos a la Nube", type="primary"):
        if txt_notas.strip():
            lineas_n = txt_notas.strip().split("\n")
            lineas_c = txt_cants.strip().split("\n") if txt_cants.strip() else []
            
            # Buscar el ID más alto de forma segura
            ids_validos = [int(r['id']) for r in st.session_state.registros if 'id' in r and str(r['id']).isdigit()]
            next_id = max(ids_validos) + 1 if ids_validos else 1
            
            for idx, nota in enumerate(lineas_n):
                if nota.strip():
                    cant_real = lineas_c[idx].strip() if idx < len(lineas_c) and lineas_c[idx].strip() != "" else "0"
                    st.session_state.registros.append({
                        "id": int(next_id), "fecha": str(fecha_formateada), "nota": str(nota.strip()), "cantidad": str(cant_real),
                        "bultos": "", "estado": "Pendiente", "separador": "", "ini_sep": "", "fin_sep": "",
                        "salida_user": "", "ini_salida": "", "fin_salida": "", "entrega": "", "destino": ""
                    })
                    next_id += 1
            sincronizar_y_recargar()
            st.success("✅ ¡Datos subidos a la nube con éxito!")

# ==================== APARTADO 2: PC 1 (SEPARACIÓN) ====================
with tab_pc1:
    st.subheader("Puesto 1: Gestión y Tiempos de Separación")
    pendientes = [r for r in st.session_state.registros if str(r.get('estado')) in ["Pendiente", "En Proceso"]]
    
    if not pendientes:
        st.info("No hay notas pendientes de separación.")
    else:
        for r in pendientes:
            with st.container(border=True):
                col_i, col_n, col_v, col_e, col_inp, col_btn = st.columns([1, 4, 1.5, 2, 2, 2])
                col_i.markdown(f"**#{r['id']}**")
                col_n.text(r['nota'])
                col_v.markdown(f"Items: **{r.get('cantidad', '0')}**")
                col_e.warning(f"Estado: {r['estado']}")
                
                if r['estado'] == "Pendiente":
                    nombre_sep = col_inp.text_input("Separador:", key=f"sep_in_{r['id']}")
                    if col_btn.button("▶️ Separar", key=f"btn_sep_{r['id']}", type="primary"):
                        if nombre_sep.strip():
                            r['separador'] = nombre_sep.strip()
                            r['estado'] = "En Proceso"
                            r['ini_sep'] = obtener_hora()
                            sincronizar_y_recargar()
                elif r['estado'] == "En Proceso":
                    col_inp.markdown(f"Asignado a: **{r['separador']}**")
                    if col_btn.button("🏁 Finalizar Sep.", key=f"btn_fsep_{r['id']}", type="secondary"):
                        r['estado'] = "Separado"
                        r['fin_sep'] = obtener_hora()
                        sincronizar_y_recargar()

# ==================== APARTADO 3: PC 2 (CONTROL SALIDA) ====================
with tab_pc2:
    st.subheader("Puesto 2: Gestión y Despacho de Salida")
    para_salida = [r for r in st.session_state.registros if str(r.get('estado')) in ["Separado", "En Salida"]]
    
    if not para_salida:
        st.info("No hay órdenes listas para proceso de salida.")
    else:
        for r in para_salida:
            with st.container(border=True):
                col_i, col_n, col_v, col_s, col_inp, col_btn = st.columns([1, 3, 1.5, 2, 2, 2])
                col_i.markdown(f"**#{r['id']}**")
                col_n.text(r['nota'])
                col_v.markdown(f"Items: **{r.get('cantidad', '0')}**")
                col_s.markdown(f"Separó: **{r['separador']}**")
                
                if r['estado'] == "Separado":
                    nombre_sal = col_inp.text_input("Encargado Salida:", key=f"sal_in_{r['id']}")
                    if col_btn.button("🚀 Iniciar Salida", key=f"btn_sal_{r['id']}", type="primary"):
                        if nombre_sal.strip():
                            r['salida_user'] = nombre_sal.strip()
                            r['estado'] = "En Salida"
                            r['ini_salida'] = obtener_hora()
                            sincronizar_y_recargar()
                elif r['estado'] == "En Salida":
                    col_inp.markdown(f"Despacha: **{r['salida_user']}**")
                    if col_btn.button("🛑 Fin Salida", key=f"btn_fsal_{r['id']}", type="secondary"):
                        hora = obtener_hora()
                        r['estado'] = "Finalizado"
                        r['fin_salida'] = hora
                        r['entrega'] = hora
                        sincronizar_y_recargar()

# ==================== APARTADO 4: PC 3 (EDICIÓN / ENTREGA) ====================
with tab_pc3:
    st.subheader("Puesto 3: Registro de Destino, Volumen (Cajas) y Cierre de Entrega")
    busqueda_nota = st.text_input("🔍 Buscar por número de Nota o ID:", key="buscar_nota_input").strip()
    
    registros_filtrados = st.session_state.registros
    if busqueda_nota:
        registros_filtrados = [r for r in st.session_state.registros if busqueda_nota in str(r['nota']) or busqueda_nota in str(r['id'])]
        
    if not registros_filtrados:
        st.info("No se encontraron registros.")
    else:
        df_temporal = pd.DataFrame(registros_filtrados)
        for col in ['fecha', 'destino']:
            if col not in df_temporal.columns: df_temporal[col] = ""
        df_temporal['destino'] = df_temporal['destino'].fillna("").astype(str).str.strip()
        df_temporal['fecha'] = df_temporal['fecha'].fillna("")
        df_temporal = df_temporal.sort_values(by=['fecha', 'destino'], ascending=[False, True])
        registros_ordenados = df_temporal.to_dict('records')

        for r in registros_ordenados:
            with st.container(border=True):
                col_i, col_f, col_n, col_dest, col_cant, col_vol, col_op, col_tim, col_ent, col_del = st.columns(
                    [0.5, 1.1, 1.8, 1.4, 0.9, 1.1, 1.6, 2.8, 2.2, 0.5]
                )
                col_i.markdown(f"**#{r['id']}**")
                col_f.markdown(f"📅 {r.get('fecha', '--')}")
                col_n.text(r['nota'])
                
                nuevo_destino = col_dest.text_input("Destino:", value=str(r.get('destino', '')), key=f"dest_ed_{r['id']}", placeholder="Ej. 21")
                if nuevo_destino != str(r.get('destino', '')):
                    r['destino'] = nuevo_destino.strip()
                    sincronizar_y_recargar()
                
                col_cant.markdown(f"Ítems:<br>**{r.get('cantidad', '0')}**", unsafe_allow_html=True)
                
                nuevo_bulto = col_vol.text_input("Vol (Cajas):", value=str(r.get('bultos', '')), key=f"bultos_ed_{r['id']}", placeholder="0")
                if nuevo_bulto != str(r.get('bultos', '')):
                    r['bultos'] = nuevo_bulto.strip()
                    guardar_datos_web(st.session_state.registros)
                    
                col_op.markdown(f"Sep: **{r.get('separador', '--')}**<br>Sal: **{r.get('salida_user', '--')}**", unsafe_allow_html=True)
