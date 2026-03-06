import sqlite3
import datetime
import streamlit as st
import pandas as pd
from pathlib import Path
import time
import io
import re

# =====================================================
# CONFIGURACIÓN INICIAL
# =====================================================

st.set_page_config(
    page_title="Gestión del PEMA",
    page_icon="ada-icono.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = DATA_DIR / "inventory_shared.db"

LOGO_FILE   = BASE_DIR / "ada-logo.png"
HEADER_FILE = BASE_DIR / "ADA-vc-color.jpg"

# ── Tipos de equipos disponibles en el inventario ──────────────────────
TIPOS_EQUIPO = [
    "Ordenador sobremesa",
    "Portátil",
    "Monitor",
    "Impresora",
    "Proyector",
    "Tablet",
    "Teléfono",
    "Servidor",
    "Switch/Router",
    "Otro",
]

# ── Grupos visuales PEMA (idéntico al original) ────────────────────────
GROUPS_CONFIG = {
    "Discos duros":  {"cat": "Almacenamiento",         "img": "hdd.png"},
    "Memorias":      {"cat": "Almacenamiento",         "img": "memory.png"},
    "Adaptadores":   {"cat": "Conectores/Adaptadores", "img": "adapter.png"},
    "Cables":        {"cat": "Cables",                 "img": "cable.png"},
    "Periféricos":   {"cat": "Periféricos",            "img": "peripheral.png"},
    "Switch":        {"cat": "Redes",                  "img": "switch.png"},
    "Energía":       {"cat": "Energía",                "img": "power.png"},
    "Otros":         {"cat": "Otros",                  "img": "other.png"},
}

# =====================================================
# CSS
# =====================================================

def cargar_estilos_css():
    st.markdown("""
    <style>
    :root {
        --verde-junta: #0b6e3c;
        --verde-hover: #158f4a;
        --verde-claro: #e7f6ed;
        --blanco: #ffffff;
        --gris-claro: #f4f6f9;
        --texto-oscuro: #1f2937;
    }
    .stApp { background-color: var(--blanco); color: var(--texto-oscuro); }
    header[data-testid="stHeader"] {
        background-color: var(--blanco);
        border-bottom: 4px solid var(--verde-junta);
        padding: 0.5rem;
    }
    header::after { display: none !important; }
    header img { max-height: 60px !important; object-fit: contain; }

    section[data-testid="stSidebar"] { background-color: var(--verde-junta); padding-top: 1rem; }
    section[data-testid="stSidebar"] * { color: var(--blanco) !important; font-size: 15px; }

    div[data-testid^="stKey-nav_"] button {
        all: unset;
        width: 90% !important;
        margin: 0 auto !important;
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 12px 0px;
        margin-bottom: 8px !important;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 500;
        color: var(--blanco) !important;
        background-color: rgba(255,255,255,0.1);
        border: 1px solid rgba(255,255,255,0.2);
        transition: background 0.2s;
        box-sizing: border-box;
    }
    div[data-testid^="stKey-nav_"] button:hover {
        background-color: var(--verde-hover);
        border-color: var(--blanco);
    }

    .main { padding: 2rem; }
    .stButton > button {
        background-color: var(--verde-junta); color: var(--blanco);
        border-radius: 6px; border: none; padding: 0.5rem 1rem; font-weight: 600;
    }
    .stButton > button:hover { background-color: var(--verde-hover); }
    input, textarea { border-radius: 6px !important; }
    footer { visibility: hidden; }

    [data-testid="stVerticalBlockBorderWrapper"] {
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        background-color: #f9f9f9;
    }

    /* Tarjetas métricas inventario */
    .inv-metric {
        background: var(--verde-claro);
        border: 1px solid #b2dfc5;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        text-align: center;
    }
    .inv-metric .val { font-size: 2rem; font-weight: 700; color: var(--verde-junta); }
    .inv-metric .lbl { font-size: 0.85rem; color: #444; margin-top: 0.2rem; }
    </style>
    """, unsafe_allow_html=True)

# =====================================================
# BASE DE DATOS
# =====================================================

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    tables_sql = [
        # Tabla original PEMA
        """CREATE TABLE IF NOT EXISTS system_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'tecnico',
            last_password_change TEXT,
            force_reset INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS articles (
            code TEXT PRIMARY KEY,
            name TEXT, type TEXT,
            initial_stock INTEGER DEFAULT 0,
            entries INTEGER DEFAULT 0,
            exits INTEGER DEFAULT 0,
            current_stock INTEGER DEFAULT 0,
            created_by TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS clients (
            code TEXT PRIMARY KEY,
            fiscal_name TEXT, name TEXT, surname TEXT, nif TEXT,
            phone TEXT, email TEXT, address TEXT, city TEXT,
            province TEXT, zip_code TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS providers (
            code TEXT PRIMARY KEY,
            fiscal_name TEXT, name TEXT, surname TEXT, nif TEXT,
            phone TEXT, email TEXT, address TEXT, city TEXT,
            province TEXT, zip_code TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS stock_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_code TEXT UNIQUE, date TEXT,
            provider_code TEXT, provider_name TEXT,
            article_code TEXT, article_name TEXT,
            quantity INTEGER, last_modified_by TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS stock_exits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exit_code TEXT UNIQUE, date TEXT,
            client_code TEXT, client_name TEXT,
            article_code TEXT, article_name TEXT,
            quantity INTEGER, price REAL,
            delivered_to TEXT, last_modified_by TEXT
        )""",
        # ── NUEVA: inventario del instituto ──────────────────────────────
        """CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT,
            tipo TEXT,
            marca TEXT,
            modelo TEXT,
            numero_serie TEXT,
            ubicacion TEXT,
            aula TEXT,
            estado TEXT DEFAULT 'Operativo',
            fecha_alta TEXT,
            observaciones TEXT
        )""",
    ]
    for sql in tables_sql:
        cursor.execute(sql)
    conn.commit()
    update_existing_article_types(conn)
    conn.close()

# =====================================================
# HELPERS PEMA (idénticos al original)
# =====================================================

def get_exact_group_and_category(code_input, name_input=""):
    s_code = str(code_input).strip()
    s_name = str(name_input).strip().lower()

    if "altavoz" in s_name or "altavoces" in s_name: return "Periféricos", "Periféricos"
    if s_code.lower() in ['nan', '', 'none']:          return "Cables", "Cables"
    if s_code == 'S/R-1':                              return "Adaptadores", "Conectores/Adaptadores"
    if s_code in ['200', '2.1']:                       return "Periféricos", "Periféricos"

    try:
        parts = s_code.split('.')
        if len(parts) == 2 and parts[0] == '1':
            minor = int(parts[1])
            if   1  <= minor <= 12:  return "Discos duros",  "Almacenamiento"
            if  13  <= minor <= 27:  return "Adaptadores",   "Conectores/Adaptadores"
            if  28  <= minor <= 40:  return "Cables",        "Cables"
            if  41  <= minor <= 44:  return "Energía",       "Energía"
            if  45  <= minor <= 48:  return "Cables",        "Cables"
            if  49  <= minor <= 50:  return "Switch",        "Redes"
            if  51  <= minor <= 57:  return "Energía",       "Energía"
            if  58  <= minor <= 66:  return "Periféricos",   "Periféricos"
            if  67  <= minor <= 74:  return "Otros",         "Otros"
            if  75  <= minor <= 80:  return "Periféricos",   "Periféricos"
            if  81  <= minor <= 82:  return "Discos duros",  "Almacenamiento"
            if  83  <= minor <= 100: return "Periféricos",   "Periféricos"
            if 101  <= minor <= 103: return "Memorias",      "Almacenamiento"
            if 104  <= minor <= 106: return "Discos duros",  "Almacenamiento"
            if 107  <= minor <= 108: return "Otros",         "Otros"
            if 109  <= minor <= 111: return "Energía",       "Energía"
            if 112  <= minor <= 114: return "Cables",        "Cables"
            if 115  <= minor <= 117: return "Otros",         "Otros"
    except: pass

    if 'adaptador' in s_name or 'conector' in s_name:                             return "Adaptadores",  "Conectores/Adaptadores"
    if 'switch' in s_name or 'router' in s_name or 'hub' in s_name:               return "Switch",       "Redes"
    if any(x in s_name for x in ['ratón','teclado','monitor','webcam','cámara']):  return "Periféricos",  "Periféricos"
    if any(x in s_name for x in ['memoria','pendrive','usb','sd']):               return "Memorias",     "Almacenamiento"
    if any(x in s_name for x in ['disco','hdd','ssd']):                           return "Discos duros", "Almacenamiento"
    if 'cable' in s_name or 'latiguillo' in s_name:                               return "Cables",       "Cables"
    if any(x in s_name for x in ['pila','batería','cargador','regleta','alimentación']): return "Energía", "Energía"
    return "Otros", "Otros"

def classify_article_category_only(code):
    _, cat = get_exact_group_and_category(code, "")
    return cat

def determine_visual_group(row):
    group, _ = get_exact_group_and_category(row['code'], row['name'])
    return group

def update_existing_article_types(conn):
    try:
        cursor = conn.cursor()
        articles = cursor.execute("SELECT code, name, type FROM articles").fetchall()
        for art in articles:
            _, correct_cat = get_exact_group_and_category(art['code'], art['name'])
            if art['type'] != correct_cat:
                cursor.execute("UPDATE articles SET type = ? WHERE code = ?", (correct_cat, art['code']))
        conn.commit()
    except Exception as e:
        print(f"Error updating types: {e}")

def sync_stock_calculations(conn):
    try:
        conn.execute("UPDATE articles SET initial_stock = 0 WHERE initial_stock IS NULL")
        conn.execute("UPDATE articles SET entries = 0 WHERE entries IS NULL")
        conn.execute("UPDATE articles SET exits = 0 WHERE exits IS NULL")
        conn.execute("""UPDATE articles SET entries = (
            SELECT COALESCE(SUM(quantity), 0) FROM stock_entries
            WHERE stock_entries.article_code = articles.code)""")
        conn.execute("""UPDATE articles SET exits = (
            SELECT COALESCE(SUM(quantity), 0) FROM stock_exits
            WHERE stock_exits.article_code = articles.code)""")
        conn.execute("UPDATE articles SET current_stock = initial_stock + entries - exits")
        conn.commit()
    except Exception as e:
        print(f"Sync error: {e}")

def safe_str_code(val):
    if pd.isna(val) or val is None: return ""
    s = str(val).strip()
    if s in ("nan", ""): return ""
    if s.endswith(".0"): return s[:-2]
    return s

def natural_sort_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', str(s))]

def sort_df_naturally(df, col_name):
    try:
        df['_sk'] = df[col_name].apply(natural_sort_key)
        df = df.sort_values('_sk').drop('_sk', axis=1)
        return df
    except:
        return df

def normalize_header(col_name):
    return (str(col_name).strip().lower()
            .replace("á","a").replace("é","e").replace("í","i")
            .replace("ó","o").replace("ú","u").replace("ñ","n"))

def format_date_eu(val):
    if not val: return ""
    try:
        if isinstance(val, str):
            ts = pd.to_datetime(val, errors='coerce', dayfirst=True)
            if pd.notna(ts): return ts.strftime("%d-%m-%Y")
            return val
        if isinstance(val, (datetime.date, datetime.datetime, pd.Timestamp)):
            return val.strftime("%d-%m-%Y")
        return str(val)
    except:
        return str(val)

def to_excel_download(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

def format_mixed(code, name):
    if pd.isna(code): return ""
    s = str(code).strip()
    if s in ("", "0", "0.0") or s.lower() == "nan": return ""
    try:
        return f"{int(float(s))} / {name}" if float(s).is_integer() else f"{s} / {name}"
    except:
        return f"{s} / {name}"

def clear_cache():
    st.cache_data.clear()

def import_master_excel(uploaded_file, current_user):
    conn = get_db_connection()
    results = {"Existencias": 0, "Sedes": 0, "Proveedores": 0, "Entradas": 0, "Salidas": 0}
    try:
        conn.execute("DELETE FROM articles");       conn.execute("DELETE FROM clients")
        conn.execute("DELETE FROM providers");      conn.execute("DELETE FROM stock_entries")
        conn.execute("DELETE FROM stock_exits");    conn.commit()
        xls = pd.read_excel(uploaded_file, sheet_name=None)

        sn = next((s for s in xls if "existencia" in s.lower()), None)
        if sn:
            df = xls[sn]; df.columns = [normalize_header(c) for c in df.columns]
            for _, row in df.iterrows():
                try:
                    ini = float(row.get('existencias iniciales', 0))
                    ent = float(row.get('entradas', 0))
                    sal = float(row.get('salidas', 0))
                    code = safe_str_code(row.get('codigo', ''))
                    if code:
                        conn.execute(
                            "INSERT INTO articles (code,name,type,initial_stock,entries,exits,current_stock) VALUES (?,?,?,?,?,?,?)",
                            (code, row.get('nombre del articulo'), classify_article_category_only(code),
                             ini, ent, sal, ini+ent-sal))
                        results["Existencias"] += 1
                except: pass

        for sheet_key, table, cols in [
            ("cliente",    "clients",   ("codigo","nombre fiscal","nombre","apellidos","nif/cif","telefono","e-mail","direccion","poblacion","provincia","codigo postal")),
            ("proveedor",  "providers", ("codigo","nombre fiscal","nombre","apellidos","nif/cif","telefono","e-mail","direccion","poblacion","provincia","codigo postal")),
        ]:
            sn = next((s for s in xls if sheet_key in s.lower()), None)
            if sn:
                df = xls[sn]; df.columns = [normalize_header(c) for c in df.columns]
                for _, row in df.iterrows():
                    code = safe_str_code(row.get('codigo', ''))
                    if code:
                        try:
                            conn.execute(
                                f"INSERT INTO {table} (code,fiscal_name,name,surname,nif,phone,email,address,city,province,zip_code) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                (code, row.get('nombre fiscal'), row.get('nombre'), row.get('apellidos'),
                                 row.get('nif/cif'), row.get('telefono'), row.get('e-mail'),
                                 row.get('direccion'), row.get('poblacion'), row.get('provincia'),
                                 row.get('codigo postal')))
                            results["Sedes" if table=="clients" else "Proveedores"] += 1
                        except: pass

        sn = next((s for s in xls if "entrada" in s.lower()), None)
        if sn:
            df = xls[sn]; df.columns = [normalize_header(c) for c in df.columns]
            for _, row in df.iterrows():
                code = safe_str_code(row.get('codigo', ''))
                if code:
                    try:
                        conn.execute(
                            "INSERT INTO stock_entries (entry_code,date,provider_code,provider_name,article_code,article_name,quantity,last_modified_by) VALUES (?,?,?,?,?,?,?,?)",
                            (code, format_date_eu(row.get('fecha')),
                             safe_str_code(row.get('proveedor (codigo)','')), row.get('proveedor (nombre)'),
                             safe_str_code(row.get('articulo (codigo)','')),  row.get('articulo (nombre)'),
                             row.get('cantidad',0), current_user))
                        results["Entradas"] += 1
                    except: pass

        sn = next((s for s in xls if "salida" in s.lower()), None)
        if sn:
            df = xls[sn]; df.columns = [normalize_header(c) for c in df.columns]
            for _, row in df.iterrows():
                code = safe_str_code(row.get('codigo',''))
                if code:
                    try:
                        conn.execute(
                            "INSERT INTO stock_exits (exit_code,date,client_code,client_name,article_code,article_name,quantity,price,delivered_to,last_modified_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (code, format_date_eu(row.get('fecha')),
                             safe_str_code(row.get('cliente (codigo)','')), row.get('cliente (nombre)'),
                             safe_str_code(row.get('articulo (codigo)','')), row.get('articulo (nombre)'),
                             row.get('cantidad',0), row.get('precio'), row.get('entregado a'), current_user))
                        results["Salidas"] += 1
                    except: pass

        conn.commit()
        return True, results
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

