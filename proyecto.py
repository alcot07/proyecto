import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
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
BASE_DIR           = Path(__file__).resolve().parent
CARPETA_REVISIONES = BASE_DIR / "revisiones"
CARPETA_REVISIONES.mkdir(exist_ok=True)
USUARIOS_FILE      = BASE_DIR / "usuarios.json"
DATA_DIR           = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_FILE            = DATA_DIR / "inventory_shared.db"
LOGO_FILE          = BASE_DIR / "logo" / "alcot_logo.png"

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
defaults={'autenticado':False,'usuario_actual':None,'revision_activa':None}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k]=v

try:    logo_icon=Image.open(LOGO_FILE)
except: logo_icon="🖥️"

st.set_page_config(page_title=APP_NAME, page_icon=logo_icon, layout="wide", initial_sidebar_state="expanded")

# ============================================================================
# CSS
# ============================================================================
st.markdown("""
<style>
:root{--bg-dark:#0d1b2a;--lima:#7fff00;--verde:#39d353;--verde-dim:#2aad3e;--texto:#e8f5e9;}
header[data-testid="stHeader"]{background-color:var(--bg-dark) !important;border-bottom:3px solid var(--lima) !important;}
header::after{display:none !important;}
section[data-testid="stSidebar"]{background-color:var(--bg-dark) !important;border-right:2px solid var(--verde) !important;padding-top:1rem;}
section[data-testid="stSidebar"]>div,
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{background-color:var(--bg-dark) !important;}
section[data-testid="stSidebar"] *,section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div,section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,section[data-testid="stSidebar"] h3{color:var(--texto) !important;font-size:15px;}
section[data-testid="stSidebar"] .stButton>button,section[data-testid="stSidebar"] button{
    background-color:rgba(127,255,0,0.12) !important;color:var(--lima) !important;
    border:1px solid rgba(127,255,0,0.4) !important;border-radius:6px !important;
    font-size:13px !important;width:100% !important;box-shadow:none !important;}
section[data-testid="stSidebar"] .stButton>button:hover,
section[data-testid="stSidebar"] button:hover{background-color:rgba(127,255,0,0.25) !important;}
section[data-testid="stSidebar"] button p{color:var(--lima) !important;font-size:13px !important;}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]{background-color:transparent !important;border-radius:6px !important;padding:0.4rem 0.6rem !important;transition:background 0.2s;}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover{background-color:rgba(127,255,0,0.12) !important;}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"]{background-color:rgba(57,211,83,0.2) !important;border-left:3px solid var(--lima) !important;font-weight:700 !important;}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span,
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] p{color:var(--texto) !important;}
section[data-testid="stSidebar"] nav>div>p{color:rgba(127,255,0,0.55) !important;font-size:11px !important;text-transform:uppercase;letter-spacing:0.08em;font-weight:600 !important;}
.main{padding:2rem;}
.main .stButton>button{background-color:var(--bg-dark);color:var(--lima);border:1px solid var(--verde);border-radius:6px;padding:0.5rem 1rem;font-weight:600;width:100%;}
.main .stButton>button:hover{background-color:var(--verde-dim);color:#ffffff;}
[data-testid="stMetric"]{background:var(--bg-dark);border-radius:10px;padding:1rem;border:1px solid var(--verde);}
[data-testid="stMetricLabel"]{color:var(--texto) !important;}
[data-testid="stMetricValue"]{color:var(--lima) !important;font-weight:900 !important;}
input,textarea{border-radius:6px !important;}
footer{visibility:hidden;}
.login-box{max-width:420px;margin:3rem auto;padding:2.5rem 2rem;background:#0d1b2a;border-radius:12px;box-shadow:0 4px 32px rgba(127,255,0,0.15);border-top:5px solid #7fff00;}
.login-box label,.login-box p,.login-box span{color:#e8f5e9 !important;}
.revision-card{background:var(--bg-dark);border:1px solid rgba(57,211,83,0.4);border-left:4px solid var(--lima);border-radius:8px;padding:0.8rem 1rem;margin-bottom:0.5rem;}
.revision-card-activa{background:#0d2a1a;border:1px solid #7fff00;border-left:4px solid #7fff00;border-radius:8px;padding:0.8rem 1rem;margin-bottom:0.5rem;}
.revision-nombre{font-weight:700;color:var(--lima);font-size:1rem;}
.revision-meta{font-size:0.8rem;color:rgba(255,255,255,0.55);margin-top:0.2rem;}
button[data-baseweb="tab"] p,button[data-baseweb="tab"] span{color:#39d353 !important;font-weight:600 !important;}
button[data-baseweb="tab"][aria-selected="true"] p,
button[data-baseweb="tab"][aria-selected="true"] span{color:#7fff00 !important;font-weight:700 !important;}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"]{background-color:#7fff00 !important;}
div[data-testid="stTabs"] [data-baseweb="tab-border"]{background-color:rgba(57,211,83,0.3) !important;}
</style>
""", unsafe_allow_html=True)

