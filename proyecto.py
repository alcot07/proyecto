import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import traceback
import shutil
import hashlib
import json
import sqlite3
import datetime
import time
from pathlib import Path
from PIL import Image
from datetime import datetime as dt

# ============================================================================
# RUTAS
# ============================================================================
BASE_DIR         = Path(__file__).resolve().parent
DIR_DISENO       = BASE_DIR / "logo" / "alcot_logo.png"
ICONO_FILE       = DIR_DISENO / "alcot_logo.png"
HEADER_MAIN_FILE = DIR_DISENO / "alcot_logo.png"
CARPETA_REVISIONES = BASE_DIR / "revisiones"
CARPETA_REVISIONES.mkdir(exist_ok=True)
USUARIOS_FILE    = BASE_DIR / "usuarios.json"
DATA_DIR         = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_FILE          = DATA_DIR / "inventory_shared.db"

GROUPS_CONFIG = {
    "Discos duros": {"cat": "Almacenamiento"},
    "Memorias":     {"cat": "Almacenamiento"},
    "Adaptadores":  {"cat": "Conectores/Adaptadores"},
    "Cables":       {"cat": "Cables"},
    "Periféricos":  {"cat": "Periféricos"},
    "Switch":       {"cat": "Redes"},
    "Energía":      {"cat": "Energía"},
    "Otros":        {"cat": "Otros"},
}

APP_NAME = "Alcot's & Co."

LOGO_SVG = """
<svg width="100%" viewBox="0 0 680 290" xmlns="http://www.w3.org/2000/svg">
<rect x="0" y="0" width="680" height="280" fill="#0d1b2a" rx="16"/>
<g transform="translate(340,80)">
  <polygon points="-54,54 0,-54 0,0" fill="none" stroke="#7fff00" stroke-width="5" stroke-linejoin="round"/>
  <polygon points="54,54 0,-54 0,0" fill="none" stroke="#39d353" stroke-width="5" stroke-linejoin="round"/>
  <polygon points="0,-54 28,0 0,20 -28,0" fill="#39d353" opacity="0.25"/>
  <line x1="0" y1="-54" x2="0" y2="54" stroke="#7fff00" stroke-width="3"/>
  <line x1="-54" y1="54" x2="54" y2="54" stroke="#39d353" stroke-width="5" stroke-linecap="round"/>
</g>
<text x="340" y="195" text-anchor="middle" font-family="Arial Black, Arial, sans-serif" font-weight="900" font-size="48" letter-spacing="6" fill="#7fff00">ALCOT</text>
<text x="340" y="245" text-anchor="middle" font-family="Arial Black, Arial, sans-serif" font-weight="900" font-size="28" letter-spacing="8" fill="#39d353">&amp; CO</text>
</svg>
"""

# ============================================================================
# GESTIÓN DE USUARIOS
# ============================================================================
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

def cargar_usuarios():
    if USUARIOS_FILE.exists():
        try:
            with open(USUARIOS_FILE,'r',encoding='utf-8') as f: return json.load(f)
        except: pass
    d={"admin":{"password_hash":hash_password("admin123"),"nombre":"Administrador","rol":"admin"}}
    guardar_usuarios(d); return d

def guardar_usuarios(u):
    with open(USUARIOS_FILE,'w',encoding='utf-8') as f: json.dump(u,f,ensure_ascii=False,indent=2)

def verificar_credenciales(username,password):
    u=cargar_usuarios()
    return username in u and u[username]['password_hash']==hash_password(password)

# ============================================================================
# SESSION STATE
# ============================================================================
defaults={'autenticado':False,'usuario_actual':None}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k]=v
        
try:    favicon=Image.open(BASE_DIR / "logo" / "alcot_logo.png")
except: favicon="🖥️"
st.set_page_config(page_title=APP_NAME, page_icon="alcot_logo.png", layout="wide", initial_sidebar_state="expanded")

# ============================================================================
# CSS — colores del logo (#0d1b2a fondo, #7fff00 lima, #39d353 verde)
# ============================================================================
st.markdown("""
<style>
:root{
    --bg-dark:   #0d1b2a;
    --lima:      #7fff00;
    --verde:     #39d353;
    --verde-dim: #2aad3e;
    --texto:     #e8f5e9;
}

/* ── Header ── */
header[data-testid="stHeader"]{
    background-color: var(--bg-dark) !important;
    border-bottom: 3px solid var(--lima) !important;
}
header::after{display:none !important;}

/* ── Sidebar ── */
section[data-testid="stSidebar"]{
    background-color: var(--bg-dark) !important;
    border-right: 2px solid var(--verde) !important;
    padding-top: 1rem;
}
section[data-testid="stSidebar"]>div,
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{
    background-color: var(--bg-dark) !important;
}
section[data-testid="stSidebar"] *,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3{
    color: var(--texto) !important; font-size:15px;
}
section[data-testid="stSidebar"] .stButton>button,
section[data-testid="stSidebar"] button{
    background-color: rgba(127,255,0,0.12) !important;
    color: var(--lima) !important;
    border: 1px solid rgba(127,255,0,0.4) !important;
    border-radius: 6px !important;
    font-size: 13px !important;
    width: 100% !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] .stButton>button:hover,
section[data-testid="stSidebar"] button:hover{
    background-color: rgba(127,255,0,0.25) !important;
}
section[data-testid="stSidebar"] button p{color: var(--lima) !important; font-size:13px !important;}

/* Nav links */
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]{
    background-color: transparent !important;
    border-radius: 6px !important;
    padding: 0.4rem 0.6rem !important;
    transition: background 0.2s;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover{
    background-color: rgba(127,255,0,0.12) !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"]{
    background-color: rgba(57,211,83,0.2) !important;
    border-left: 3px solid var(--lima) !important;
    font-weight: 700 !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span,
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] p{
    color: var(--texto) !important;
}
section[data-testid="stSidebar"] nav>div>p{
    color: rgba(127,255,0,0.55) !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600 !important;
}

/* ── Main content ── */
.main{padding:2rem; background-color:#f4fff4;}
.main .stButton>button{
    background-color: var(--bg-dark);
    color: var(--lima);
    border: 1px solid var(--verde);
    border-radius: 6px;
    padding: 0.5rem 1rem;
    font-weight: 600;
    width: 100%;
}
.main .stButton>button:hover{
    background-color: var(--verde-dim);
    color: #ffffff;
}

/* Métricas */
[data-testid="stMetric"]{
    background: var(--bg-dark);
    border-radius: 10px;
    padding: 1rem;
    border: 1px solid var(--verde);
}
[data-testid="stMetricLabel"]{color: var(--texto) !important;}
[data-testid="stMetricValue"]{color: var(--lima) !important; font-weight:900 !important;}

/* Tabs */
[data-testid="stTabs"] [data-testid="stTab"]{
    color: var(--bg-dark) !important;
    font-weight: 600;
}
[data-testid="stTabs"] [aria-selected="true"]{
    border-bottom: 3px solid var(--lima) !important;
    color: var(--bg-dark) !important;
}

input,textarea{border-radius:6px !important;}
footer{visibility:hidden;}

/* Login */
.login-box{
    max-width:420px; margin:3rem auto; padding:2.5rem 2rem;
    background:#0d1b2a; border-radius:12px;
    box-shadow:0 4px 32px rgba(127,255,0,0.15);
    border-top:5px solid #7fff00;
}
.login-box label, .login-box p, .login-box span{color:#e8f5e9 !important;}

/* Revision card */
.revision-card{
    background: var(--bg-dark);
    border: 1px solid rgba(57,211,83,0.4);
    border-left: 4px solid var(--lima);
    border-radius: 8px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.5rem;
}
.revision-nombre{font-weight:700; color:var(--lima); font-size:1rem;}
.revision-meta{font-size:0.8rem; color:rgba(255,255,255,0.55); margin-top:0.2rem;}
</style>
""", unsafe_allow_html=True)

# ============================================================================
# LOGIN
# ============================================================================
def mostrar_login():
    st.markdown("""<style>
    section[data-testid="stSidebar"]{display:none !important;}
    [data-testid="collapsedControl"]{display:none !important;}
    body, .main{background-color:#0d1b2a !important;}
    </style>""", unsafe_allow_html=True)

    _,col_c,_=st.columns([1,2,1])
    with col_c:
        st.markdown(LOGO_SVG, unsafe_allow_html=True)

    _,col_c,_=st.columns([1,1.4,1])
    with col_c:
        st.markdown('<div class="login-box">',unsafe_allow_html=True)
        st.markdown("<h3 style='text-align:center;color:#7fff00;font-family:Arial Black;'>🔐 Acceso al Sistema</h3>",unsafe_allow_html=True)
        st.markdown(f"<p style='text-align:center;color:#39d353;font-size:0.9rem;font-weight:700;'>{APP_NAME}</p>",unsafe_allow_html=True)
        username=st.text_input("👤 Usuario",placeholder="Introduce tu usuario",key="login_user")
        password=st.text_input("🔑 Contraseña",type="password",placeholder="Introduce tu contraseña",key="login_pass")
        if st.button("Entrar →",type="primary",use_container_width=True):
            if not username.strip(): st.error("Introduce tu usuario.")
            elif not password: st.error("Introduce tu contraseña.")
            elif verificar_credenciales(username.strip(),password):
                st.session_state.autenticado=True; st.session_state.usuario_actual=username.strip(); st.rerun()
            else: st.error("❌ Usuario o contraseña incorrectos.")
        st.markdown('</div>',unsafe_allow_html=True)