# =====================================================
# HELPERS INVENTARIO INSTITUTO
# =====================================================

def cargar_inventario(conn) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM inventario ORDER BY ubicacion, aula, codigo", conn)
    return df

def guardar_equipo(conn, datos: dict, es_nuevo: bool):
    if es_nuevo:
        conn.execute(
            """INSERT INTO inventario
               (codigo,nombre,tipo,marca,modelo,numero_serie,ubicacion,aula,estado,fecha_alta,observaciones)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (datos['codigo'], datos['nombre'], datos['tipo'], datos['marca'], datos['modelo'],
             datos['numero_serie'], datos['ubicacion'], datos['aula'], datos['estado'],
             datos['fecha_alta'], datos['observaciones'])
        )
    else:
        conn.execute(
            """UPDATE inventario SET
               nombre=?,tipo=?,marca=?,modelo=?,numero_serie=?,
               ubicacion=?,aula=?,estado=?,fecha_alta=?,observaciones=?
               WHERE codigo=?""",
            (datos['nombre'], datos['tipo'], datos['marca'], datos['modelo'],
             datos['numero_serie'], datos['ubicacion'], datos['aula'], datos['estado'],
             datos['fecha_alta'], datos['observaciones'], datos['codigo'])
        )
    conn.commit()

def eliminar_equipos(conn, ids: list):
    for i in ids:
        conn.execute("DELETE FROM inventario WHERE id=?", (i,))
    conn.commit()

# =====================================================
# PÁGINA: INVENTARIO DEL INSTITUTO
# =====================================================

def tab_inventario(conn):
    """Tab Inventario: tabla interactiva + gráfico + filtros por ubicación/aula."""

    # ── Intentamos importar plotly; si no está disponible usamos st.bar_chart
    try:
        import plotly.express as px
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False

    st.subheader("🖥️ Inventario del Instituto")

    df_inv = cargar_inventario(conn)

    # ── Botón Añadir equipo ────────────────────────────────────────────
    with st.expander("➕ Añadir Nuevo Equipo", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            n_codigo   = st.text_input("Código / Nº inventario *", key="inv_cod")
            n_nombre   = st.text_input("Descripción / Nombre",     key="inv_nom")
            n_tipo     = st.selectbox("Tipo de equipo",            TIPOS_EQUIPO, key="inv_tipo")
            n_estado   = st.selectbox("Estado", ["Operativo","En reparación","Baja","Reserva"], key="inv_est")
        with c2:
            n_marca    = st.text_input("Marca",         key="inv_marca")
            n_modelo   = st.text_input("Modelo",        key="inv_modelo")
            n_serie    = st.text_input("Nº de Serie",   key="inv_serie")
            n_fecha    = st.date_input("Fecha de Alta", value=datetime.date.today(), key="inv_fecha")
        with c3:
            n_ubicacion = st.text_input("Ubicación (Ej: Edificio A, Planta 1)", key="inv_ubi")
            n_aula      = st.text_input("Aula / Sala (Ej: Aula 101, Lab. Informática)", key="inv_aula")
            n_obs       = st.text_area("Observaciones", height=100, key="inv_obs")

        if st.button("💾 Guardar Equipo", key="btn_add_inv"):
            if not n_codigo.strip():
                st.error("El código es obligatorio.")
            else:
                try:
                    guardar_equipo(conn, {
                        'codigo': n_codigo.strip(), 'nombre': n_nombre,
                        'tipo': n_tipo, 'marca': n_marca, 'modelo': n_modelo,
                        'numero_serie': n_serie, 'ubicacion': n_ubicacion,
                        'aula': n_aula, 'estado': n_estado,
                        'fecha_alta': n_fecha.strftime("%d-%m-%Y"),
                        'observaciones': n_obs,
                    }, es_nuevo=True)
                    st.success(f"✅ Equipo **{n_codigo}** añadido correctamente.")
                    clear_cache(); time.sleep(0.4); st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Ya existe un equipo con ese código.")

    st.markdown("---")

    if df_inv.empty:
        st.info("No hay equipos registrados aún. Añade el primero con el botón de arriba.")
        return

    # ── Métricas resumen ───────────────────────────────────────────────
    total     = len(df_inv)
    operativo = len(df_inv[df_inv['estado'] == 'Operativo'])
    reparac   = len(df_inv[df_inv['estado'] == 'En reparación'])
    baja      = len(df_inv[df_inv['estado'] == 'Baja'])

    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f'<div class="inv-metric"><div class="val">{total}</div><div class="lbl">Total equipos</div></div>', unsafe_allow_html=True)
    m2.markdown(f'<div class="inv-metric"><div class="val" style="color:#1a7f3c">{operativo}</div><div class="lbl">Operativos</div></div>', unsafe_allow_html=True)
    m3.markdown(f'<div class="inv-metric"><div class="val" style="color:#d97706">{reparac}</div><div class="lbl">En reparación</div></div>', unsafe_allow_html=True)
    m4.markdown(f'<div class="inv-metric"><div class="val" style="color:#dc2626">{baja}</div><div class="lbl">Baja</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Filtros ────────────────────────────────────────────────────────
    st.markdown("#### 🔎 Filtros")
    fc1, fc2, fc3, fc4, fc5 = st.columns(5)

    ubicaciones  = sorted([u for u in df_inv['ubicacion'].dropna().unique() if u.strip()])
    aulas        = sorted([a for a in df_inv['aula'].dropna().unique()      if a.strip()])
    tipos_disp   = sorted([t for t in df_inv['tipo'].dropna().unique()      if t.strip()])
    estados_disp = sorted([e for e in df_inv['estado'].dropna().unique()    if e.strip()])

    with fc1: f_ubicacion = st.multiselect("📍 Ubicación",    options=ubicaciones,  key="inv_f_ubi")
    with fc2: f_aula      = st.multiselect("🏫 Aula / Sala",  options=aulas,        key="inv_f_aula")
    with fc3: f_tipo      = st.multiselect("🖥️ Tipo",         options=tipos_disp,   key="inv_f_tipo")
    with fc4: f_estado    = st.multiselect("🔵 Estado",       options=estados_disp, key="inv_f_estado")
    with fc5: f_texto     = st.text_input("🔍 Buscar texto",  placeholder="Marca, modelo, código…", key="inv_f_texto")

    df_f = df_inv.copy()
    if f_ubicacion: df_f = df_f[df_f['ubicacion'].isin(f_ubicacion)]
    if f_aula:      df_f = df_f[df_f['aula'].isin(f_aula)]
    if f_tipo:      df_f = df_f[df_f['tipo'].isin(f_tipo)]
    if f_estado:    df_f = df_f[df_f['estado'].isin(f_estado)]
    if f_texto.strip():
        q = f_texto.strip().lower()
        mask = (
            df_f['codigo'].str.lower().str.contains(q, na=False)  |
            df_f['nombre'].str.lower().str.contains(q, na=False)  |
            df_f['marca'].str.lower().str.contains(q, na=False)   |
            df_f['modelo'].str.lower().str.contains(q, na=False)  |
            df_f['numero_serie'].str.lower().str.contains(q, na=False)
        )
        df_f = df_f[mask]

    st.caption(f"Mostrando **{len(df_f)}** de **{total}** equipos")

    # ── Gráfico: equipos por aula ──────────────────────────────────────
    st.markdown("#### 📊 Distribución por Aula / Sala")

    df_chart = df_f.copy()
    df_chart['aula_label'] = df_chart['aula'].fillna('Sin aula').replace('', 'Sin aula')

    if not df_chart.empty:
        por_aula = (df_chart.groupby(['aula_label', 'estado'])
                            .size()
                            .reset_index(name='cantidad'))

        if HAS_PLOTLY:
            import plotly.express as px
            color_map = {
                'Operativo':      '#0b6e3c',
                'En reparación':  '#d97706',
                'Baja':           '#dc2626',
                'Reserva':        '#6366f1',
            }
            fig = px.bar(
                por_aula,
                x='aula_label', y='cantidad', color='estado',
                color_discrete_map=color_map,
                labels={'aula_label': 'Aula / Sala', 'cantidad': 'Nº Equipos', 'estado': 'Estado'},
                title='Equipos por Aula — desglosados por Estado',
                barmode='stack',
                height=380,
            )
            fig.update_layout(
                plot_bgcolor='#f9fafb',
                paper_bgcolor='#ffffff',
                legend_title_text='Estado',
                xaxis_tickangle=-35,
                margin=dict(l=20, r=20, t=50, b=60),
                font=dict(family='sans-serif', size=13),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Fallback sin plotly
            pivot = por_aula.pivot_table(
                index='aula_label', columns='estado', values='cantidad', fill_value=0
            )
            st.bar_chart(pivot)
    else:
        st.info("No hay datos para mostrar en el gráfico con los filtros actuales.")

    # ── Tabla interactiva ──────────────────────────────────────────────
    st.markdown("#### 📋 Tabla de Inventario")

    df_edit = df_f.copy()
    df_edit.insert(0, "Sel", False)

    col_cfg = {
        "Sel":          st.column_config.CheckboxColumn("✅", width="small"),
        "id":           {"hidden": True},
        "codigo":       st.column_config.TextColumn("Código", disabled=True),
        "nombre":       st.column_config.TextColumn("Descripción"),
        "tipo":         st.column_config.SelectboxColumn("Tipo", options=TIPOS_EQUIPO),
        "marca":        st.column_config.TextColumn("Marca"),
        "modelo":       st.column_config.TextColumn("Modelo"),
        "numero_serie": st.column_config.TextColumn("Nº Serie"),
        "ubicacion":    st.column_config.TextColumn("Ubicación"),
        "aula":         st.column_config.TextColumn("Aula / Sala"),
        "estado":       st.column_config.SelectboxColumn("Estado", options=["Operativo","En reparación","Baja","Reserva"]),
        "fecha_alta":   st.column_config.TextColumn("Fecha Alta"),
        "observaciones":st.column_config.TextColumn("Observaciones"),
    }

    edited = st.data_editor(df_edit, num_rows="fixed", key="ed_inv",
                            column_config=col_cfg, use_container_width=True, height=420)

    c_save, c_del, c_exp = st.columns([1, 1, 2])
    with c_save:
        if st.button("💾 Guardar Cambios", key="btn_save_inv", type="primary"):
            try:
                cambios = 0
                for _, row in edited.iterrows():
                    if row['codigo']:
                        conn.execute(
                            """UPDATE inventario SET nombre=?,tipo=?,marca=?,modelo=?,
                               numero_serie=?,ubicacion=?,aula=?,estado=?,
                               fecha_alta=?,observaciones=? WHERE codigo=?""",
                            (row['nombre'], row['tipo'], row['marca'], row['modelo'],
                             row['numero_serie'], row['ubicacion'], row['aula'],
                             row['estado'], row['fecha_alta'], row['observaciones'],
                             row['codigo'])
                        )
                        cambios += 1
                conn.commit()
                st.success(f"✅ {cambios} registros guardados.")
                clear_cache(); time.sleep(0.4); st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    with c_del:
        if st.button("🗑️ Eliminar Seleccionados", key="btn_del_inv"):
            ids_borrar = edited[edited["Sel"] == True]["id"].dropna().astype(int).tolist()
            if ids_borrar:
                eliminar_equipos(conn, ids_borrar)
                st.success(f"🗑️ {len(ids_borrar)} equipo(s) eliminado(s).")
                clear_cache(); time.sleep(0.4); st.rerun()
            else:
                st.warning("Selecciona al menos un equipo con el checkbox ✅.")

    with c_exp:
        if not df_f.empty:
            cols_export = [c for c in df_f.columns if c != 'id']
            excel_inv = to_excel_download(df_f[cols_export])
            st.download_button(
                "📥 Exportar a Excel",
                data=excel_inv,
                file_name="inventario_instituto.xlsx",
                mime="application/vnd.ms-excel",
                key="btn_exp_inv"
            )

    # ── Detalle por ubicación (acordeón) ──────────────────────────────
    st.markdown("---")
    st.markdown("#### 📍 Vista por Ubicación")

    ubicaciones_en_df = sorted(df_f['ubicacion'].fillna('Sin ubicación').replace('', 'Sin ubicación').unique())
    for ubi in ubicaciones_en_df:
        df_ubi = df_f[df_f['ubicacion'].fillna('Sin ubicación').replace('', 'Sin ubicación') == ubi]
        with st.expander(f"📍 {ubi}  —  {len(df_ubi)} equipo(s)"):
            aulas_ubi = sorted(df_ubi['aula'].fillna('Sin aula').replace('', 'Sin aula').unique())
            for aula in aulas_ubi:
                df_aula = df_ubi[df_ubi['aula'].fillna('Sin aula').replace('', 'Sin aula') == aula]
                st.markdown(f"**🏫 {aula}** &nbsp; ({len(df_aula)} equipos)")
                st.dataframe(
                    df_aula[['codigo','nombre','tipo','marca','modelo','estado','numero_serie','observaciones']],
                    use_container_width=True, hide_index=True
                )


# =====================================================
# PÁGINA: PRODUCTOS (idéntico al PEMA original)
# =====================================================

def tab_productos(conn, df_arts, current_user):
    st.subheader("Catálogo de Productos")

    with st.expander("➕ Añadir Nuevo Producto", expanded=False):
        ca1, ca2, ca3 = st.columns(3)
        n_code = ca1.text_input("Código Nuevo", key="prod_code")
        n_name = ca2.text_input("Nombre Nuevo", key="prod_name")
        n_type = ca3.selectbox("Categoría", list(GROUPS_CONFIG.keys()), key="prod_cat")
        if st.button("Crear Producto", key="btn_crear_prod"):
            if n_code and n_name:
                try:
                    cat_real = GROUPS_CONFIG[n_type]["cat"]
                    conn.execute(
                        "INSERT INTO articles (code,name,type,initial_stock,entries,exits,current_stock,created_by) VALUES (?,?,?,0,0,0,0,?)",
                        (n_code.strip(), n_name, cat_real, current_user)
                    )
                    conn.commit()
                    st.success("Producto añadido.")
                    clear_cache(); time.sleep(0.5); st.rerun()
                except Exception:
                    st.error("Error: El código ya existe u otro error.")
            else:
                st.warning("Rellena código y nombre")

    df_all = df_arts.copy()
    df_all['type']         = df_all['type'].fillna('Otros').replace('', 'Otros')
    df_all['visual_group'] = df_all.apply(determine_visual_group, axis=1)

    f_col1, f_col2 = st.columns(2)
    with f_col1:
        filtro_grupo = st.multiselect("📂 Filtrar por Grupo Visual:",  options=list(GROUPS_CONFIG.keys()), key="prd_fg")
    with f_col2:
        cats_disp    = sorted(list({t for t in df_all['type'].unique() if pd.notna(t)}))
        filtro_cat   = st.multiselect("🏷️ Filtrar por Categoría:", options=cats_disp, key="prd_fc")

    if filtro_grupo: df_all = df_all[df_all['visual_group'].isin(filtro_grupo)]
    if filtro_cat:   df_all = df_all[df_all['type'].isin(filtro_cat)]

    for group_name in GROUPS_CONFIG.keys():
        group_df = df_all[df_all['visual_group'] == group_name].copy()
        if group_df.empty: continue

        group_df['current_stock'] = pd.to_numeric(group_df['current_stock'], errors='coerce').fillna(0)

        with st.expander(f"📂 {group_name} ({len(group_df)})"):
            group_df.insert(0, "Sel", False)
            safe_key = re.sub(r'\W+', '', group_name)

            edited_grp = st.data_editor(
                group_df, num_rows="dynamic", key=f"ed_{safe_key}",
                column_config={
                    "Sel":           st.column_config.CheckboxColumn("✅", width="small"),
                    "display_full":  None,
                    "code":          st.column_config.TextColumn("Código", disabled=True),
                    "name":          st.column_config.TextColumn("Nombre"),
                    "type":          st.column_config.SelectboxColumn("Categoría", options=[
                        "Almacenamiento","Conectores/Adaptadores","Cables",
                        "Energía","Periféricos","Redes","Consumibles","Otros"]),
                    "current_stock": st.column_config.NumberColumn("Stock", disabled=False),
                    "created_by":    st.column_config.TextColumn("Creador", disabled=True),
                    "entries": None, "exits": None,
                    "visual_group": None, "initial_stock": None,
                },
                use_container_width=True, hide_index=True
            )

            cb1, cb2 = st.columns(2)
            with cb1:
                if st.button("💾 Guardar Cambios", key=f"save_{safe_key}"):
                    try:
                        for _, row in edited_grp.iterrows():
                            if row['code']:
                                nc   = float(row['current_stock'])
                                ents = float(row['entries'])
                                exts = float(row['exits'])
                                conn.execute(
                                    "UPDATE articles SET name=?,type=?,initial_stock=?,current_stock=? WHERE code=?",
                                    (row['name'], row['type'], nc-ents+exts, nc, row['code'])
                                )
                        conn.commit()
                        st.success("Actualizado.")
                        clear_cache(); time.sleep(0.5); st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            with cb2:
                if st.button("🗑️ Eliminar", key=f"del_{safe_key}"):
                    try:
                        to_del = edited_grp[edited_grp["Sel"] == True]["code"].tolist()
                        for c in to_del:
                            conn.execute("DELETE FROM articles WHERE code=?", (c,))
                        conn.commit()
                        st.success("Eliminado.")
                        clear_cache(); time.sleep(0.5); st.rerun()
                    except: pass


# =====================================================
# MAIN
# =====================================================

def main():
    initialize_db()
    cargar_estilos_css()

    if 'selected_menu' not in st.session_state:
        st.session_state['selected_menu'] = "PEMA"

    current_user = "Usuario PEMA"

    with st.sidebar:
        if LOGO_FILE.exists():
            st.image(str(LOGO_FILE), use_container_width=True)
        st.title("Gestión del PEMA")

        if st.button("PEMA", key="nav_PEMA", use_container_width=True):
            st.session_state['selected_menu'] = "PEMA"
            st.rerun()

        if st.button("Configuración", key="nav_Config", use_container_width=True):
            st.session_state['selected_menu'] = "Configuración"
            st.rerun()

    menu = st.session_state['selected_menu']

    # ================================================================
    if menu == "PEMA":
        st.title("PEMA")
        conn = get_db_connection()

        # Datos base
        df_arts  = pd.read_sql("SELECT code,name,type,initial_stock,entries,exits,current_stock,created_by FROM articles", conn)
        df_provs = pd.read_sql("SELECT code,fiscal_name,phone,email,city FROM providers", conn)
        df_clis  = pd.read_sql("SELECT code,fiscal_name,name,surname,phone,email,city FROM clients", conn)

        df_arts['code']  = df_arts['code'].apply(safe_str_code)
        df_provs['code'] = df_provs['code'].apply(safe_str_code)
        df_clis['code']  = df_clis['code'].apply(safe_str_code)

        df_arts  = sort_df_naturally(df_arts,  'code')
        df_provs = sort_df_naturally(df_provs, 'code')
        df_clis  = sort_df_naturally(df_clis,  'code')

        df_arts['display_full']  = df_arts.apply( lambda x: format_mixed(x['code'], x['name']),       axis=1)
        df_provs['display_full'] = df_provs.apply(lambda x: format_mixed(x['code'], x['fiscal_name']), axis=1)
        df_clis['display_full']  = df_clis.apply( lambda x: format_mixed(x['code'], x['fiscal_name']), axis=1)

        list_articles_full  = [x for x in df_arts['display_full']  if x]
        list_providers_full = [x for x in df_provs['display_full'] if x]
        list_clients_full   = [x for x in df_clis['display_full']  if x]

        list_responsibles = []
        if not df_clis.empty:
            list_responsibles = [
                x for x in df_clis.apply(
                    lambda r: f"{r['name'] or ''} {r['surname'] or ''}".strip(), axis=1
                ).unique() if x
            ]

        sede_resp_map = {}
        for _, row in df_clis.iterrows():
            sn = row['fiscal_name']
            fn = f"{row['name'] or ''} {row['surname'] or ''}".strip()
            if sn not in sede_resp_map: sede_resp_map[sn] = []
            if fn: sede_resp_map[sn].append(fn)

        # ── Tabs: Inventario reemplaza Existencias, Productos igual al PEMA ──
        t_inv, t_prod, t_ent, t_sal, t_sedes, t_provs = st.tabs([
            "🖥️ Inventario", "📦 Productos",
            "📥 Entradas",   "📤 Salidas",
            "🏢 Sedes",      "🏭 Proveedores"
        ])

        # ── 1. INVENTARIO ──────────────────────────────────────────────
        with t_inv:
            tab_inventario(conn)

        # ── 2. PRODUCTOS (idéntico al PEMA) ────────────────────────────
        with t_prod:
            tab_productos(conn, df_arts, current_user)

        # ── 3. ENTRADAS ────────────────────────────────────────────────
        with t_ent:
            st.subheader("Entradas")
            df = pd.read_sql(
                "SELECT id,entry_code,date,provider_name,provider_code,article_name,article_code,quantity FROM stock_entries ORDER BY date DESC,id DESC",
                conn
            )
            df['date']       = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
            df['quantity']   = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
            df['entry_code'] = df['entry_code'].apply(safe_str_code)
            df['provider_mixed'] = df.apply(lambda x: format_mixed(x['provider_code'], x['provider_name']), axis=1)
            df['article_mixed']  = df.apply(lambda x: format_mixed(x['article_code'],  x['article_name']),  axis=1)

            with st.expander("➕ Añadir Nueva Entrada", expanded=False):
                ce1,ce2,ce3,ce4,ce5 = st.columns(5)
                ne_code = ce1.text_input("Cód. Entrada")
                ne_date = ce2.date_input("Fecha", value=datetime.date.today(), key="ne_date")
                ne_prov = ce3.selectbox("Proveedor", [""]+list_providers_full, key="ne_prov")
                ne_art  = ce4.selectbox("Artículo",  [""]+list_articles_full,  key="ne_art")
                ne_qty  = ce5.number_input("Cantidad", min_value=1, step=1, key="ne_qty")
                if st.button("Guardar Entrada", key="btn_ent_new"):
                    if ne_art and ne_qty > 0:
                        pc,pn = ("",""); ac,an = ("","")
                        if ne_prov:
                            pts=ne_prov.split(' / ',1)
                            if len(pts)==2: pc,pn=pts
                        if ne_art:
                            pts=ne_art.split(' / ',1)
                            if len(pts)==2: ac,an=pts
                        try:
                            conn.execute(
                                "INSERT INTO stock_entries (entry_code,date,provider_name,provider_code,article_name,article_code,quantity,last_modified_by) VALUES (?,?,?,?,?,?,?,?)",
                                (ne_code.strip() or None, ne_date.strftime("%d-%m-%Y"), pn,pc,an,ac,ne_qty,current_user)
                            )
                            conn.commit(); sync_stock_calculations(conn)
                            st.success("Entrada creada."); clear_cache(); time.sleep(0.5); st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
                    else: st.warning("Selecciona Artículo y Cantidad.")

            # Filtros
            ff1,ff2,ff3,ff4 = st.columns(4)
            with ff1: fe_date  = st.date_input("📅 Rango:", value=[], key="fe_date")
            with ff2: fe_code  = st.multiselect("🔢 Código:",    options=sorted([c for c in df['entry_code'].unique()    if c]), key="fe_cod")
            with ff3: fe_prov  = st.multiselect("🏢 Proveedor:", options=sorted([p for p in df['provider_mixed'].unique() if p]), key="fe_prov")
            with ff4: fe_art   = st.multiselect("📦 Artículo:",  options=sorted([a for a in df['article_mixed'].unique()  if a]), key="fe_art")

            dv = df.copy()
            if fe_date and len(fe_date)==2: dv=dv[dv['date'].dt.date.between(fe_date[0],fe_date[1]).fillna(False)]
            elif fe_date and len(fe_date)==1: dv=dv[(dv['date'].dt.date==fe_date[0]).fillna(False)]
            if fe_code: dv=dv[dv['entry_code'].isin(fe_code)]
            if fe_prov: dv=dv[dv['provider_mixed'].isin(fe_prov)]
            if fe_art:  dv=dv[dv['article_mixed'].isin(fe_art)]

            map_ent={"entry_code":"Cód. Entrada","date":"Fecha","provider_name":"Proveedor","article_code":"Cód. Artículo","article_name":"Artículo","quantity":"Cantidad"}
            cx1,cx2=st.columns([3,1])
            with cx1: cs_ent=st.multiselect("📊 Columnas exportar:",options=list(map_ent.values()),default=list(map_ent.values()),key="cs_ent")
            with cx2:
                if cs_ent:
                    imap={v:k for k,v in map_ent.items()}
                    df_ex=dv[[imap[v] for v in cs_ent if v in imap]].copy()
                    if 'date' in df_ex.columns: df_ex['date']=df_ex['date'].dt.strftime('%d-%m-%Y')
                    df_ex.rename(columns=map_ent,inplace=True)
                    st.download_button("📥 Excel",data=to_excel_download(df_ex),file_name="entradas.xlsx",mime="application/vnd.ms-excel")

            dv.insert(0,"Sel",False)
            ed_ent=st.data_editor(dv,num_rows="dynamic",key="ed_ent",column_config={
                "Sel":st.column_config.CheckboxColumn("✅",width="small"),
                "id":{"hidden":True},"provider_code":{"hidden":True},"provider_name":{"hidden":True},
                "article_code":{"hidden":True},"article_name":{"hidden":True},
                "entry_code":st.column_config.TextColumn("Código"),
                "date":st.column_config.DateColumn("Fecha",format="DD-MM-YYYY"),
                "provider_mixed":st.column_config.SelectboxColumn("Proveedor",options=list_providers_full,width="medium"),
                "article_mixed":st.column_config.SelectboxColumn("Artículo",options=list_articles_full,width="medium"),
                "quantity":st.column_config.NumberColumn("Cant.")
            },use_container_width=True)

            cs1,cs2=st.columns(2)
            with cs1:
                if st.button("💾 Guardar Cambios",key="save_ent",type="primary"):
                    try:
                        with st.spinner("Sincronizando..."):
                            for _,row in ed_ent.iterrows():
                                pc,pn=("",""); ac,an=("","")
                                if row['provider_mixed']:
                                    pts=row['provider_mixed'].split(' / ',1)
                                    if len(pts)==2: pc,pn=pts
                                if row['article_mixed']:
                                    pts=row['article_mixed'].split(' / ',1)
                                    if len(pts)==2: ac,an=pts
                                ds=format_date_eu(row['date'])
                                if pd.isna(row['id']):
                                    conn.execute("INSERT INTO stock_entries (entry_code,date,provider_name,provider_code,article_name,article_code,quantity,last_modified_by) VALUES (?,?,?,?,?,?,?,?)",(row['entry_code'] or None,ds,pn,pc,an,ac,row['quantity'],current_user))
                                else:
                                    conn.execute("UPDATE stock_entries SET entry_code=?,date=?,provider_name=?,provider_code=?,article_name=?,article_code=?,quantity=?,last_modified_by=? WHERE id=?",(row['entry_code'] or None,ds,pn,pc,an,ac,row['quantity'],current_user,row['id']))
                            conn.commit(); sync_stock_calculations(conn)
                        st.success("Guardado."); clear_cache(); time.sleep(0.5); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
            with cs2:
                if st.button("🗑️ Eliminar Seleccionados",key="del_ent"):
                    try:
                        for i in ed_ent[ed_ent["Sel"]==True]["id"].dropna().tolist():
                            conn.execute("DELETE FROM stock_entries WHERE id=?",(i,))
                        conn.commit(); sync_stock_calculations(conn); st.success("Eliminado."); clear_cache(); time.sleep(0.5); st.rerun()
                    except: pass

        # ── 4. SALIDAS ─────────────────────────────────────────────────
        with t_sal:
            st.subheader("Salidas")
            df = pd.read_sql(
                "SELECT id,exit_code,date,client_name,client_code,article_name,article_code,quantity,delivered_to FROM stock_exits",
                conn
            )
            df['date']      = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
            df['quantity']  = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
            df['exit_code'] = df['exit_code'].apply(safe_str_code)
            df = sort_df_naturally(df, 'exit_code')
            df['client_mixed']  = df.apply(lambda x: format_mixed(x['client_code'],  x['client_name']),  axis=1)
            df['article_mixed'] = df.apply(lambda x: format_mixed(x['article_code'], x['article_name']), axis=1)

            with st.expander("➕ Añadir Nueva Salida", expanded=False):
                cs1n,cs2n,cs3n,cs4n,cs5n,cs6n = st.columns(6)
                ns_code = cs1n.text_input("Cód. Salida", key="ns_code")
                ns_date = cs2n.date_input("Fecha", value=datetime.date.today(), key="ns_date")
                ns_cli  = cs3n.selectbox("Sede", [""]+list_clients_full, key="ns_cli")
                ns_art  = cs4n.selectbox("Artículo", [""]+list_articles_full, key="ns_art")
                ns_qty  = cs5n.number_input("Cantidad", min_value=1, step=1, key="ns_qty")
                ns_resp = cs6n.selectbox("Responsable", [""]+list_responsibles, key="ns_resp")
                if st.button("Guardar Salida", key="btn_sal_new"):
                    if ns_art and ns_qty > 0:
                        cc,cn=("",""); ac,an=("","")
                        if ns_cli:
                            pts=ns_cli.split(' / ',1)
                            if len(pts)==2: cc,cn=pts
                        if ns_art:
                            pts=ns_art.split(' / ',1)
                            if len(pts)==2: ac,an=pts
                        if not ns_resp and cn:
                            cands=sede_resp_map.get(cn,[])
                            if len(cands)==1: ns_resp=cands[0]
                        try:
                            conn.execute(
                                "INSERT INTO stock_exits (exit_code,date,client_name,client_code,article_name,article_code,quantity,delivered_to,last_modified_by) VALUES (?,?,?,?,?,?,?,?,?)",
                                (ns_code.strip() or None,ns_date.strftime("%d-%m-%Y"),cn,cc,an,ac,ns_qty,ns_resp,current_user)
                            )
                            conn.commit(); sync_stock_calculations(conn)
                            st.success("Salida creada."); clear_cache(); time.sleep(0.5); st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
                    else: st.warning("Selecciona Artículo y Cantidad.")

            # Filtros
            sf1,sf2,sf3,sf4,sf5 = st.columns(5)
            with sf1: fs_date  = st.date_input("📅 Rango:", value=[], key="fs_date")
            with sf2: fs_code  = st.multiselect("🔢 Código:",     options=sorted([c for c in df['exit_code'].unique()    if c]), key="fs_cod")
            with sf3: fs_sede  = st.multiselect("🏢 Sede:",       options=sorted([s for s in df['client_mixed'].unique()  if s]), key="fs_sede")
            with sf4: fs_art   = st.multiselect("📦 Artículo:",   options=sorted([a for a in df['article_mixed'].unique() if a]), key="fs_art")
            with sf5: fs_resp  = st.multiselect("👤 Responsable:",options=sorted([r for r in df['delivered_to'].unique()  if pd.notna(r) and r]), key="fs_resp")

            ds_v = df.copy()
            if fs_date and len(fs_date)==2: ds_v=ds_v[ds_v['date'].dt.date.between(fs_date[0],fs_date[1]).fillna(False)]
            elif fs_date and len(fs_date)==1: ds_v=ds_v[(ds_v['date'].dt.date==fs_date[0]).fillna(False)]
            if fs_code: ds_v=ds_v[ds_v['exit_code'].isin(fs_code)]
            if fs_sede: ds_v=ds_v[ds_v['client_mixed'].isin(fs_sede)]
            if fs_art:  ds_v=ds_v[ds_v['article_mixed'].isin(fs_art)]
            if fs_resp: ds_v=ds_v[ds_v['delivered_to'].isin(fs_resp)]

            map_ext={"exit_code":"Cód. Salida","date":"Fecha","client_name":"Sede/Cliente","article_code":"Cód. Artículo","article_name":"Artículo","quantity":"Cantidad","delivered_to":"Responsable"}
            sx1,sx2=st.columns([3,1])
            with sx1: cs_ext=st.multiselect("📊 Columnas exportar:",options=list(map_ext.values()),default=list(map_ext.values()),key="cs_ext")
            with sx2:
                if cs_ext:
                    imap_ex={v:k for k,v in map_ext.items()}
                    df_ex2=ds_v[[imap_ex[v] for v in cs_ext if v in imap_ex]].copy()
                    if 'date' in df_ex2.columns: df_ex2['date']=df_ex2['date'].dt.strftime('%d-%m-%Y')
                    df_ex2.rename(columns=map_ext,inplace=True)
                    st.download_button("📥 Excel",data=to_excel_download(df_ex2),file_name="salidas.xlsx",mime="application/vnd.ms-excel",key="btn_down_sal")

            ds_v.insert(0,"Sel",False)
            ed_sal=st.data_editor(ds_v,num_rows="dynamic",key="ed_sal",column_config={
                "Sel":st.column_config.CheckboxColumn("✅",width="small"),
                "id":{"hidden":True},"client_code":{"hidden":True},"client_name":{"hidden":True},
                "article_code":{"hidden":True},"article_name":{"hidden":True},
                "exit_code":st.column_config.TextColumn("Código"),
                "date":st.column_config.DateColumn("Fecha",format="DD-MM-YYYY"),
                "client_mixed":st.column_config.SelectboxColumn("Sede",options=list_clients_full,width="medium"),
                "article_mixed":st.column_config.SelectboxColumn("Artículo",options=list_articles_full,width="medium"),
                "quantity":st.column_config.NumberColumn("Cant."),
                "delivered_to":st.column_config.SelectboxColumn("Responsable",options=list_responsibles)
            },use_container_width=True)

            ss1,ss2=st.columns(2)
            with ss1:
                if st.button("💾 Guardar Cambios",key="save_sal",type="primary"):
                    try:
                        with st.spinner("Sincronizando..."):
                            for _,row in ed_sal.iterrows():
                                cc,cn=("",""); ac,an=("","")
                                if row['client_mixed']:
                                    pts=row['client_mixed'].split(' / ',1)
                                    if len(pts)==2: cc,cn=pts
                                if row['article_mixed']:
                                    pts=row['article_mixed'].split(' / ',1)
                                    if len(pts)==2: ac,an=pts
                                ds=format_date_eu(row['date'])
                                fr=row['delivered_to']
                                if not fr and cn:
                                    cands=sede_resp_map.get(cn,[])
                                    if len(cands)==1: fr=cands[0]
                                if pd.isna(row['id']):
                                    conn.execute("INSERT INTO stock_exits (exit_code,date,client_name,client_code,article_name,article_code,quantity,delivered_to,last_modified_by) VALUES (?,?,?,?,?,?,?,?,?)",(row['exit_code'] or None,ds,cn,cc,an,ac,row['quantity'],fr,current_user))
                                else:
                                    conn.execute("UPDATE stock_exits SET exit_code=?,date=?,client_name=?,client_code=?,article_name=?,article_code=?,quantity=?,delivered_to=?,last_modified_by=? WHERE id=?",(row['exit_code'] or None,ds,cn,cc,an,ac,row['quantity'],fr,current_user,row['id']))
                            conn.commit(); sync_stock_calculations(conn)
                        st.success("Guardado."); clear_cache(); time.sleep(0.5); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
            with ss2:
                if st.button("🗑️ Eliminar Seleccionados",key="del_sal"):
                    try:
                        for i in ed_sal[ed_sal["Sel"]==True]["id"].dropna().tolist():
                            conn.execute("DELETE FROM stock_exits WHERE id=?",(i,))
                        conn.commit(); sync_stock_calculations(conn); st.success("Eliminado."); clear_cache(); time.sleep(0.5); st.rerun()
                    except: pass

        # ── 5. SEDES ───────────────────────────────────────────────────
        with t_sedes:
            st.subheader("Sedes")
            with st.expander("➕ Añadir Nueva Sede", expanded=False):
                sc1,sc2,sc3=st.columns(3)
                n_ccode=sc1.text_input("Código",key="nc_code"); n_cname=sc2.text_input("Nombre Fiscal",key="nc_name"); n_cphone=sc3.text_input("Teléfono",key="nc_phone")
                if st.button("Crear Sede",key="btn_sede"):
                    if n_ccode and n_cname:
                        try:
                            conn.execute("INSERT INTO clients (code,fiscal_name,phone) VALUES (?,?,?)",(n_ccode.strip(),n_cname,n_cphone))
                            conn.commit(); st.success("Sede añadida."); clear_cache(); time.sleep(0.5); st.rerun()
                        except sqlite3.IntegrityError: st.error("Código duplicado.")
            df_cv=df_clis.copy()
            ciudades_c=sorted([c for c in df_cv['city'].unique() if pd.notna(c) and c.strip()])
            fc_=st.multiselect("🌆 Ciudad:",options=ciudades_c,key="ms_city_cli")
            if fc_: df_cv=df_cv[df_cv['city'].isin(fc_)]
            df_cv.insert(0,"Sel",False)
            ed_cli=st.data_editor(df_cv,num_rows="dynamic",key="ed_cli",column_config={
                "Sel":st.column_config.CheckboxColumn("✅",width="small"),"display_full":None,
                "code":st.column_config.TextColumn("Código"),"fiscal_name":"Nombre","phone":"Teléfono","email":"Email","city":"Ciudad"
            },use_container_width=True)
            sc_s,sc_d=st.columns(2)
            with sc_s:
                if st.button("💾 Guardar",key="save_cli",type="primary"):
                    try:
                        for _,row in ed_cli.iterrows():
                            if row['code']: conn.execute("INSERT OR REPLACE INTO clients (code,fiscal_name,phone,email,city) VALUES (?,?,?,?,?)",(row['code'],row['fiscal_name'],row['phone'],row['email'],row['city']))
                        conn.commit(); st.success("Guardado."); clear_cache(); time.sleep(0.5); st.rerun()
                    except: pass
            with sc_d:
                if st.button("🗑️ Eliminar",key="del_cli"):
                    try:
                        for c in ed_cli[ed_cli["Sel"]==True]["code"].tolist():
                            conn.execute("DELETE FROM clients WHERE code=?",(c,))
                        conn.commit(); st.success("Eliminado."); clear_cache(); time.sleep(0.5); st.rerun()
                    except: pass

        # ── 6. PROVEEDORES ─────────────────────────────────────────────
        with t_provs:
            st.subheader("Proveedores")
            with st.expander("➕ Añadir Nuevo Proveedor", expanded=False):
                pp1,pp2,pp3,pp4=st.columns(4)
                n_pcode=pp1.text_input("Código",key="np_code"); n_pname=pp2.text_input("Nombre Fiscal",key="np_name")
                n_pphone=pp3.text_input("Teléfono",key="np_phone"); n_pemail=pp4.text_input("Email",key="np_email")
                if st.button("Crear Proveedor",key="btn_prov"):
                    if n_pcode and n_pname:
                        try:
                            conn.execute("INSERT INTO providers (code,fiscal_name,phone,email) VALUES (?,?,?,?)",(n_pcode.strip(),n_pname,n_pphone,n_pemail))
                            conn.commit(); st.success("Proveedor añadido."); clear_cache(); time.sleep(0.5); st.rerun()
                        except sqlite3.IntegrityError: st.error("Código duplicado.")
            df_pv=df_provs.copy()
            ciudades_p=sorted([c for c in df_pv['city'].unique() if pd.notna(c) and c.strip()])
            fp_=st.multiselect("🌆 Ciudad:",options=ciudades_p,key="ms_city_prov")
            if fp_: df_pv=df_pv[df_pv['city'].isin(fp_)]
            df_pv.insert(0,"Sel",False)
            ed_prov=st.data_editor(df_pv,num_rows="dynamic",key="ed_prov",column_config={
                "Sel":st.column_config.CheckboxColumn("✅",width="small"),"display_full":None,
                "code":st.column_config.TextColumn("Código"),"fiscal_name":"Nombre",
                "phone":st.column_config.TextColumn("Teléfono"),"email":st.column_config.TextColumn("Email"),"city":"Ciudad"
            },use_container_width=True)
            sp_s,sp_d=st.columns(2)
            with sp_s:
                if st.button("💾 Guardar",key="save_prov",type="primary"):
                    try:
                        for _,row in ed_prov.iterrows():
                            if row['code']: conn.execute("INSERT OR REPLACE INTO providers (code,fiscal_name,phone,email,city) VALUES (?,?,?,?,?)",(row['code'],row['fiscal_name'],row['phone'],row['email'],row['city']))
                        conn.commit(); st.success("Guardado."); clear_cache(); time.sleep(0.5); st.rerun()
                    except: pass
            with sp_d:
                if st.button("🗑️ Eliminar",key="del_prov"):
                    try:
                        for c in ed_prov[ed_prov["Sel"]==True]["code"].tolist():
                            conn.execute("DELETE FROM providers WHERE code=?",(c,))
                        conn.commit(); st.success("Eliminado."); clear_cache(); time.sleep(0.5); st.rerun()
                    except: pass

        conn.close()

    # ================================================================
    elif menu == "Configuración":
        st.title("⚙️ Configuración del Sistema")
        st.markdown("### 📥 Importación de Datos")
        u = st.file_uploader("Subir archivo Excel (.xlsx)", type=["xlsx"])
        if u and st.button("Procesar Archivo"):
            with st.spinner("Procesando..."):
                ok, msg = import_master_excel(u, "Usuario PEMA")
                if ok:
                    st.success("Importación completada.")
                    st.json(msg)
                    time.sleep(3); st.rerun()
                else:
                    st.error(f"Error: {msg}")


if __name__ == "__main__":
    main()