# ============================================================================
# LOGIN
# ============================================================================
def mostrar_login():
    st.markdown("""<style>
    section[data-testid="stSidebar"]{display:none !important;}
    [data-testid="collapsedControl"]{display:none !important;}
    body,.main{background-color:#0d1b2a !important;}
    </style>""", unsafe_allow_html=True)
    _,col_c,_=st.columns([1,2,1])
    with col_c: st.markdown(LOGO_SVG,unsafe_allow_html=True)
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
# BANNER y TÍTULO
# ============================================================================
def _banner():
    col_logo,col_titulo=st.columns([1,4])
    with col_logo:
        st.markdown(f'<div style="max-width:180px">{LOGO_SVG}</div>',unsafe_allow_html=True)
    with col_titulo:
        st.markdown(f"""
        <div style="padding-left:1rem;padding-top:0.5rem;">
            <span style="font-family:Arial Black,sans-serif;font-size:2rem;font-weight:900;letter-spacing:2px;color:#7fff00;">{APP_NAME}</span><br>
            <span style="font-size:0.85rem;color:#39d353;font-weight:600;">Gestión de Inventario</span>
        </div>
        """,unsafe_allow_html=True)
    if st.session_state.revision_activa:
        meta=leer_meta(st.session_state.revision_activa)
        st.markdown(f"<div style='margin-top:0.3rem;padding-left:1rem;'><span style='background:#0d2a1a;border:1px solid #7fff00;border-radius:4px;padding:0.2rem 0.6rem;font-size:0.8rem;color:#7fff00;'>📁 Revisión activa: <b>{meta['nombre']}</b></span></div>",unsafe_allow_html=True)
    st.markdown("<hr style='border:1.5px solid #39d353;margin-top:0.5rem;margin-bottom:1.5rem;'>",unsafe_allow_html=True)

def _titulo(icono,texto):
    st.markdown(f"<h1 style='color:#39d353;'>{icono} {texto}</h1>",unsafe_allow_html=True)

# ============================================================================
# REVISIONES — helpers
# ============================================================================
def _nombre_revision_por_defecto(): return dt.now().strftime("%H:%M - %d/%m/%Y")
def _slug(nombre): return re.sub(r'[<>:"/\\|?*\s]','_',nombre.strip())

def listar_revisiones():
    if not CARPETA_REVISIONES.exists(): return []
    return sorted([r for r in CARPETA_REVISIONES.iterdir() if r.is_dir()],key=lambda r:r.stat().st_mtime,reverse=True)

def crear_revision(nombre,archivos):
    slug=_slug(nombre); carpeta=CARPETA_REVISIONES/slug; carpeta.mkdir(exist_ok=True)
    meta={"nombre":nombre,"creada":dt.now().strftime("%H:%M - %d/%m/%Y")}
    with open(carpeta/"_meta.json","w",encoding="utf-8") as f: json.dump(meta,f,ensure_ascii=False)
    xlsx_encontrado=None
    for nom_arch,contenido in archivos:
        with open(carpeta/nom_arch,"wb") as f: f.write(contenido)
        if nom_arch.lower().endswith(".xlsx"): xlsx_encontrado=contenido
    if xlsx_encontrado:
        conn=get_db()
        try:
            _importar_xlsx_a_bd(conn,xlsx_encontrado,"revision",limpiar=True)
            conn.execute("INSERT OR IGNORE INTO demo_loaded (id) VALUES (1)")
            conn.commit()
        except Exception as e: print(f"Auto-import error: {e}")
        finally: conn.close()
        st.session_state.revision_activa=carpeta
    return carpeta

def leer_meta(carpeta):
    if carpeta is None: return {"nombre":"Sin revisión","creada":""}
    mf=carpeta/"_meta.json"
    if mf.exists():
        try:
            with open(mf,"r",encoding="utf-8") as f: return json.load(f)
        except: pass
    mtime=dt.fromtimestamp(carpeta.stat().st_mtime)
    return {"nombre":carpeta.name.replace("_"," "),"creada":mtime.strftime("%H:%M - %d/%m/%Y")}

def archivos_de_revision(carpeta):
    return [p for p in sorted(carpeta.iterdir()) if p.suffix.lower() in (".pdf",".csv",".xlsx") and p.name!="_meta.json"]