if not st.session_state.autenticado:
    mostrar_login(); st.stop()

# ============================================================================
# BANNER (logo en cabecera de cada página)
# ============================================================================
def _banner():
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        st.markdown(f'<div style="max-width:180px">{LOGO_SVG}</div>', unsafe_allow_html=True)
    with col_titulo:
        st.markdown(f"""
        <div style="padding-left:1rem;padding-top:0.5rem;">
            <span style="font-family:Arial Black;font-size:2rem;font-weight:900;color:#0d1b2a;letter-spacing:2px;">{APP_NAME}</span><br>
            <span style="font-size:0.85rem;color:#39d353;font-weight:600;">Gestión de Inventario</span>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("<hr style='border:1.5px solid #39d353;margin-top:0.5rem;margin-bottom:1.5rem;'>", unsafe_allow_html=True)

# ============================================================================
# REVISIONES — helpers
# ============================================================================
def _nombre_revision_por_defecto(): return dt.now().strftime("%H:%M - %d/%m/%Y")
def _slug(nombre): return re.sub(r'[<>:"/\\|?*\s]','_',nombre.strip())

def listar_revisiones():
    return sorted([r for r in CARPETA_REVISIONES.iterdir() if r.is_dir()],key=lambda r:r.stat().st_mtime,reverse=True)

def crear_revision(nombre,archivos):
    slug=_slug(nombre); carpeta=CARPETA_REVISIONES/slug; carpeta.mkdir(exist_ok=True)
    meta={"nombre":nombre,"creada":dt.now().strftime("%H:%M - %d/%m/%Y")}
    with open(carpeta/"_meta.json","w",encoding="utf-8") as f: json.dump(meta,f,ensure_ascii=False)
    xlsx_bytes_list=[]
    for nom_arch,contenido in archivos:
        with open(carpeta/nom_arch,"wb") as f: f.write(contenido)
        if nom_arch.lower().endswith(".xlsx"):
            xlsx_bytes_list.append(contenido)
    if xlsx_bytes_list:
        conn=get_db()
        try:
            _importar_xlsx_a_bd(conn,xlsx_bytes_list[-1],"revision",limpiar=True)
            conn.execute("INSERT OR IGNORE INTO demo_loaded (id) VALUES (1)")
            conn.commit(); _sync_stock(conn)
        except Exception as e: print(f"Auto-import error: {e}")
        finally: conn.close()
    return carpeta

def leer_meta(carpeta):
    mf=carpeta/"_meta.json"
    if mf.exists():
        try:
            with open(mf,"r",encoding="utf-8") as f: return json.load(f)
        except: pass
    mtime=dt.fromtimestamp(carpeta.stat().st_mtime)
    return {"nombre":carpeta.name.replace("_"," "),"creada":mtime.strftime("%H:%M - %d/%m/%Y")}

def archivos_de_revision(carpeta):
    return [p for p in sorted(carpeta.iterdir()) if p.suffix.lower() in (".pdf",".csv",".xlsx") and p.name!="_meta.json"]

def eliminar_revision(carpeta):
    shutil.rmtree(carpeta)
    conn=get_db()
    try:
        for tabla in ["articles","clients","providers","stock_entries","stock_exits","demo_loaded"]:
            conn.execute(f"DELETE FROM {tabla}")
        conn.commit()
    except Exception as e: print(f"Error limpiando BD: {e}")
    finally: conn.close()
    _clear_cache()

def renombrar_revision(carpeta,nuevo_nombre):
    meta_vieja=leer_meta(carpeta); nueva=CARPETA_REVISIONES/_slug(nuevo_nombre)
    carpeta.rename(nueva)
    with open(nueva/"_meta.json","w",encoding="utf-8") as f:
        json.dump({"nombre":nuevo_nombre,"creada":meta_vieja.get("creada","")},f,ensure_ascii=False)
    return nueva

# ============================================================================
# BASE DE DATOS
# ============================================================================
def get_db():
    conn=sqlite3.connect(DB_FILE,check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON"); conn.row_factory=sqlite3.Row; return conn

def init_db():
    conn=get_db(); c=conn.cursor()
    for sql in [
        "CREATE TABLE IF NOT EXISTS articles (code TEXT PRIMARY KEY,name TEXT,type TEXT,initial_stock INTEGER DEFAULT 0,entries INTEGER DEFAULT 0,exits INTEGER DEFAULT 0,current_stock INTEGER DEFAULT 0,created_by TEXT)",
        "CREATE TABLE IF NOT EXISTS clients (code TEXT PRIMARY KEY,fiscal_name TEXT,name TEXT,surname TEXT,nif TEXT,phone TEXT,email TEXT,address TEXT,city TEXT,province TEXT,zip_code TEXT)",
        "CREATE TABLE IF NOT EXISTS providers (code TEXT PRIMARY KEY,fiscal_name TEXT,name TEXT,surname TEXT,nif TEXT,phone TEXT,email TEXT,address TEXT,city TEXT,province TEXT,zip_code TEXT)",
        "CREATE TABLE IF NOT EXISTS stock_entries (id INTEGER PRIMARY KEY AUTOINCREMENT,entry_code TEXT,date TEXT,provider_code TEXT,provider_name TEXT,article_code TEXT,article_name TEXT,quantity INTEGER,last_modified_by TEXT)",
        "CREATE TABLE IF NOT EXISTS stock_exits (id INTEGER PRIMARY KEY AUTOINCREMENT,exit_code TEXT,date TEXT,client_code TEXT,client_name TEXT,article_code TEXT,article_name TEXT,quantity INTEGER,price REAL,delivered_to TEXT,last_modified_by TEXT)",
        "CREATE TABLE IF NOT EXISTS demo_loaded (id INTEGER PRIMARY KEY)",
    ]: c.execute(sql)
    conn.commit(); _load_demo(conn); conn.close()

def _nh(c):
    s=str(c).strip().lower()
    for a,b in (("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")): s=s.replace(a,b)
    return s

def _sc(val):
    if val is None: return ""
    try:
        if pd.isna(val): return ""
    except: pass
    s=str(val).strip()
    if s in ("nan",""): return ""
    if s.endswith(".0"): return s[:-2]
    return s

def _ff(val):
    try: return float(val)
    except: return 0.0

def _fd(val):
    if val is None: return ""
    try:
        if isinstance(val,float) and pd.isna(val): return ""
    except: pass
    try:
        ts=pd.to_datetime(val,errors='coerce',dayfirst=True)
        return ts.strftime("%d-%m-%Y") if pd.notna(ts) else str(val)
    except: return str(val)

def _classify(code):
    s=str(code).strip()
    try:
        parts=s.split('.')
        if len(parts)==2 and parts[0]=='1':
            m=int(parts[1])
            if m<=12 or 81<=m<=82 or 101<=m<=106: return "Almacenamiento"
            if 13<=m<=27: return "Conectores/Adaptadores"
            if (28<=m<=40) or (45<=m<=48) or (112<=m<=114): return "Cables"
            if (41<=m<=44) or (51<=m<=57) or (109<=m<=111): return "Energía"
            if 49<=m<=50: return "Redes"
            if (58<=m<=66) or (75<=m<=80) or (83<=m<=100): return "Periféricos"
    except: pass
    return "Otros"

def _group(code, name=""):
    nm = str(name).lower().strip()
    if any(k in nm for k in ("memoria ram","memoria usb","pendrive","pen drive","tarjeta sd","sd card")):
        return "Memorias"
    if any(k in nm for k in ("disco duro","ssd","hdd","nvme","disco sólido","disco solido")):
        return "Discos duros"
    if any(k in nm for k in ("adaptador","conversor","convertidor","hub usb","dock","docking")):
        return "Adaptadores"
    if any(k in nm for k in ("cable","latigillo","latiguillo","cordón","cordon","hdmi","vga","displayport")):
        return "Cables"
    if any(k in nm for k in ("cargador","fuente de alimentacion","fuente de alimentación","bateria","batería","sai","ups","regleta","alargador","enchufe")):
        return "Energía"
    if any(k in nm for k in ("raton","ratón","mouse","teclado","keyboard","auricular","auriculares","headset","cascos","webcam","camara","cámara","microfono","micrófono","monitor","pantalla","display","impresora","escaner","escáner","scanner","altavoz","altavoces","speakers")):
        return "Periféricos"
    if any(k in nm for k in ("switch","router","access point","punto de acceso","wifi","ethernet","patch panel","rack")):
        return "Switch"
    cat=_classify(code)
    MAP={"Almacenamiento":"Discos duros","Conectores/Adaptadores":"Adaptadores","Cables":"Cables","Energía":"Energía","Redes":"Switch","Periféricos":"Periféricos"}
    return MAP.get(cat,"Otros")

def _natural_key(s): return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)',str(s))]

def _sort_nat(df,col):
    try:
        df['_sk']=df[col].apply(_natural_key); df=df.sort_values('_sk').drop('_sk',axis=1)
    except: pass
    return df

def _fmt_mixed(code,name):
    s=_sc(code)
    if not s or s in ("0","0.0"): return ""
    try: return f"{int(float(s))} / {name}" if float(s).is_integer() else f"{s} / {name}"
    except: return f"{s} / {name}"

def _to_excel(df):
    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine='openpyxl') as w: df.to_excel(w,index=False,sheet_name='Datos')
    return buf.getvalue()

def _sync_stock(conn):
    conn.execute("UPDATE articles SET entries=(SELECT COALESCE(SUM(quantity),0) FROM stock_entries WHERE stock_entries.article_code=articles.code)")
    conn.execute("UPDATE articles SET exits=(SELECT COALESCE(SUM(quantity),0) FROM stock_exits WHERE stock_exits.article_code=articles.code)")
    conn.execute("UPDATE articles SET current_stock=initial_stock+entries-exits")
    conn.commit()

def _clear_cache(): st.cache_data.clear()

def _load_base(conn):
    df_arts=pd.read_sql("SELECT code,name,type,initial_stock,entries,exits,current_stock,created_by FROM articles",conn)
    df_provs=pd.read_sql("SELECT code,fiscal_name,phone,email,city FROM providers",conn)
    df_profs=pd.read_sql("SELECT code,fiscal_name,name,surname,phone,email,city FROM clients",conn)
    for df in [df_arts,df_provs,df_profs]: df['code']=df['code'].apply(_sc)
    df_arts=_sort_nat(df_arts,'code'); df_provs=_sort_nat(df_provs,'code'); df_profs=_sort_nat(df_profs,'code')
    df_arts['display_full']=df_arts.apply(lambda r:_fmt_mixed(r['code'],r['name']),axis=1)
    df_provs['display_full']=df_provs.apply(lambda r:_fmt_mixed(r['code'],r['fiscal_name']),axis=1)
    df_profs['display_full']=df_profs.apply(lambda r:_fmt_mixed(r['code'],r['fiscal_name']),axis=1)
    return df_arts,df_provs,df_profs

def _load_demo(conn):
    if conn.execute("SELECT COUNT(*) FROM demo_loaded").fetchone()[0]>0: return
    demo=BASE_DIR/"Almacén_PEMA_Jaén.xlsx"
    if not demo.exists(): return
    try:
        _importar_xlsx_a_bd(conn,demo.read_bytes(),"demo")
        conn.execute("INSERT INTO demo_loaded (id) VALUES (1)"); conn.commit()
    except Exception as e: print(f"Demo load error: {e}")

# ============================================================================
# IMPORTACIÓN XLSX CENTRALIZADA
# ============================================================================
def _importar_xlsx_a_bd(conn, xlsx_bytes, fuente="import", limpiar=False):
    if limpiar:
        for tabla in ["articles","clients","providers","stock_entries","stock_exits","demo_loaded"]:
            conn.execute(f"DELETE FROM {tabla}")
        conn.commit()
    xls=pd.read_excel(io.BytesIO(xlsx_bytes),sheet_name=None)
    results={"Artículos":0,"Profesores":0,"Proveedores":0,"Entradas":0,"Salidas":0}
    sn=next((s for s in xls if "existencia" in s.lower()),None)
    if sn:
        df=xls[sn]; df.columns=[_nh(c) for c in df.columns]
        for _,row in df.iterrows():
            code=_sc(row.get("codigo",""))
            if not code: continue
            ini=_ff(row.get("existencias iniciales",0)); ent=_ff(row.get("entradas",0)); sal=_ff(row.get("salidas",0))
            nombre=row.get("nombre del articulo","")
            try:
                conn.execute("INSERT OR REPLACE INTO articles (code,name,type,initial_stock,entries,exits,current_stock) VALUES (?,?,?,?,?,?,?)",(code,nombre,_classify(code),ini,ent,sal,ini+ent-sal))
                results["Artículos"]+=1
            except: pass
    sn=next((s for s in xls if "profesor" in s.lower() or "cliente" in s.lower()),None)
    if sn:
        df=xls[sn]; df.columns=[_nh(c) for c in df.columns]
        for _,row in df.iterrows():
            code=_sc(row.get("codigo",""))
            if not code: continue
            try:
                conn.execute("INSERT OR REPLACE INTO clients (code,fiscal_name,name,surname,nif,phone,email,address,city,province,zip_code) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (code,row.get("nombre fiscal"),row.get("nombre"),row.get("apellidos"),row.get("nif/cif"),row.get("telefono"),row.get("e-mail"),row.get("direccion"),row.get("poblacion"),row.get("provincia"),_sc(row.get("codigo postal",""))))
                results["Profesores"]+=1
            except: pass
    sn=next((s for s in xls if "proveedor" in s.lower()),None)
    if sn:
        df=xls[sn]; df.columns=[_nh(c) for c in df.columns]
        for _,row in df.iterrows():
            code=_sc(row.get("codigo",""))
            if not code: continue
            try:
                conn.execute("INSERT OR REPLACE INTO providers (code,fiscal_name,name,surname,nif,phone,email,address,city,province,zip_code) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (code,row.get("nombre fiscal"),row.get("nombre"),row.get("apellidos"),row.get("nif/cif"),row.get("telefono"),row.get("e-mail"),row.get("direccion"),row.get("poblacion"),row.get("provincia"),_sc(row.get("codigo postal",""))))
                results["Proveedores"]+=1
            except: pass
    sn=next((s for s in xls if "entrada" in s.lower()),None)
    if sn:
        df=xls[sn]; df.columns=[_nh(c) for c in df.columns]
        for _,row in df.iterrows():
            code=_sc(row.get("codigo",""))
            if not code: continue
            try:
                conn.execute("INSERT OR IGNORE INTO stock_entries (entry_code,date,provider_code,provider_name,article_code,article_name,quantity,last_modified_by) VALUES (?,?,?,?,?,?,?,?)",
                    (code,_fd(row.get("fecha")),_sc(row.get("proveedor (codigo)","")),row.get("proveedor (nombre)"),_sc(row.get("articulo (codigo)","")),row.get("articulo (nombre)"),_ff(row.get("cantidad",0)),fuente))
                results["Entradas"]+=1
            except: pass
    sn=next((s for s in xls if "salida" in s.lower()),None)
    if sn:
        df=xls[sn]; df.columns=[_nh(c) for c in df.columns]
        for _,row in df.iterrows():
            code=_sc(row.get("codigo",""))
            if not code: continue
            try:
                conn.execute("INSERT OR IGNORE INTO stock_exits (exit_code,date,client_code,client_name,article_code,article_name,quantity,price,delivered_to,last_modified_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (code,_fd(row.get("fecha")),_sc(row.get("profesor (codigo)","")),row.get("profesor (nombre)"),_sc(row.get("articulo (codigo)","")),row.get("articulo (nombre)"),_ff(row.get("cantidad",0)),row.get("precio"),row.get("entregado a"),fuente))
                results["Salidas"]+=1
            except: pass
    conn.commit()
    return results

# ============================================================================
# FUNCIONES RPT
# ============================================================================
def es_linea_plaza(linea):
    if ',' in linea and re.search(r'\d{8}[A-Z]\d+[A-Z].*,',linea): return False
    if re.match(r'^\s*\d?\s*\d{4,8}\s*[A-ZÁÉÍÓÚÑ]',linea):
        if not re.match(r'^\s*\d{6,8}[A-Z]\d+[A-Z]+\d+',linea): return True
    return False

def es_linea_persona(linea):
    if re.match(r'^\s*\d{8}[A-Z]\d+[A-Z]+\d+[A-ZÁÉÍÓÚÑÜ\s\.\-ªº]+,\s*[A-ZÁÉÍÓÚÑÜ]',linea): return True
    if re.match(r'^\s*\d{8}[A-Z]\d+L\d+[A-ZÁÉÍÓÚÑÜ\s\.\-ªº]+,\s*[A-ZÁÉÍÓÚÑÜ]',linea): return True
    return False

def extraer_codigo_puesto(linea):
    m=re.search(r'(\d{4,8})',linea); return m.group(1) if m else None

def extraer_denominacion(linea):
    mc=re.search(r'\d{4,8}',linea)
    if not mc: return None
    resto=linea[mc.end():]
    m=re.match(r'\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s\.\/\(\)ºª\-]+?)(?:\.{2,}|\s+[A-E]\d|\s+\d+\s+\d+)',resto)
    if m:
        d=re.sub(r'\.+$','',m.group(1).strip()).strip()
        return d if len(d)>2 else None
    return None

def extraer_grupo(linea):
    for pat in [r'\s+([A-E]\d(?:-[A-E]\d)?)\s+P-[A-E]\d',r'\s+([A-E]\d(?:-[A-E]\d)?)P-[A-E]\d',r'\s+([IVX]+)\s+[A-Z]']:
        m=re.search(pat,linea)
        if m: return m.group(1)
    return None

def extraer_cuerpo(linea):
    m=re.search(r'(P-[A-E]\d+)[\s\w]',linea)
    if m: return m.group(1)
    m=re.search(r'[IVX]+\s+([A-ZÁÉÍÓÚÑ\s\.]+?)\s+\d{2}\s+',linea)
    if m:
        c=' '.join(m.group(1).strip().split())
        return c if len(c)>3 else None
    return None

def extraer_nombre_persona(linea):
    m=re.search(r'\d{8}[A-Z]\d+[A-Z]+\d+([A-ZÁÉÍÓÚÑÜ\s,\.\-ªº]+?)(?:\s+[A-E]\d|\s+FUNC\.|LABORAL|[A-E]\d+\s)',linea)
    if m:
        nombre=' '.join(m.group(1).strip().split())
        if len(nombre)>5 and ',' in nombre: return nombre
    return None

def extraer_formacion(linea):
    if 'PROVISIONAL' in linea.upper(): return 'PROVISIONAL'
    elif 'DEFINITIVO' in linea.upper(): return 'DEFINITIVO'
    return None

def extraer_dni(linea):
    m=re.search(r'(\d{8}[A-Z])',linea); return m.group(1) if m else None

def extraer_ads(linea):
    if re.search(r'\b1F\s',linea): return 'F'
    if re.search(r'\b1L\s',linea): return 'L'
    return None

def extraer_modo_acceso(linea):
    m=re.search(r'1F\s+([A-Z]{2,3}(?:,\w+)?|[A-Z]\.\d+,?/?\d*|/\d+,[A-Z]\.\d+)\s+(?:AX\s+)?[A-E]\d',linea)
    if m:
        modo=m.group(1).strip()
        if modo in ('PC','PLD','PCE'): return modo
        elif modo.startswith('RD'): return 'RD (Art.7.1.A)'
        elif modo.startswith('D.') or modo.startswith('/'): return 'DTO 2/2002'
        return modo
    m=re.search(r'1F\s+(PLD)\s+AX\s+[A-E]\d',linea)
    if m: return 'PLD'
    m=re.search(r'1L\s+([A-Z]{1,3}(?:,\w+)?)\s+[IVX]+\s',linea)
    if m:
        modo=m.group(1).strip()
        return 'PC,S' if modo=='S,PC' else modo
    return None

LOCALIDAD_A_PROVINCIA={
    'ALMERIA':'ALMERÍA','MOJONERA (LA)':'ALMERÍA','ALGECIRAS':'CÁDIZ','CADIZ':'CÁDIZ',
    'CHIPIONA':'CÁDIZ','JEREZ DE LA FRONTERA':'CÁDIZ','PUERTO DE SANTA MARI':'CÁDIZ',
    'SANLUCAR DE BARRAMED':'CÁDIZ','CABRA':'CÓRDOBA','CORDOBA':'CÓRDOBA',
    'HINOJOSA DEL DUQUE':'CÓRDOBA','PALMA DEL RIO':'CÓRDOBA','ARMILLA':'GRANADA',
    'GRANADA':'GRANADA','MOTRIL':'GRANADA','CARTAYA':'HUELVA','HUELVA':'HUELVA',
    'JAEN':'JAÉN','MENGIBAR':'JAÉN','CAMPANILLAS':'MÁLAGA','CHURRIANA':'MÁLAGA',
    'MALAGA':'MÁLAGA','ALCALA DEL RIO':'SEVILLA','AZNALCAZAR':'SEVILLA',
    'PALACIOS Y VILLAFRAN':'SEVILLA','SEVILLA':'SEVILLA',
}
LOCALIDADES_INVALIDAS={'DPL. INFORMATICA INFORMATICA SEVILLA','GRDO/A EN ING SEVILLA','INFORMATICA MALAGA','INFORMATICA SEVILLA','INGENIERO EN SEVILLA','INGENIERO SEVILLA'}

def extraer_localidad(linea):
    m=re.search(r'[\d\.]+,\d{2}\s+(?:\d+\s+)?([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s\.\/\-\(\)]+?)\s*$',linea)
    if m:
        loc=m.group(1).strip().upper()
        if len(loc)>=3 and loc not in LOCALIDADES_INVALIDAS: return loc
        if loc in LOCALIDADES_INVALIDAS:
            partes=loc.split()
            for n in range(1,min(4,len(partes))):
                cand=' '.join(partes[-n:])
                if cand in LOCALIDAD_A_PROVINCIA: return cand
    return "NO ESPECIFICADA"

def extraer_dotacion(linea):
    if "NO DOTADA" in linea.upper(): return "NO DOTADA"
    for pat in [r'\.+\s+(\d+)\s+(\d+)\s',r'\.+\s+(\d+)\s+(\d+)\s+[A-E]\d',r'\s(\d+)\s+(\d+)\s+[A-E]\d(?:-[A-E]\d)?(?:\s|P-)',r'\s(\d+)\s+(\d+)\s+[IVX]+\s']:
        m=re.search(pat,linea)
        if m: return "NO DOTADA" if m.group(2)=='0' else "DOTADA"
    partes=linea.split()
    if len(partes)>2 and (partes[-1]=='N' or partes[-2]=='N'): return "NO DOTADA"
    return "NO DOTADA"

def procesar_pdf(archivo_bytes,nombre_archivo):
    registros=[]
    try:
        with pdfplumber.open(io.BytesIO(archivo_bytes)) as pdf:
            num_pag=len(pdf.pages); todas_lineas=[]; paginas_sin_texto=[]
            with st.spinner(f'📄 Procesando {nombre_archivo} ({num_pag} páginas)...'):
                for np_idx,pagina in enumerate(pdf.pages,1):
                    try:
                        texto=pagina.extract_text()
                        if texto: todas_lineas.extend(texto.split('\n'))
                        else: paginas_sin_texto.append(np_idx)
                    except: pass
                if paginas_sin_texto: st.warning(f"⚠️ {len(paginas_sin_texto)} páginas sin texto")
                st.info(f"✅ {nombre_archivo}: {len(todas_lineas):,} líneas extraídas")
            i=0
            while i<len(todas_lineas):
                linea=todas_lineas[i]
                if es_linea_plaza(linea):
                    codigo=extraer_codigo_puesto(linea)
                    if not codigo: i+=1; continue
                    nombre_ocupante=dni_ocupante=formacion_ocupante=None
                    for j in range(1,6):
                        if (i+j)<len(todas_lineas):
                            sig=todas_lineas[i+j]
                            if es_linea_persona(sig):
                                nombre_ocupante=extraer_nombre_persona(sig); dni_ocupante=extraer_dni(sig); formacion_ocupante=extraer_formacion(sig)
                                if formacion_ocupante is None:
                                    for k in range(1,4):
                                        if (i+j+k)<len(todas_lineas):
                                            sig2=todas_lineas[i+j+k]
                                            if es_linea_plaza(sig2) or es_linea_persona(sig2): break
                                            formacion_ocupante=extraer_formacion(sig2)
                                            if formacion_ocupante: break
                                break
                            if es_linea_plaza(sig): break
                    _loc=extraer_localidad(linea)
                    registros.append({'Código':codigo,'Denominación':extraer_denominacion(linea),'Grupo':extraer_grupo(linea),'Cuerpo':extraer_cuerpo(linea),
                        'Provincia':LOCALIDAD_A_PROVINCIA.get(_loc,"NO ESPECIFICADA"),'Localidad':_loc,'Dotación':extraer_dotacion(linea),
                        'ADS':extraer_ads(linea),'Modo_Acceso':extraer_modo_acceso(linea),
                        'Ocupante':nombre_ocupante if nombre_ocupante else 'LIBRE',
                        'Estado_Plaza':'OCUPADA' if nombre_ocupante else 'VACANTE','DNI':dni_ocupante,'Carácter':formacion_ocupante})
                i+=1
        df=pd.DataFrame(registros)
        if df.empty: st.error(f"❌ {nombre_archivo}: sin plazas."); return pd.DataFrame()
        df_oc=df[df['Estado_Plaza']=='OCUPADA'].copy()
        if not df_oc.empty and 'DNI' in df_oc.columns:
            df_oc['_cp']=df_oc['DNI'].fillna('')+'|'+df_oc['Ocupante']
            dups=df_oc[df_oc.duplicated(subset=['_cp'],keep=False)]
            if not dups.empty:
                for persona in dups['_cp'].unique():
                    if '|' not in persona or persona.startswith('|'): continue
                    rp=df_oc[df_oc['_cp']==persona]
                    if 'PROVISIONAL' in rp['Carácter'].values:
                        nombre_func=persona.split('|',1)[1]
                        for cod in rp[rp['Carácter']=='DEFINITIVO']['Código'].tolist():
                            df.loc[df['Código']==cod,'Estado_Plaza']='VACANTE'
                            df.loc[df['Código']==cod,'Ocupante']=f'({nombre_func})'
        df=df.drop_duplicates(subset=['Código'])
        st.success(f"✅ {nombre_archivo}: {len(df):,} plazas únicas")
        return df
    except Exception as e:
        st.error(f"❌ Error: {e}")
        with st.expander("🔍 Detalles"): st.code(traceback.format_exc())
        return pd.DataFrame()

# ============================================================================
# PÁGINAS 1-4
# ============================================================================
def pagina_existencias():
    _banner(); st.title("📦 Existencias")
    conn=get_db(); df_arts,_,_=_load_base(conn)
    total_art=len(df_arts); total_stock=int(df_arts['current_stock'].sum()); sin_stock=len(df_arts[df_arts['current_stock']<=0])
    m1,m2,m3=st.columns(3)
    m1.metric("Total artículos",total_art); m2.metric("Unidades en stock",total_stock); m3.metric("Sin stock",sin_stock)
    st.markdown("---")
    fc1,fc2,fc3=st.columns(3)
    tipos_disp=sorted([t for t in df_arts['type'].dropna().unique() if t])
    with fc1: f_tipo=st.multiselect("📂 Categoría",options=tipos_disp,key="ex_ftipo")
    with fc2: f_stock=st.multiselect("📊 Stock",options=["Con stock","Sin stock"],key="ex_fest")
    with fc3: f_texto=st.text_input("🔍 Buscar",placeholder="Código o nombre…",key="ex_ftxt")
    df_view=df_arts.copy()
    if f_tipo: df_view=df_view[df_view['type'].isin(f_tipo)]
    if "Con stock" in f_stock: df_view=df_view[df_view['current_stock']>0]
    if "Sin stock" in f_stock: df_view=df_view[df_view['current_stock']<=0]
    if f_texto.strip():
        q=f_texto.strip().lower()
        df_view=df_view[df_view['code'].str.lower().str.contains(q,na=False)|df_view['name'].str.lower().str.contains(q,na=False)]
    st.caption(f"Mostrando **{len(df_view)}** de **{total_art}** artículos")
    if not df_view.empty:
        try:
            import plotly.express as px
            df_c=df_view.groupby('type')['current_stock'].sum().reset_index(); df_c.columns=['Categoría','Unidades']; df_c=df_c[df_c['Unidades']>0]
            if not df_c.empty:
                fig=px.bar(df_c,x='Categoría',y='Unidades',color='Categoría',height=300,
                    color_discrete_sequence=['#7fff00','#39d353','#2aad3e','#0d5c2e','#a8ff47','#57e86b','#1a8c3a','#b2ff59'])
                fig.update_layout(showlegend=False,plot_bgcolor='#f4fff4',paper_bgcolor='#f4fff4',margin=dict(l=10,r=10,t=30,b=40))
                st.plotly_chart(fig,use_container_width=True)
        except ImportError:
            st.bar_chart(df_view.groupby('type')['current_stock'].sum())
    st.markdown("---")
    for col in ['initial_stock','entries','exits','current_stock']:
        df_view[col]=pd.to_numeric(df_view[col],errors='coerce').fillna(0)
    df_view.insert(0,"Sel",False)
    edited=st.data_editor(df_view,num_rows="dynamic",key="ed_art",column_config={
        "Sel":st.column_config.CheckboxColumn("✅",width="small"),"display_full":None,
        "code":st.column_config.TextColumn("Código",disabled=True),"name":st.column_config.TextColumn("Artículo",disabled=True),
        "type":st.column_config.TextColumn("Tipo",disabled=True),"initial_stock":st.column_config.NumberColumn("Inicial"),
        "entries":st.column_config.NumberColumn("Entradas",disabled=True),"exits":st.column_config.NumberColumn("Salidas",disabled=True),
        "current_stock":st.column_config.NumberColumn("Actual",disabled=True),"created_by":None,
    },use_container_width=True)
    cb1,cb2,cb3=st.columns(3)
    with cb1:
        if st.button("💾 Guardar cambios",key="save_art",type="primary"):
            try:
                for _,row in edited.iterrows():
                    if row['code']: conn.execute("UPDATE articles SET initial_stock=? WHERE code=?",(row['initial_stock'],row['code']))
                conn.commit(); _sync_stock(conn); st.success("✅ Guardado."); _clear_cache(); time.sleep(0.4); st.rerun()
            except Exception as e: st.error(f"Error: {e}")
    with cb2:
        if st.button("🗑️ Eliminar seleccionados",key="del_art"):
            ids=edited[edited["Sel"]==True]["code"].tolist()
            if ids:
                for c in ids: conn.execute("DELETE FROM articles WHERE code=?",(c,))
                conn.commit(); st.success(f"🗑️ {len(ids)} eliminado(s)."); _clear_cache(); time.sleep(0.4); st.rerun()
            else: st.warning("Selecciona al menos un artículo.")
    with cb3:
        if not df_view.empty:
            cols_ex=[c for c in df_view.columns if c not in ("Sel","display_full")]
            st.download_button("📥 Exportar Excel",data=_to_excel(df_view[cols_ex]),file_name="existencias.xlsx",mime="application/vnd.ms-excel",key="exp_art")
    conn.close()

def pagina_productos():
    _banner(); st.title("🗂️ Productos")
    conn=get_db(); df_arts,_,_=_load_base(conn); current_user=st.session_state.usuario_actual or "usuario"
    with st.expander("➕ Añadir Nuevo Producto",expanded=False):
        ca1,ca2,ca3=st.columns(3)
        n_code=ca1.text_input("Código Nuevo",key="prod_code"); n_name=ca2.text_input("Nombre Nuevo",key="prod_name")
        n_type=ca3.selectbox("Grupo",options=list(GROUPS_CONFIG.keys()),key="prod_cat")
        if st.button("Crear Producto",key="btn_crear_prod"):
            if n_code and n_name:
                try:
                    conn.execute("INSERT INTO articles (code,name,type,initial_stock,entries,exits,current_stock,created_by) VALUES (?,?,?,0,0,0,0,?)",(n_code.strip(),n_name,GROUPS_CONFIG[n_type]["cat"],current_user))
                    conn.commit(); st.success("✅ Producto añadido."); _clear_cache(); time.sleep(0.5); st.rerun()
                except Exception: st.error("Error: el código ya existe.")
            else: st.warning("Rellena código y nombre.")
    fpc1,fpc2=st.columns(2)
    with fpc1: filtro_grupo=st.multiselect("📂 Filtrar por Grupo:",options=list(GROUPS_CONFIG.keys()),key="prd_fg")
    with fpc2:
        cats_disp=sorted({t for t in df_arts['type'].dropna() if t})
        filtro_cat=st.multiselect("🏷️ Filtrar por Categoría:",options=cats_disp,key="prd_fc")
    df_all=df_arts.copy(); df_all['type']=df_all['type'].fillna('Otros').replace('','Otros')
    df_all['visual_group']=df_all.apply(lambda r:_group(r['code'],r['name']),axis=1)
    if filtro_grupo: df_all=df_all[df_all['visual_group'].isin(filtro_grupo)]
    if filtro_cat: df_all=df_all[df_all['type'].isin(filtro_cat)]
    for group_name in GROUPS_CONFIG.keys():
        gdf=df_all[df_all['visual_group']==group_name].copy()
        if gdf.empty: continue
        gdf['current_stock']=pd.to_numeric(gdf['current_stock'],errors='coerce').fillna(0)
        with st.expander(f"📂 {group_name} ({len(gdf)})"):
            gdf.insert(0,"Sel",False); sk=re.sub(r'\W+','',group_name)
            edited_grp=st.data_editor(gdf,num_rows="dynamic",key=f"ed_{sk}",column_config={
                "Sel":st.column_config.CheckboxColumn("✅",width="small"),"display_full":None,
                "code":st.column_config.TextColumn("Código",disabled=True),"name":st.column_config.TextColumn("Nombre"),
                "type":st.column_config.SelectboxColumn("Categoría",options=["Almacenamiento","Conectores/Adaptadores","Cables","Energía","Periféricos","Redes","Consumibles","Otros"]),
                "current_stock":st.column_config.NumberColumn("Stock"),"created_by":st.column_config.TextColumn("Creador",disabled=True),
                "entries":None,"exits":None,"visual_group":None,"initial_stock":None,
            },use_container_width=True,hide_index=True)
            cb1g,cb2g=st.columns(2)
            with cb1g:
                if st.button("💾 Guardar",key=f"save_{sk}"):
                    try:
                        for _,row in edited_grp.iterrows():
                            if row['code']:
                                nc=float(row['current_stock'])
                                conn.execute("UPDATE articles SET name=?,type=?,initial_stock=?,current_stock=? WHERE code=?",(row['name'],row['type'],nc-float(row['entries'])+float(row['exits']),nc,row['code']))
                        conn.commit(); st.success("✅ Actualizado."); _clear_cache(); time.sleep(0.5); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
            with cb2g:
                if st.button("🗑️ Eliminar",key=f"del_{sk}"):
                    try:
                        for c in edited_grp[edited_grp["Sel"]==True]["code"].tolist():
                            conn.execute("DELETE FROM articles WHERE code=?",(c,))
                        conn.commit(); st.success("✅ Eliminado."); _clear_cache(); time.sleep(0.5); st.rerun()
                    except: pass
    conn.close()

def pagina_entradas():
    _banner(); st.title("📥 Entradas")
    conn=get_db(); df_arts,df_provs,_=_load_base(conn); current_user=st.session_state.usuario_actual or "usuario"
    list_articles_full=[x for x in df_arts['display_full'] if x]
    list_providers_full=[x for x in df_provs['display_full'] if x]
    df=pd.read_sql("SELECT id,entry_code,date,provider_name,provider_code,article_name,article_code,quantity FROM stock_entries ORDER BY date DESC,id DESC",conn)
    df['date']=pd.to_datetime(df['date'],dayfirst=True,errors='coerce'); df['quantity']=pd.to_numeric(df['quantity'],errors='coerce').fillna(0)
    df['entry_code']=df['entry_code'].apply(_sc)
    df['provider_mixed']=df.apply(lambda x:_fmt_mixed(x['provider_code'],x['provider_name']),axis=1)
    df['article_mixed']=df.apply(lambda x:_fmt_mixed(x['article_code'],x['article_name']),axis=1)
    with st.expander("➕ Añadir Nueva Entrada",expanded=False):
        ce1,ce2,ce3,ce4,ce5=st.columns(5)
        ne_code=ce1.text_input("Cód. Entrada",key="ne_code"); ne_date=ce2.date_input("Fecha",value=datetime.date.today(),key="ne_date")
        ne_prov=ce3.selectbox("Proveedor",[""]+list_providers_full,key="ne_prov")
        ne_art=ce4.selectbox("Artículo",[""]+list_articles_full,key="ne_art")
        ne_qty=ce5.number_input("Cantidad",min_value=1,step=1,key="ne_qty")
        if st.button("Guardar Entrada",key="btn_ent_add"):
            if ne_art and ne_qty>0:
                pc,pn="",""; ac,an="",""
                if ne_prov:
                    pts=ne_prov.split(' / ',1)
                    if len(pts)==2: pc,pn=pts
                if ne_art:
                    pts=ne_art.split(' / ',1)
                    if len(pts)==2: ac,an=pts
                try:
                    conn.execute("INSERT INTO stock_entries (entry_code,date,provider_name,provider_code,article_name,article_code,quantity,last_modified_by) VALUES (?,?,?,?,?,?,?,?)",(ne_code.strip() or None,ne_date.strftime("%d-%m-%Y"),pn,pc,an,ac,ne_qty,current_user))
                    conn.commit(); _sync_stock(conn); st.success("✅ Entrada guardada."); _clear_cache(); time.sleep(0.4); st.rerun()
                except Exception as e: st.error(f"Error: {e}")
            else: st.warning("Selecciona artículo y cantidad.")
    st.markdown("#### 🔎 Filtros")
    ff1,ff2,ff3,ff4=st.columns(4)
    with ff1: fe_date=st.date_input("📅 Rango:",value=[],key="fe_date")
    with ff2: fe_code=st.multiselect("🔢 Código:",options=sorted([c for c in df['entry_code'].unique() if c]),key="fe_cod")
    with ff3: fe_prov=st.multiselect("🏢 Proveedor:",options=sorted([p for p in df['provider_mixed'].unique() if p]),key="fe_prov")
    with ff4: fe_art=st.multiselect("📦 Artículo:",options=sorted([a for a in df['article_mixed'].unique() if a]),key="fe_art")
    dv=df.copy()
    if fe_date and len(fe_date)==2: dv=dv[dv['date'].dt.date.between(fe_date[0],fe_date[1]).fillna(False)]
    elif fe_date and len(fe_date)==1: dv=dv[(dv['date'].dt.date==fe_date[0]).fillna(False)]
    if fe_code: dv=dv[dv['entry_code'].isin(fe_code)]
    if fe_prov: dv=dv[dv['provider_mixed'].isin(fe_prov)]
    if fe_art: dv=dv[dv['article_mixed'].isin(fe_art)]
    st.caption(f"Mostrando **{len(dv)}** entradas")
    map_ent={"entry_code":"Cód.","date":"Fecha","provider_name":"Proveedor","article_code":"Cód.Art.","article_name":"Artículo","quantity":"Cantidad"}
    cx1,cx2=st.columns([3,1])
    with cx1: cs_ent=st.multiselect("📊 Columnas exportar:",options=list(map_ent.values()),default=list(map_ent.values()),key="cs_ent")
    with cx2:
        if cs_ent:
            imap={v:k for k,v in map_ent.items()}; df_ex=dv[[imap[v] for v in cs_ent if v in imap]].copy()
            if 'date' in df_ex.columns: df_ex['date']=df_ex['date'].dt.strftime('%d-%m-%Y')
            df_ex.rename(columns=map_ent,inplace=True)
            st.download_button("📥 Excel",data=_to_excel(df_ex),file_name="entradas.xlsx",mime="application/vnd.ms-excel")
    dv.insert(0,"Sel",False)
    ed_ent=st.data_editor(dv,num_rows="dynamic",key="ed_ent",column_config={
        "Sel":st.column_config.CheckboxColumn("✅",width="small"),"id":{"hidden":True},
        "provider_code":{"hidden":True},"provider_name":{"hidden":True},"article_code":{"hidden":True},"article_name":{"hidden":True},
        "entry_code":st.column_config.TextColumn("Código"),"date":st.column_config.DateColumn("Fecha",format="DD-MM-YYYY"),
        "provider_mixed":st.column_config.SelectboxColumn("Proveedor",options=list_providers_full,width="medium"),
        "article_mixed":st.column_config.SelectboxColumn("Artículo",options=list_articles_full,width="medium"),
        "quantity":st.column_config.NumberColumn("Cant."),
    },use_container_width=True)
    cs1,cs2=st.columns(2)
    with cs1:
        if st.button("💾 Guardar cambios",key="save_ent",type="primary"):
            try:
                for _,row in ed_ent.iterrows():
                    pc,pn="",""; ac,an="",""
                    if row['provider_mixed']:
                        pts=row['provider_mixed'].split(' / ',1)
                        if len(pts)==2: pc,pn=pts
                    if row['article_mixed']:
                        pts=row['article_mixed'].split(' / ',1)
                        if len(pts)==2: ac,an=pts
                    ds=_fd(row['date'])
                    if pd.isna(row['id']):
                        conn.execute("INSERT INTO stock_entries (entry_code,date,provider_name,provider_code,article_name,article_code,quantity,last_modified_by) VALUES (?,?,?,?,?,?,?,?)",(row['entry_code'] or None,ds,pn,pc,an,ac,row['quantity'],current_user))
                    else:
                        conn.execute("UPDATE stock_entries SET entry_code=?,date=?,provider_name=?,provider_code=?,article_name=?,article_code=?,quantity=?,last_modified_by=? WHERE id=?",(row['entry_code'] or None,ds,pn,pc,an,ac,row['quantity'],current_user,row['id']))
                conn.commit(); _sync_stock(conn); st.success("✅ Guardado."); _clear_cache(); time.sleep(0.4); st.rerun()
            except Exception as e: st.error(f"Error: {e}")
    with cs2:
        if st.button("🗑️ Eliminar seleccionados",key="del_ent"):
            try:
                for i in ed_ent[ed_ent["Sel"]==True]["id"].dropna().tolist():
                    conn.execute("DELETE FROM stock_entries WHERE id=?",(i,))
                conn.commit(); _sync_stock(conn); st.success("✅ Eliminado."); _clear_cache(); time.sleep(0.4); st.rerun()
            except: pass
    conn.close()

def pagina_salidas():
    _banner(); st.title("📤 Salidas")
    conn=get_db(); df_arts,_,df_profs=_load_base(conn); current_user=st.session_state.usuario_actual or "usuario"
    list_articles_full=[x for x in df_arts['display_full'] if x]
    list_profs_full=[x for x in df_profs['display_full'] if x]
    list_responsibles=[x for x in df_profs.apply(lambda r:f"{r['name'] or ''} {r['surname'] or ''}".strip(),axis=1).unique() if x]
    prof_resp_map={}
    for _,row in df_profs.iterrows():
        fn=f"{row['name'] or ''} {row['surname'] or ''}".strip()
        if row['fiscal_name'] not in prof_resp_map: prof_resp_map[row['fiscal_name']]=[]
        if fn: prof_resp_map[row['fiscal_name']].append(fn)
    df=pd.read_sql("SELECT id,exit_code,date,client_name,client_code,article_name,article_code,quantity,delivered_to FROM stock_exits",conn)
    df['date']=pd.to_datetime(df['date'],dayfirst=True,errors='coerce'); df['quantity']=pd.to_numeric(df['quantity'],errors='coerce').fillna(0)
    df['exit_code']=df['exit_code'].apply(_sc); df=_sort_nat(df,'exit_code')
    df['prof_mixed']=df.apply(lambda x:_fmt_mixed(x['client_code'],x['client_name']),axis=1)
    df['article_mixed']=df.apply(lambda x:_fmt_mixed(x['article_code'],x['article_name']),axis=1)
    with st.expander("➕ Añadir Nueva Salida",expanded=False):
        cs1n,cs2n,cs3n,cs4n,cs5n,cs6n=st.columns(6)
        ns_code=cs1n.text_input("Cód. Salida",key="ns_code"); ns_date=cs2n.date_input("Fecha",value=datetime.date.today(),key="ns_date")
        ns_prof=cs3n.selectbox("Profesor",[""]+list_profs_full,key="ns_prof")
        ns_art=cs4n.selectbox("Artículo",[""]+list_articles_full,key="ns_art")
        ns_qty=cs5n.number_input("Cantidad",min_value=1,step=1,key="ns_qty")
        ns_resp=cs6n.selectbox("Responsable",[""]+list_responsibles,key="ns_resp")
        if st.button("Guardar Salida",key="btn_sal_add"):
            if ns_art and ns_qty>0:
                cc,cn="",""; ac,an="",""
                if ns_prof:
                    pts=ns_prof.split(' / ',1)
                    if len(pts)==2: cc,cn=pts
                if ns_art:
                    pts=ns_art.split(' / ',1)
                    if len(pts)==2: ac,an=pts
                if not ns_resp and cn:
                    cands=prof_resp_map.get(cn,[])
                    if len(cands)==1: ns_resp=cands[0]
                try:
                    conn.execute("INSERT INTO stock_exits (exit_code,date,client_name,client_code,article_name,article_code,quantity,delivered_to,last_modified_by) VALUES (?,?,?,?,?,?,?,?,?)",(ns_code.strip() or None,ns_date.strftime("%d-%m-%Y"),cn,cc,an,ac,ns_qty,ns_resp,current_user))
                    conn.commit(); _sync_stock(conn); st.success("✅ Salida guardada."); _clear_cache(); time.sleep(0.4); st.rerun()
                except Exception as e: st.error(f"Error: {e}")
            else: st.warning("Selecciona artículo y cantidad.")
    st.markdown("#### 🔎 Filtros")
    sf1,sf2,sf3,sf4,sf5=st.columns(5)
    with sf1: fs_date=st.date_input("📅 Rango:",value=[],key="fs_date")
    with sf2: fs_code=st.multiselect("🔢 Código:",options=sorted([c for c in df['exit_code'].unique() if c]),key="fs_cod")
    with sf3: fs_prof=st.multiselect("👨‍🏫 Profesor:",options=sorted([s for s in df['prof_mixed'].unique() if s]),key="fs_prof")
    with sf4: fs_art=st.multiselect("📦 Artículo:",options=sorted([a for a in df['article_mixed'].unique() if a]),key="fs_art")
    with sf5: fs_resp=st.multiselect("👤 Responsable:",options=sorted([r for r in df['delivered_to'].unique() if pd.notna(r) and r]),key="fs_resp")
    dv=df.copy()
    if fs_date and len(fs_date)==2: dv=dv[dv['date'].dt.date.between(fs_date[0],fs_date[1]).fillna(False)]
    elif fs_date and len(fs_date)==1: dv=dv[(dv['date'].dt.date==fs_date[0]).fillna(False)]
    if fs_code: dv=dv[dv['exit_code'].isin(fs_code)]
    if fs_prof: dv=dv[dv['prof_mixed'].isin(fs_prof)]
    if fs_art: dv=dv[dv['article_mixed'].isin(fs_art)]
    if fs_resp: dv=dv[dv['delivered_to'].isin(fs_resp)]
    st.caption(f"Mostrando **{len(dv)}** salidas")
    map_ext={"exit_code":"Cód.","date":"Fecha","client_name":"Profesor","article_code":"Cód.Art.","article_name":"Artículo","quantity":"Cantidad","delivered_to":"Responsable"}
    sx1,sx2=st.columns([3,1])
    with sx1: cs_ext=st.multiselect("📊 Columnas exportar:",options=list(map_ext.values()),default=list(map_ext.values()),key="cs_ext")
    with sx2:
        if cs_ext:
            imap={v:k for k,v in map_ext.items()}; df_ex2=dv[[imap[v] for v in cs_ext if v in imap]].copy()
            if 'date' in df_ex2.columns: df_ex2['date']=df_ex2['date'].dt.strftime('%d-%m-%Y')
            df_ex2.rename(columns=map_ext,inplace=True)
            st.download_button("📥 Excel",data=_to_excel(df_ex2),file_name="salidas.xlsx",mime="application/vnd.ms-excel",key="btn_exp_sal")
    dv.insert(0,"Sel",False)
    ed_sal=st.data_editor(dv,num_rows="dynamic",key="ed_sal",column_config={
        "Sel":st.column_config.CheckboxColumn("✅",width="small"),"id":{"hidden":True},
        "client_code":{"hidden":True},"client_name":{"hidden":True},"article_code":{"hidden":True},"article_name":{"hidden":True},
        "exit_code":st.column_config.TextColumn("Código"),"date":st.column_config.DateColumn("Fecha",format="DD-MM-YYYY"),
        "prof_mixed":st.column_config.SelectboxColumn("Profesor",options=list_profs_full,width="medium"),
        "article_mixed":st.column_config.SelectboxColumn("Artículo",options=list_articles_full,width="medium"),
        "quantity":st.column_config.NumberColumn("Cant."),"delivered_to":st.column_config.SelectboxColumn("Responsable",options=list_responsibles),
    },use_container_width=True)
    ss1,ss2=st.columns(2)
    with ss1:
        if st.button("💾 Guardar cambios",key="save_sal",type="primary"):
            try:
                for _,row in ed_sal.iterrows():
                    cc,cn="",""; ac,an="",""
                    if row['prof_mixed']:
                        pts=row['prof_mixed'].split(' / ',1)
                        if len(pts)==2: cc,cn=pts
                    if row['article_mixed']:
                        pts=row['article_mixed'].split(' / ',1)
                        if len(pts)==2: ac,an=pts
                    ds=_fd(row['date']); fr=row['delivered_to']
                    if not fr and cn:
                        cands=prof_resp_map.get(cn,[])
                        if len(cands)==1: fr=cands[0]
                    if pd.isna(row['id']):
                        conn.execute("INSERT INTO stock_exits (exit_code,date,client_name,client_code,article_name,article_code,quantity,delivered_to,last_modified_by) VALUES (?,?,?,?,?,?,?,?,?)",(row['exit_code'] or None,ds,cn,cc,an,ac,row['quantity'],fr,current_user))
                    else:
                        conn.execute("UPDATE stock_exits SET exit_code=?,date=?,client_name=?,client_code=?,article_name=?,article_code=?,quantity=?,delivered_to=?,last_modified_by=? WHERE id=?",(row['exit_code'] or None,ds,cn,cc,an,ac,row['quantity'],fr,current_user,row['id']))
                conn.commit(); _sync_stock(conn); st.success("✅ Guardado."); _clear_cache(); time.sleep(0.4); st.rerun()
            except Exception as e: st.error(f"Error: {e}")
    with ss2:
        if st.button("🗑️ Eliminar seleccionados",key="del_sal"):
            try:
                for i in ed_sal[ed_sal["Sel"]==True]["id"].dropna().tolist():
                    conn.execute("DELETE FROM stock_exits WHERE id=?",(i,))
                conn.commit(); _sync_stock(conn); st.success("✅ Eliminado."); _clear_cache(); time.sleep(0.4); st.rerun()
            except: pass
    conn.close()

# ============================================================================
# PÁGINA 5 — CONFIGURACIÓN
# ============================================================================
def pagina_configuracion():
    _banner(); st.title("⚙️ Configuración")
    tab_rev,tab_usr=st.tabs(["📁 Revisiones","👥 Gestión de Usuarios"])

    with tab_rev:
        st.markdown("### 📁 Revisiones guardadas")
        st.markdown("Sube archivos **PDF, CSV o XLSX**. Los XLSX se importan automáticamente al guardar.")
        archivos_subidos=st.file_uploader("📎 Arrastra aquí tus archivos",type=["pdf","csv","xlsx"],accept_multiple_files=True,key="rev_uploader")
        col_nombre,col_btn=st.columns([3,1])
        with col_nombre:
            nombre_rev=st.text_input("Nombre de la revisión",value=_nombre_revision_por_defecto(),key="rev_nombre")
        with col_btn:
            st.markdown("<br>",unsafe_allow_html=True)
            if st.button("💾 Guardar revisión",key="btn_guardar_rev",use_container_width=True):
                if not archivos_subidos: st.warning("⚠️ Sube al menos un archivo.")
                elif not nombre_rev.strip(): st.error("El nombre no puede estar vacío.")
                else:
                    pares=[(f.name,f.read()) for f in archivos_subidos]
                    crear_revision(nombre_rev.strip(),pares)
                    st.success(f"✅ Revisión **{nombre_rev}** guardada. Datos importados automáticamente.")
                    _clear_cache(); st.rerun()
        st.markdown("---")
        revisiones=listar_revisiones()
        if not revisiones:
            st.info("No hay revisiones guardadas aún.")
        else:
            st.markdown(f"**{len(revisiones)} revisión(es) guardada(s):**")
            for carpeta in revisiones:
                meta=leer_meta(carpeta); archivos=archivos_de_revision(carpeta)
                st.markdown(f"""
                <div class="revision-card">
                    <div class="revision-nombre">📁 {meta['nombre']}</div>
                    <div class="revision-meta">🕐 Creada: {meta['creada']} &nbsp;|&nbsp; 📄 {len(archivos)} archivo(s)</div>
                </div>""",unsafe_allow_html=True)
                c1,c2,c3,c4=st.columns([3,1,1,1])
                with c1:
                    if archivos: st.caption("📄 "+" , ".join(p.name for p in archivos))
                with c2:
                    nuevo_nom=st.text_input("",placeholder="Nuevo nombre…",key=f"ren_{carpeta.name}",label_visibility="collapsed")
                with c3:
                    if st.button("✏️ Renombrar",key=f"btn_ren_{carpeta.name}"):
                        if nuevo_nom.strip(): renombrar_revision(carpeta,nuevo_nom.strip()); st.success("✅ Renombrada."); st.rerun()
                        else: st.warning("Escribe el nuevo nombre.")
                with c4:
                    if st.button("🗑️ Eliminar",key=f"btn_del_{carpeta.name}"):
                        eliminar_revision(carpeta); st.success("🗑️ Revisión y datos eliminados."); st.rerun()
                with st.expander("➕ Añadir archivos a esta revisión",expanded=False):
                    extra=st.file_uploader("Arrastra PDF, CSV o XLSX",type=["pdf","csv","xlsx"],accept_multiple_files=True,key=f"extra_{carpeta.name}")
                    if st.button("Añadir a revisión",key=f"btn_add_{carpeta.name}"):
                        if extra:
                            xlsx_nuevos=[]
                            for f in extra:
                                dest=carpeta/f.name
                                contenido=f.read()
                                with open(dest,"wb") as out: out.write(contenido)
                                if f.name.lower().endswith(".xlsx"): xlsx_nuevos.append(contenido)
                            if xlsx_nuevos:
                                conn=get_db()
                                try:
                                    _importar_xlsx_a_bd(conn,xlsx_nuevos[-1],"revision",limpiar=True)
                                    conn.execute("INSERT OR IGNORE INTO demo_loaded (id) VALUES (1)")
                                    conn.commit(); _sync_stock(conn); _clear_cache()
                                except Exception as e: st.error(f"Error importando: {e}")
                                finally: conn.close()
                            st.success(f"✅ {len(extra)} archivo(s) añadido(s)."); st.rerun()
                        else: st.warning("Selecciona al menos un archivo.")
                st.markdown("<div style='margin-bottom:0.5rem'></div>",unsafe_allow_html=True)

    with tab_usr:
        st.markdown("### 👥 Usuarios registrados")
        usuarios_actuales=cargar_usuarios()
        for uname,udata in list(usuarios_actuales.items()):
            cu,cn,cr,cd=st.columns([2,2,1,1])
            with cu: st.markdown(f"**`{uname}`**")
            with cn: st.markdown(udata.get('nombre','—'))
            with cr:
                icon="🔑" if udata.get('rol')=='admin' else "👤"
                st.markdown(f"{icon} {udata.get('rol','usuario')}")
            with cd:
                admins=[u for u,d in usuarios_actuales.items() if d.get('rol')=='admin']
                puede=not (uname==st.session_state.usuario_actual or (udata.get('rol')=='admin' and len(admins)<=1))
                if puede:
                    if st.button("🗑️",key=f"del_u_{uname}",help=f"Eliminar {uname}"):
                        del usuarios_actuales[uname]; guardar_usuarios(usuarios_actuales)
                        st.success(f"Usuario **{uname}** eliminado."); st.rerun()
                else: st.markdown("—")
        st.markdown("---"); st.markdown("### 🔑 Cambiar contraseña")
        ca,cb=st.columns(2)
        with ca: usr_c=st.selectbox("Usuario",options=list(usuarios_actuales.keys()),key="c_usr")
        with cb: np1=st.text_input("Nueva contraseña",type="password",key="np1")
        np2=st.text_input("Confirmar contraseña",type="password",key="np2")
        if st.button("💾 Guardar contraseña",use_container_width=True):
            if not np1: st.error("La contraseña no puede estar vacía.")
            elif np1!=np2: st.error("Las contraseñas no coinciden.")
            elif len(np1)<6: st.error("Mínimo 6 caracteres.")
            else:
                usuarios_actuales[usr_c]['password_hash']=hash_password(np1)
                guardar_usuarios(usuarios_actuales); st.success(f"✅ Contraseña de **{usr_c}** actualizada.")
        st.markdown("---"); st.markdown("### ➕ Añadir nuevo usuario")
        c1,c2=st.columns(2)
        with c1:
            nu_user=st.text_input("Nombre de usuario",placeholder="ej: usuario1",key="nu_user")
            nu_name=st.text_input("Nombre completo",placeholder="ej: Ana Pérez",key="nu_name")
        with c2:
            nu_pass=st.text_input("Contraseña",type="password",key="nu_pass")
            nu_rol=st.selectbox("Rol",options=["usuario","admin"],key="nu_rol")
        if st.button("➕ Crear usuario",use_container_width=True):
            nu=nu_user.strip()
            if not nu: st.error("El nombre no puede estar vacío.")
            elif nu in usuarios_actuales: st.error(f"El usuario **{nu}** ya existe.")
            elif not nu_pass: st.error("La contraseña no puede estar vacía.")
            elif len(nu_pass)<6: st.error("Mínimo 6 caracteres.")
            elif not re.match(r'^[a-zA-Z0-9_\-\.]+$',nu): st.error("Solo letras, números, guiones y puntos.")
            else:
                usuarios_actuales[nu]={"password_hash":hash_password(nu_pass),"nombre":nu_name.strip() or nu,"rol":nu_rol}
                guardar_usuarios(usuarios_actuales); st.success(f"✅ Usuario **{nu}** creado."); st.rerun()

# ============================================================================
# MAIN
# ============================================================================
def main():
    init_db()
    with st.sidebar:
        st.markdown(f'<div style="max-width:160px;margin:0 auto 0.5rem auto">{LOGO_SVG}</div>',unsafe_allow_html=True)
        usuarios=cargar_usuarios()
        nombre_mostrar=usuarios.get(st.session_state.usuario_actual,{}).get('nombre',st.session_state.usuario_actual)
        st.markdown(f"👤 **{nombre_mostrar}**")
        if st.button("🚪 Cerrar Sesión",use_container_width=True):
            for k in list(defaults.keys()): st.session_state[k]=defaults[k]
            st.rerun()
        st.markdown("---")
        st.markdown("**📎 Subida rápida**")
        archivos_sidebar=st.file_uploader("PDF, CSV o XLSX",type=["pdf","csv","xlsx"],accept_multiple_files=True,key="sidebar_uploader",label_visibility="collapsed")
        if archivos_sidebar:
            nombre_auto=_nombre_revision_por_defecto()
            if st.button("💾 Guardar como revisión",key="btn_sidebar_save",use_container_width=True):
                pares=[(f.name,f.read()) for f in archivos_sidebar]
                crear_revision(nombre_auto,pares)
                st.success(f"✅ Guardado: {nombre_auto}"); st.rerun()
        st.markdown("---")

    p_existencias=st.Page(pagina_existencias,  title="Existencias",  icon="📦",default=True)
    p_productos  =st.Page(pagina_productos,    title="Productos",    icon="🗂️")
    p_entradas   =st.Page(pagina_entradas,     title="Entradas",     icon="📥")
    p_salidas    =st.Page(pagina_salidas,      title="Salidas",      icon="📤")
    p_config     =st.Page(pagina_configuracion,title="Configuración",icon="⚙️")

    pg=st.navigation({
        f"{APP_NAME}":[p_existencias,p_productos,p_entradas,p_salidas],
        "Administración":[p_config],
    })
    pg.run()

if __name__=="__main__":
    main()