def cargar_revision(carpeta):
    xlsx_files=[p for p in archivos_de_revision(carpeta) if p.suffix.lower()==".xlsx"]
    if not xlsx_files:
        st.warning("Esta revisión no tiene archivos XLSX para cargar.")
        return False
    conn=get_db()
    try:
        _importar_xlsx_a_bd(conn,xlsx_files[-1].read_bytes(),"revision",limpiar=True)
        conn.execute("INSERT OR IGNORE INTO demo_loaded (id) VALUES (1)")
        conn.commit(); _clear_cache()
        return True
    except Exception as e:
        st.error(f"Error cargando revisión: {e}"); return False
    finally: conn.close()

def eliminar_revision(carpeta):
    if st.session_state.revision_activa==carpeta:
        st.session_state.revision_activa=None
        conn=get_db()
        try:
            for tabla in ["ordenadores","demo_loaded"]:
                conn.execute(f"DELETE FROM {tabla}")
            conn.commit()
        except: pass
        finally: conn.close()
    shutil.rmtree(carpeta); _clear_cache()

def renombrar_revision(carpeta,nuevo_nombre):
    meta_vieja=leer_meta(carpeta); nueva=CARPETA_REVISIONES/_slug(nuevo_nombre)
    carpeta.rename(nueva)
    with open(nueva/"_meta.json","w",encoding="utf-8") as f:
        json.dump({"nombre":nuevo_nombre,"creada":meta_vieja.get("creada","")},f,ensure_ascii=False)
    if st.session_state.revision_activa==carpeta:
        st.session_state.revision_activa=nueva
    return nueva

# ============================================================================
# BASE DE DATOS — adaptada al inventario del instituto
# ============================================================================
def get_db():
    conn=sqlite3.connect(DB_FILE,check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON"); conn.row_factory=sqlite3.Row; return conn

def init_db():
    conn=get_db(); c=conn.cursor()
    for sql in [
        """CREATE TABLE IF NOT EXISTS ordenadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aula TEXT,
            pc TEXT,
            mac TEXT,
            procesador TEXT,
            ram TEXT,
            disco_duro TEXT,
            numero_serie TEXT,
            numero_serie_pantalla TEXT,
            pulgadas TEXT,
            observaciones TEXT
        )""",
        "CREATE TABLE IF NOT EXISTS entradas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, aula TEXT, pc TEXT, mac TEXT, procesador TEXT, ram TEXT, disco_duro TEXT, numero_serie TEXT, numero_serie_pantalla TEXT, pulgadas TEXT, observaciones TEXT, responsable TEXT)",
        "CREATE TABLE IF NOT EXISTS salidas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, aula TEXT, pc TEXT, mac TEXT, motivo TEXT, responsable TEXT, observaciones TEXT)",
        "CREATE TABLE IF NOT EXISTS demo_loaded (id INTEGER PRIMARY KEY)",
    ]: c.execute(sql)
    conn.commit(); _load_demo(conn); conn.close()

def _sc(val):
    if val is None: return ""
    try:
        if pd.isna(val): return ""
    except: pass
    s=str(val).strip()
    if s in ("nan","None",""): return ""
    return s

def _clear_cache(): st.cache_data.clear()

def _load_demo(conn):
    if conn.execute("SELECT COUNT(*) FROM demo_loaded").fetchone()[0]>0: return
    demo=BASE_DIR/"Inventario_Instituto.xlsx"
    if not demo.exists(): return
    try:
        _importar_xlsx_a_bd(conn,demo.read_bytes(),"demo")
        conn.execute("INSERT INTO demo_loaded (id) VALUES (1)"); conn.commit()
    except Exception as e: print(f"Demo load error: {e}")

# ============================================================================
# IMPORTACIÓN XLSX — lee cada hoja como un aula
# ============================================================================
def _importar_xlsx_a_bd(conn,xlsx_bytes,fuente="import",limpiar=False):
    if limpiar:
        for tabla in ["ordenadores","entradas","salidas","demo_loaded"]:
            conn.execute(f"DELETE FROM {tabla}")
        conn.commit()

    xls=pd.read_excel(io.BytesIO(xlsx_bytes),sheet_name=None)
    total=0

    for sheet_name, df in xls.items():
        # Normalizar columnas
        df.columns=[str(c).strip() for c in df.columns]
        # La primera columna es el nombre del PC (Pc1, Pc2...)
        col_pc=df.columns[0]  # ej: "Aula 0-3"
        aula=sheet_name.strip()

        for _,row in df.iterrows():
            pc=_sc(row.get(col_pc,""))
            if not pc: continue
            mac=_sc(row.get("Mac del ordenador ","") or row.get("Mac del ordenador",""))
            procesador=_sc(row.get("Procesador ","") or row.get("Procesador",""))
            ram=_sc(row.get("RAM",""))
            disco=_sc(row.get("Disco duro ","") or row.get("Disco duro",""))
            nserie=_sc(row.get("Número de serie ","") or row.get("Número de serie",""))
            nserie_pant=_sc(row.get("Número de serie de pantalla ","") or row.get("Número de serie de pantalla",""))
            pulgadas=_sc(row.get("Pulgadas ","") or row.get("Pulgadas",""))
            obs=_sc(row.get("OBSERVACIONES",""))
            try:
                conn.execute(
                    "INSERT INTO ordenadores (aula,pc,mac,procesador,ram,disco_duro,numero_serie,numero_serie_pantalla,pulgadas,observaciones) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (aula,pc,mac,procesador,ram,disco,nserie,nserie_pant,pulgadas,obs))
                total+=1
            except Exception as e: print(f"Error insertando {aula}/{pc}: {e}")

    conn.commit()
    return total

def _to_excel(df):
    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine='openpyxl') as w: df.to_excel(w,index=False,sheet_name='Datos')
    return buf.getvalue()

# ============================================================================
# CHECK REVISIÓN
# ============================================================================
def _check_revision():
    if not st.session_state.revision_activa:
        st.markdown("<br>",unsafe_allow_html=True)
        st.markdown("""
        <div style='background:#0d1b2a;border:2px solid #7fff00;border-radius:10px;padding:2rem;text-align:center;'>
            <span style='font-size:2rem;'>📁</span><br>
            <span style='color:#7fff00;font-size:1.2rem;font-weight:700;'>No hay ninguna revisión activa</span><br>
            <span style='color:#39d353;font-size:0.9rem;'>Ve a <b>Configuración → Revisiones</b> y activa una revisión para ver los datos.</span>
        </div>
        """,unsafe_allow_html=True)
        return False
    return True

# ============================================================================
# PÁGINA 1 — EXISTENCIAS
# ============================================================================
def pagina_existencias():
    _banner(); _titulo("📦","Existencias")
    if not _check_revision(): return

    conn=get_db()
    df=pd.read_sql("SELECT * FROM ordenadores",conn)
    conn.close()

    # Métricas principales
    total_pcs=len(df)
    total_aulas=df['aula'].nunique()
    con_obs=len(df[df['observaciones'].notna() & (df['observaciones']!="")])

    m1,m2,m3=st.columns(3)
    m1.metric("🖥️ Total ordenadores",total_pcs)
    m2.metric("🏫 Total aulas",total_aulas)
    m3.metric("⚠️ Con observaciones",con_obs)
    st.markdown("---")

    # Filtros
    st.markdown("#### 🔎 Filtros")
    fc1,fc2,fc3,fc4=st.columns(4)

    aulas_disp=sorted(df['aula'].dropna().unique().tolist())
    macs_disp=sorted([m for m in df['mac'].dropna().unique().tolist() if m])
    nserie_disp=sorted([n for n in df['numero_serie'].dropna().unique().tolist() if n and n!="0"])
    obs_disp=sorted([o for o in df['observaciones'].dropna().unique().tolist() if o])

    with fc1: f_aula=st.multiselect("🏫 Aula",options=aulas_disp,key="ex_aula")
    with fc2: f_mac=st.multiselect("🔌 MAC",options=macs_disp,key="ex_mac")
    with fc3: f_ns=st.multiselect("🔢 Nº Serie",options=nserie_disp,key="ex_ns")
    with fc4: f_obs=st.multiselect("⚠️ Observaciones",options=obs_disp,key="ex_obs")

    df_view=df.copy()
    if f_aula: df_view=df_view[df_view['aula'].isin(f_aula)]
    if f_mac:  df_view=df_view[df_view['mac'].isin(f_mac)]
    if f_ns:   df_view=df_view[df_view['numero_serie'].isin(f_ns)]
    if f_obs:  df_view=df_view[df_view['observaciones'].isin(f_obs)]

    st.caption(f"Mostrando **{len(df_view)}** de **{total_pcs}** ordenadores")

    # Gráfica por aula
    if not df_view.empty:
        try:
            import plotly.express as px
            df_c=df_view.groupby('aula').size().reset_index(name='Ordenadores')
            fig=px.bar(df_c,x='aula',y='Ordenadores',color='aula',height=300,
                color_discrete_sequence=['#7fff00','#39d353','#2aad3e','#0d5c2e','#a8ff47','#57e86b','#1a8c3a','#b2ff59'])
            fig.update_layout(showlegend=False,plot_bgcolor='rgba(0,0,0,0)',paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=10,r=10,t=30,b=40),xaxis_title="Aula",yaxis_title="Nº Ordenadores")
            st.plotly_chart(fig,use_container_width=True)
        except ImportError:
            st.bar_chart(df_view.groupby('aula').size())

    st.markdown("---")

    # Tabla
    cols_mostrar=['aula','pc','mac','procesador','ram','disco_duro','numero_serie','numero_serie_pantalla','pulgadas','observaciones']
    rename_cols={
        'aula':'Aula','pc':'PC','mac':'MAC','procesador':'Procesador',
        'ram':'RAM','disco_duro':'Disco Duro','numero_serie':'Nº Serie',
        'numero_serie_pantalla':'Nº Serie Pantalla','pulgadas':'Pulgadas','observaciones':'Observaciones'
    }
    df_show=df_view[cols_mostrar].rename(columns=rename_cols)
    st.dataframe(df_show,use_container_width=True,hide_index=True)

    # Exportar
    if not df_show.empty:
        st.download_button("📥 Exportar Excel",data=_to_excel(df_show),
            file_name="existencias.xlsx",mime="application/vnd.ms-excel",key="exp_ex")

# ============================================================================
# PÁGINA 2 — PRODUCTOS (vista por aula con detalle)
# ============================================================================
def pagina_productos():
    _banner(); _titulo("🗂️ Equipos por Aula")
    if not _check_revision(): return

    conn=get_db()
    df=pd.read_sql("SELECT * FROM ordenadores",conn)
    conn.close()

    # Filtros
    fp1,fp2=st.columns(2)
    aulas_disp=sorted(df['aula'].dropna().unique().tolist())
    procesadores_disp=sorted([p for p in df['procesador'].dropna().unique().tolist() if p])
    with fp1: f_aula=st.multiselect("🏫 Filtrar por Aula:",options=aulas_disp,key="pr_aula")
    with fp2: f_proc=st.multiselect("⚙️ Filtrar por Procesador:",options=procesadores_disp,key="pr_proc")

    df_all=df.copy()
    if f_aula: df_all=df_all[df_all['aula'].isin(f_aula)]
    if f_proc: df_all=df_all[df_all['procesador'].isin(f_proc)]

    # Desplegable por aula
    for aula in sorted(df_all['aula'].unique()):
        gdf=df_all[df_all['aula']==aula].copy()
        with st.expander(f"🏫 {aula} — {len(gdf)} ordenadores"):
            cols_mostrar=['pc','mac','procesador','ram','disco_duro','numero_serie','numero_serie_pantalla','pulgadas','observaciones']
            rename_cols={
                'pc':'PC','mac':'MAC','procesador':'Procesador','ram':'RAM',
                'disco_duro':'Disco Duro','numero_serie':'Nº Serie',
                'numero_serie_pantalla':'Nº Serie Pantalla','pulgadas':'Pulgadas','observaciones':'Observaciones'
            }
            st.dataframe(gdf[cols_mostrar].rename(columns=rename_cols),use_container_width=True,hide_index=True)
            st.download_button(f"📥 Exportar {aula}",
                data=_to_excel(gdf[cols_mostrar].rename(columns=rename_cols)),
                file_name=f"{aula.replace(' ','_')}.xlsx",
                mime="application/vnd.ms-excel",key=f"exp_{aula}")

# ============================================================================
# PÁGINA 3 — ENTRADAS
# ============================================================================
def pagina_entradas():
    _banner(); _titulo("📥","Entradas")
    if not _check_revision(): return

    conn=get_db()
    df_ords=pd.read_sql("SELECT DISTINCT aula FROM ordenadores ORDER BY aula",conn)
    df_ent=pd.read_sql("SELECT * FROM entradas ORDER BY fecha DESC, id DESC",conn)
    conn.close()

    aulas_disp=df_ords['aula'].tolist()

    # Formulario añadir entrada
    with st.expander("➕ Registrar Nueva Entrada de Equipo",expanded=False):
        e1,e2,e3=st.columns(3)
        ne_fecha=e1.date_input("📅 Fecha",value=datetime.date.today(),key="ne_fecha")
        ne_aula=e2.selectbox("🏫 Aula",options=[""]+aulas_disp,key="ne_aula")
        ne_pc=e3.text_input("🖥️ PC (ej: Pc1)",key="ne_pc")

        e4,e5,e6=st.columns(3)
        ne_mac=e4.text_input("🔌 MAC",key="ne_mac")
        ne_proc=e5.text_input("⚙️ Procesador",key="ne_proc")
        ne_ram=e6.text_input("💾 RAM",key="ne_ram")

        e7,e8,e9=st.columns(3)
        ne_disco=e7.text_input("💿 Disco Duro",key="ne_disco")
        ne_ns=e8.text_input("🔢 Nº Serie",key="ne_ns")
        ne_nsp=e9.text_input("🔢 Nº Serie Pantalla",key="ne_nsp")

        e10,e11=st.columns(2)
        ne_pul=e10.text_input("📐 Pulgadas",key="ne_pul")
        ne_resp=e11.text_input("👤 Responsable",key="ne_resp")
        ne_obs=st.text_input("📝 Observaciones",key="ne_obs")

        if st.button("💾 Guardar Entrada",key="btn_ent_add"):
            if ne_aula and ne_pc:
                conn=get_db()
                try:
                    conn.execute(
                        "INSERT INTO entradas (fecha,aula,pc,mac,procesador,ram,disco_duro,numero_serie,numero_serie_pantalla,pulgadas,observaciones,responsable) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (ne_fecha.strftime("%d-%m-%Y"),ne_aula,ne_pc,ne_mac,ne_proc,ne_ram,ne_disco,ne_ns,ne_nsp,ne_pul,ne_obs,ne_resp))
                    conn.commit()
                    st.success("✅ Entrada registrada."); _clear_cache(); time.sleep(0.4); st.rerun()
                except Exception as e: st.error(f"Error: {e}")
                finally: conn.close()
            else: st.warning("Selecciona aula e introduce el PC.")

    st.markdown("#### 🔎 Filtros")
    ff1,ff2,ff3=st.columns(3)
    with ff1: fe_aula=st.multiselect("🏫 Aula:",options=aulas_disp,key="fe_aula")
    with ff2:
        fe_fecha=st.date_input("📅 Rango:",value=[],key="fe_fecha")
    with ff3:
        resps=sorted([r for r in df_ent['responsable'].dropna().unique() if r]) if not df_ent.empty else []
        fe_resp=st.multiselect("👤 Responsable:",options=resps,key="fe_resp")

    dv=df_ent.copy()
    if fe_aula: dv=dv[dv['aula'].isin(fe_aula)]
    if fe_resp: dv=dv[dv['responsable'].isin(fe_resp)]
    if fe_fecha and len(fe_fecha)==2:
        dv['_d']=pd.to_datetime(dv['fecha'],dayfirst=True,errors='coerce').dt.date
        dv=dv[dv['_d'].between(fe_fecha[0],fe_fecha[1])].drop('_d',axis=1)

    st.caption(f"Mostrando **{len(dv)}** entradas registradas")

    rename_e={'fecha':'Fecha','aula':'Aula','pc':'PC','mac':'MAC','procesador':'Procesador',
              'ram':'RAM','disco_duro':'Disco Duro','numero_serie':'Nº Serie',
              'numero_serie_pantalla':'Nº Serie Pantalla','pulgadas':'Pulgadas',
              'observaciones':'Observaciones','responsable':'Responsable'}

    cols_show=[c for c in rename_e.keys() if c in dv.columns]
    df_show=dv[cols_show].rename(columns=rename_e)
    st.dataframe(df_show,use_container_width=True,hide_index=True)

    c1,c2=st.columns(2)
    with c1:
        if not df_show.empty:
            st.download_button("📥 Exportar Excel",data=_to_excel(df_show),
                file_name="entradas.xlsx",mime="application/vnd.ms-excel",key="exp_ent")
    with c2:
        ids_sel=st.multiselect("Seleccionar IDs a eliminar:",options=dv['id'].tolist() if not dv.empty else [],key="del_ent_ids")
        if st.button("🗑️ Eliminar seleccionados",key="del_ent"):
            if ids_sel:
                conn=get_db()
                for i in ids_sel: conn.execute("DELETE FROM entradas WHERE id=?",(i,))
                conn.commit(); conn.close()
                st.success(f"🗑️ {len(ids_sel)} entrada(s) eliminada(s)."); _clear_cache(); time.sleep(0.4); st.rerun()
            else: st.warning("Selecciona al menos un ID.")

# ============================================================================
# PÁGINA 4 — SALIDAS
# ============================================================================
def pagina_salidas():
    _banner(); _titulo("📤","Salidas")
    if not _check_revision(): return

    conn=get_db()
    df_ords=pd.read_sql("SELECT DISTINCT aula FROM ordenadores ORDER BY aula",conn)
    df_sal=pd.read_sql("SELECT * FROM salidas ORDER BY fecha DESC, id DESC",conn)
    conn.close()

    aulas_disp=df_ords['aula'].tolist()
    motivos=["Reparación","Sustitución","Baja definitiva","Préstamo","Otro"]

    with st.expander("➕ Registrar Nueva Salida de Equipo",expanded=False):
        s1,s2,s3=st.columns(3)
        ns_fecha=s1.date_input("📅 Fecha",value=datetime.date.today(),key="ns_fecha")
        ns_aula=s2.selectbox("🏫 Aula",options=[""]+aulas_disp,key="ns_aula")
        ns_pc=s3.text_input("🖥️ PC (ej: Pc1)",key="ns_pc")

        s4,s5=st.columns(2)
        ns_mac=s4.text_input("🔌 MAC del equipo",key="ns_mac")
        ns_motivo=s5.selectbox("📋 Motivo",options=[""]+motivos,key="ns_motivo")

        s6,s7=st.columns(2)
        ns_resp=s6.text_input("👤 Responsable",key="ns_resp")
        ns_obs=s7.text_input("📝 Observaciones",key="ns_obs")

        if st.button("💾 Guardar Salida",key="btn_sal_add"):
            if ns_aula and ns_pc:
                conn=get_db()
                try:
                    conn.execute(
                        "INSERT INTO salidas (fecha,aula,pc,mac,motivo,responsable,observaciones) VALUES (?,?,?,?,?,?,?)",
                        (ns_fecha.strftime("%d-%m-%Y"),ns_aula,ns_pc,ns_mac,ns_motivo,ns_resp,ns_obs))
                    conn.commit()
                    st.success("✅ Salida registrada."); _clear_cache(); time.sleep(0.4); st.rerun()
                except Exception as e: st.error(f"Error: {e}")
                finally: conn.close()
            else: st.warning("Selecciona aula e introduce el PC.")

    st.markdown("#### 🔎 Filtros")
    sf1,sf2,sf3,sf4=st.columns(4)
    with sf1: fs_aula=st.multiselect("🏫 Aula:",options=aulas_disp,key="fs_aula")
    with sf2: fs_motivo=st.multiselect("📋 Motivo:",options=motivos,key="fs_motivo")
    with sf3:
        resps=sorted([r for r in df_sal['responsable'].dropna().unique() if r]) if not df_sal.empty else []
        fs_resp=st.multiselect("👤 Responsable:",options=resps,key="fs_resp")
    with sf4: fs_fecha=st.date_input("📅 Rango:",value=[],key="fs_fecha")

    dv=df_sal.copy()
    if fs_aula: dv=dv[dv['aula'].isin(fs_aula)]
    if fs_motivo: dv=dv[dv['motivo'].isin(fs_motivo)]
    if fs_resp: dv=dv[dv['responsable'].isin(fs_resp)]
    if fs_fecha and len(fs_fecha)==2:
        dv['_d']=pd.to_datetime(dv['fecha'],dayfirst=True,errors='coerce').dt.date
        dv=dv[dv['_d'].between(fs_fecha[0],fs_fecha[1])].drop('_d',axis=1)

    st.caption(f"Mostrando **{len(dv)}** salidas registradas")

    rename_s={'fecha':'Fecha','aula':'Aula','pc':'PC','mac':'MAC',
              'motivo':'Motivo','responsable':'Responsable','observaciones':'Observaciones'}
    cols_show=[c for c in rename_s.keys() if c in dv.columns]
    df_show=dv[cols_show].rename(columns=rename_s)
    st.dataframe(df_show,use_container_width=True,hide_index=True)

    c1,c2=st.columns(2)
    with c1:
        if not df_show.empty:
            st.download_button("📥 Exportar Excel",data=_to_excel(df_show),
                file_name="salidas.xlsx",mime="application/vnd.ms-excel",key="exp_sal")
    with c2:
        ids_sel=st.multiselect("Seleccionar IDs a eliminar:",options=dv['id'].tolist() if not dv.empty else [],key="del_sal_ids")
        if st.button("🗑️ Eliminar seleccionados",key="del_sal"):
            if ids_sel:
                conn=get_db()
                for i in ids_sel: conn.execute("DELETE FROM salidas WHERE id=?",(i,))
                conn.commit(); conn.close()
                st.success(f"🗑️ {len(ids_sel)} salida(s) eliminada(s)."); _clear_cache(); time.sleep(0.4); st.rerun()
            else: st.warning("Selecciona al menos un ID.")

# ============================================================================
# PÁGINA 5 — CONFIGURACIÓN
# ============================================================================
def pagina_configuracion():
    _banner(); _titulo("⚙️","Configuración")
    tab_rev,tab_usr=st.tabs(["📁 Revisiones","👥 Gestión de Usuarios"])

    with tab_rev:
        st.markdown("### 📁 Revisiones guardadas")
        st.markdown("Sube el archivo **XLSX** del inventario. Se importará automáticamente al guardar la revisión.")
        archivos_subidos=st.file_uploader("📎 Arrastra aquí tu archivo",type=["pdf","csv","xlsx"],accept_multiple_files=True,key="rev_uploader")
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
                    st.success(f"✅ Revisión **{nombre_rev}** guardada y activada.")
                    _clear_cache(); st.rerun()

        st.markdown("---")
        revisiones=listar_revisiones()
        if not revisiones:
            st.info("No hay revisiones guardadas aún.")
        else:
            st.markdown(f"**{len(revisiones)} revisión(es) guardada(s):**")
            for carpeta in revisiones:
                meta=leer_meta(carpeta)
                archivos=archivos_de_revision(carpeta)
                es_activa=st.session_state.revision_activa==carpeta
                clase_card="revision-card-activa" if es_activa else "revision-card"
                etiqueta=" &nbsp;✅ <b>ACTIVA</b>" if es_activa else ""
                st.markdown(f"""
                <div class="{clase_card}">
                    <div class="revision-nombre">📁 {meta['nombre']}{etiqueta}</div>
                    <div class="revision-meta">🕐 Creada: {meta['creada']} &nbsp;|&nbsp; 📄 {len(archivos)} archivo(s)</div>
                </div>""",unsafe_allow_html=True)
                c1,c2,c3,c4,c5=st.columns([2,1,1,1,1])
                with c1:
                    if archivos: st.caption("📄 "+" , ".join(p.name for p in archivos))
                with c2:
                    if not es_activa:
                        if st.button("▶️ Activar",key=f"act_{carpeta.name}",use_container_width=True):
                            if cargar_revision(carpeta):
                                st.session_state.revision_activa=carpeta
                                st.success(f"✅ Activada."); _clear_cache(); time.sleep(0.4); st.rerun()
                    else:
                        st.markdown("<span style='color:#7fff00;font-size:0.85rem;font-weight:700;'>✅ Activa</span>",unsafe_allow_html=True)
                with c3:
                    nuevo_nom=st.text_input("",placeholder="Nuevo nombre…",key=f"ren_{carpeta.name}",label_visibility="collapsed")
                with c4:
                    if st.button("✏️",key=f"btn_ren_{carpeta.name}",help="Renombrar"):
                        if nuevo_nom.strip(): renombrar_revision(carpeta,nuevo_nom.strip()); st.success("✅ Renombrada."); st.rerun()
                        else: st.warning("Escribe el nuevo nombre.")
                with c5:
                    if st.button("🗑️",key=f"btn_del_{carpeta.name}",help="Eliminar"):
                        eliminar_revision(carpeta); st.success("🗑️ Eliminada."); st.rerun()
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
        st.markdown("---")
        usuarios=cargar_usuarios()
        nombre_mostrar=usuarios.get(st.session_state.usuario_actual,{}).get('nombre',st.session_state.usuario_actual)
        st.markdown(f"👤 **{nombre_mostrar}**")
        if st.button("🚪 Cerrar Sesión",use_container_width=True):
            for k in list(defaults.keys()): st.session_state[k]=defaults[k]
            st.rerun()
        st.markdown("---")
        revisiones=listar_revisiones()
        if revisiones:
            st.markdown("**📁 Revisión activa**")
            nombres={leer_meta(r)['nombre']:r for r in revisiones}
            activa_nombre=leer_meta(st.session_state.revision_activa)['nombre'] if st.session_state.revision_activa else list(nombres.keys())[0]
            sel=st.selectbox("",options=list(nombres.keys()),
                index=list(nombres.keys()).index(activa_nombre) if activa_nombre in nombres else 0,
                key="sel_revision",label_visibility="collapsed")
            if nombres[sel]!=st.session_state.revision_activa:
                if st.button("▶️ Cargar revisión",use_container_width=True,key="btn_cargar_rev"):
                    if cargar_revision(nombres[sel]):
                        st.session_state.revision_activa=nombres[sel]; _clear_cache(); st.rerun()
            else:
                st.markdown("<span style='color:#7fff00;font-size:0.8rem;'>✅ Cargada</span>",unsafe_allow_html=True)
            st.markdown("---")
        st.markdown("**📎 Subida rápida**")
        archivos_sidebar=st.file_uploader("XLSX / PDF / CSV",type=["pdf","csv","xlsx"],accept_multiple_files=True,key="sidebar_uploader",label_visibility="collapsed")
        if archivos_sidebar:
            nombre_auto=_nombre_revision_por_defecto()
            if st.button("💾 Guardar como revisión",key="btn_sidebar_save",use_container_width=True):
                pares=[(f.name,f.read()) for f in archivos_sidebar]
                crear_revision(nombre_auto,pares)
                st.success(f"✅ Guardado: {nombre_auto}"); _clear_cache(); st.rerun()
        st.markdown("---")

    p_existencias=st.Page(pagina_existencias,title="Existencias",icon="📦",default=True)
    p_productos  =st.Page(pagina_productos,  title="Equipos por Aula",icon="🗂️")
    p_entradas   =st.Page(pagina_entradas,   title="Entradas",icon="📥")
    p_salidas    =st.Page(pagina_salidas,    title="Salidas",icon="📤")
    p_config     =st.Page(pagina_configuracion,title="Configuración",icon="⚙️")

    pg=st.navigation({
        f"{APP_NAME}":[p_existencias,p_productos,p_entradas,p_salidas],
        "Administración":[p_config],
    })
    pg.run()

if __name__=="__main__":
    main()
