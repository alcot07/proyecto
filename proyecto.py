import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import traceback
import shutil
import pickle
import hashlib
import json
from pathlib import Path
from PIL import Image
from datetime import datetime, timezone, timedelta

# ============================================================================
# RUTAS E ICONO
# ============================================================================
BASE_DIR = Path(__file__).resolve().parent
DIR_DISENO = BASE_DIR / "diseño"
ICONO_FILE = DIR_DISENO / "ada-icono (1).png"
HEADER_MAIN_FILE = DIR_DISENO / "ADA-vc-color (1).jpg"
CARPETA_REVISIONES = BASE_DIR / "revisiones"
CARPETA_REVISIONES.mkdir(exist_ok=True)

USUARIOS_FILE = BASE_DIR / "usuarios.json"

# ============================================================================
# GESTIÓN DE USUARIOS
# ============================================================================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def cargar_usuarios() -> dict:
    if USUARIOS_FILE.exists():
        try:
            with open(USUARIOS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    usuarios_default = {
        "admin": {
            "password_hash": hash_password("admin123"),
            "nombre": "Administrador",
            "rol": "admin"
        }
    }
    guardar_usuarios(usuarios_default)
    return usuarios_default

def guardar_usuarios(usuarios: dict):
    with open(USUARIOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(usuarios, f, ensure_ascii=False, indent=2)

def verificar_credenciales(username: str, password: str) -> bool:
    usuarios = cargar_usuarios()
    if username in usuarios:
        return usuarios[username]['password_hash'] == hash_password(password)
    return False

# ============================================================================
# SESSION STATE
# ============================================================================
defaults = {
    'autenticado': False,
    'usuario_actual': None,
    'archivos_procesados': None,
    'comparacion_ejecutada': False,
    'dataframes_procesados': None,
    'info_archivos': None,
    'revision_activa': None,
    'revision_activa_path': None,
    'renombrando': None,
    'confirmando_borrar': None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

try:
    icono_pestana = Image.open(ICONO_FILE)
except Exception:
    icono_pestana = "📂"

st.set_page_config(
    page_title="RPT - Gestor de Puestos",
    page_icon=icono_pestana,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CSS
# ============================================================================
st.markdown("""
    <style>
    :root {
        --verde-junta: #0b6e3c;
        --verde-hover: #158f4a;
    }
    header[data-testid="stHeader"] {
        border-bottom: 4px solid var(--verde-junta);
        padding: 0.5rem;
    }
    header::after { display: none !important; }
    header img { max-height: 60px !important; object-fit: contain; }

    section[data-testid="stSidebar"] {
        background-color: var(--verde-junta) !important;
        padding-top: 1rem;
    }
    section[data-testid="stSidebar"] > div,
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"],
    section[data-testid="stSidebarContent"] {
        background-color: var(--verde-junta) !important;
    }
    section[data-testid="stSidebar"] *,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #ffffff !important;
        font-size: 15px;
    }
    section[data-testid="stSidebar"] .stButton > button,
    section[data-testid="stSidebar"] button,
    section[data-testid="stSidebar"] [data-testid="baseButton-secondary"],
    section[data-testid="stSidebar"] [data-testid="baseButton-primary"] {
        background-color: rgba(255,255,255,0.15) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.5) !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        padding: 0.3rem 0.5rem !important;
        width: 100% !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover,
    section[data-testid="stSidebar"] button:hover {
        background-color: rgba(255,255,255,0.3) !important;
        color: #ffffff !important;
        border-color: rgba(255,255,255,0.7) !important;
    }
    section[data-testid="stSidebar"] button p,
    section[data-testid="stSidebar"] .stButton > button p {
        color: #ffffff !important;
        font-size: 13px !important;
    }
    /* st.navigation links */
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {
        background-color: transparent !important;
        border-radius: 6px !important;
        padding: 0.4rem 0.6rem !important;
        transition: background 0.2s;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {
        background-color: rgba(255,255,255,0.2) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {
        background-color: rgba(255,255,255,0.25) !important;
        border-left: 3px solid #ffffff !important;
        font-weight: 700 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span,
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] p {
        color: #ffffff !important;
    }
    /* Cabeceras de sección del nav */
    section[data-testid="stSidebar"] nav > div > p {
        color: rgba(255,255,255,0.6) !important;
        font-size: 11px !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600 !important;
    }

    [data-testid="collapsedControl"] { border-radius: 4px; }
    .main { padding: 2rem; }
    .main .stButton > button {
        background-color: var(--verde-junta);
        color: #ffffff;
        border-radius: 6px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        width: 100%;
    }
    .main .stButton > button:hover { background-color: var(--verde-hover); }
    input, textarea { border-radius: 6px !important; }
    footer { visibility: hidden; }

    /* Login */
    .login-box {
        max-width: 420px;
        margin: 3rem auto;
        padding: 2.5rem 2rem;
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 4px 24px rgba(11,110,60,0.13);
        border-top: 5px solid #0b6e3c;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# LOGIN
# ============================================================================
def mostrar_login():
    st.markdown("""
        <style>
        section[data-testid="stSidebar"]  { display: none !important; }
        [data-testid="collapsedControl"]  { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

    try:
        if HEADER_MAIN_FILE.exists():
            _, col_c, _ = st.columns([1, 2, 1])
            with col_c:
                st.image(str(HEADER_MAIN_FILE), use_container_width=True)
    except Exception:
        pass

    _, col_c, _ = st.columns([1, 1.4, 1])
    with col_c:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("<h3 style='text-align:center;color:#0b6e3c;'>🔐 Acceso al Sistema</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#666;font-size:0.9rem;'>RPT – Gestor de Efectivos</p>", unsafe_allow_html=True)
        username = st.text_input("👤 Usuario", placeholder="Introduce tu usuario", key="login_user")
        password = st.text_input("🔑 Contraseña", type="password", placeholder="Introduce tu contraseña", key="login_pass")
        if st.button("Entrar →", type="primary", use_container_width=True):
            if not username.strip():
                st.error("Introduce tu usuario.")
            elif not password:
                st.error("Introduce tu contraseña.")
            elif verificar_credenciales(username.strip(), password):
                st.session_state.autenticado = True
                st.session_state.usuario_actual = username.strip()
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos.")
        st.markdown('</div>', unsafe_allow_html=True)


if not st.session_state.autenticado:
    mostrar_login()
    st.stop()

# ============================================================================
# FUNCIONES DE REVISIONES
# ============================================================================

def listar_revisiones():
    if not CARPETA_REVISIONES.exists():
        return []
    return sorted(
        [r for r in CARPETA_REVISIONES.iterdir() if r.is_dir()],
        key=lambda r: r.stat().st_mtime,
        reverse=True
    )

def guardar_revision(nombre_revision, archivos_lista):
    nombre_limpio = re.sub(r'[<>:"/\\|?*]', '_', nombre_revision.strip())
    carpeta_rev = CARPETA_REVISIONES / nombre_limpio
    carpeta_rev.mkdir(exist_ok=True)
    for nombre_arch, bytes_pdf in archivos_lista:
        with open(carpeta_rev / nombre_arch, 'wb') as f:
            f.write(bytes_pdf)
    return carpeta_rev

def cargar_revision(carpeta_rev):
    archivos = []
    for pdf_path in sorted(carpeta_rev.glob("*.pdf")):
        with open(pdf_path, 'rb') as f:
            archivos.append((pdf_path.name, f.read()))
    return archivos

def eliminar_revision(carpeta_rev):
    shutil.rmtree(carpeta_rev)

def guardar_cache(carpeta_rev, dataframes_procesados, info_archivos):
    cache_path = carpeta_rev / "_cache.pkl"
    with open(cache_path, 'wb') as f:
        pickle.dump({'dataframes': dataframes_procesados, 'info': info_archivos}, f)

def cargar_cache(carpeta_rev):
    cache_path = carpeta_rev / "_cache.pkl"
    if cache_path.exists():
        try:
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
            return data['dataframes'], data['info']
        except Exception:
            return None, None
    return None, None

def renombrar_revision(carpeta_rev, nuevo_nombre):
    nuevo_nombre_limpio = re.sub(r'[<>:"/\\|?*]', '_', nuevo_nombre.strip())
    nueva_carpeta = CARPETA_REVISIONES / nuevo_nombre_limpio
    carpeta_rev.rename(nueva_carpeta)
    return nueva_carpeta

# ============================================================================
# FUNCIONES DE EXTRACCIÓN
# ============================================================================

def es_linea_plaza(linea):
    if ',' in linea and re.search(r'\d{8}[A-Z]\d+[A-Z].*,', linea): return False
    if re.match(r'^\s*\d?\s*\d{4,8}\s*[A-ZÁÉÍÓÚÑ]', linea):
        if not re.match(r'^\s*\d{6,8}[A-Z]\d+[A-Z]+\d+', linea): return True
    return False

def es_linea_persona(linea):
    if re.match(r'^\s*\d{8}[A-Z]\d+[A-Z]+\d+[A-ZÁÉÍÓÚÑÜ\s\.\-ªº]+,\s*[A-ZÁÉÍÓÚÑÜ]', linea): return True
    if re.match(r'^\s*\d{8}[A-Z]\d+L\d+[A-ZÁÉÍÓÚÑÜ\s\.\-ªº]+,\s*[A-ZÁÉÍÓÚÑÜ]', linea): return True
    return False

def extraer_codigo_puesto(linea):
    match = re.search(r'(\d{4,8})', linea)
    return match.group(1) if match else None

def extraer_denominacion(linea):
    match_codigo = re.search(r'\d{4,8}', linea)
    if not match_codigo: return None
    resto = linea[match_codigo.end():]
    match = re.match(r'\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s\.\/\(\)ºª\-]+?)(?:\.{2,}|\s+[A-E]\d|\s+\d+\s+\d+)', resto)
    if match:
        denom = re.sub(r'\.+$', '', match.group(1).strip()).strip()
        return denom if len(denom) > 2 else None
    return None

def extraer_grupo(linea):
    match = re.search(r'\s+([A-E]\d(?:-[A-E]\d)?)\s+P-[A-E]\d', linea)
    if match: return match.group(1)
    match = re.search(r'\s+([A-E]\d(?:-[A-E]\d)?)P-[A-E]\d', linea)
    if match: return match.group(1)
    match = re.search(r'\s+([IVX]+)\s+[A-Z]', linea)
    if match: return match.group(1)
    return None

def extraer_cuerpo(linea):
    match = re.search(r'(P-[A-E]\d+)[\s\w]', linea)
    if match: return match.group(1)
    match = re.search(r'[IVX]+\s+([A-ZÁÉÍÓÚÑ\s\.]+?)\s+\d{2}\s+', linea)
    if match:
        c = ' '.join(match.group(1).strip().split())
        return c if len(c) > 3 else None
    return None

def extraer_nombre_persona(linea):
    match = re.search(r'\d{8}[A-Z]\d+[A-Z]+\d+([A-ZÁÉÍÓÚÑÜ\s,\.\-ªº]+?)(?:\s+[A-E]\d|\s+FUNC\.|LABORAL|[A-E]\d+\s)', linea)
    if match:
        nombre = ' '.join(match.group(1).strip().split())
        if len(nombre) > 5 and ',' in nombre: return nombre
    return None

def extraer_formacion(linea):
    if 'PROVISIONAL' in linea.upper(): return 'PROVISIONAL'
    elif 'DEFINITIVO' in linea.upper(): return 'DEFINITIVO'
    return None

def extraer_dni(linea):
    match = re.search(r'(\d{8}[A-Z])', linea)
    return match.group(1) if match else None

def extraer_ads(linea):
    if re.search(r'\b1F\s', linea): return 'F'
    if re.search(r'\b1L\s', linea): return 'L'
    return None

def extraer_modo_acceso(linea):
    match = re.search(r'1F\s+([A-Z]{2,3}(?:,\w+)?|[A-Z]\.\d+,?/?\d*|/\d+,[A-Z]\.\d+)\s+(?:AX\s+)?[A-E]\d', linea)
    if match:
        modo = match.group(1).strip()
        if modo in ('PC', 'PLD', 'PCE'): return modo
        elif modo.startswith('RD'): return 'RD (Art.7.1.A)'
        elif modo.startswith('D.') or modo.startswith('/'): return 'DTO 2/2002'
        return modo
    match_pld_ax = re.search(r'1F\s+(PLD)\s+AX\s+[A-E]\d', linea)
    if match_pld_ax: return 'PLD'
    match_laboral = re.search(r'1L\s+([A-Z]{1,3}(?:,\w+)?)\s+[IVX]+\s', linea)
    if match_laboral:
        modo = match_laboral.group(1).strip()
        return 'PC,S' if modo == 'S,PC' else modo
    match2 = re.search(r'\d{6,8}\s*[A-ZÁÉÍÓÚÑ][^\d]*?\s+(\d+)\s+(\d+)\s+([A-E]\d)', linea)
    if not match2:
        match3 = re.search(r'\.+\s+([A-E]\d(?:-[A-E]\d)?)\s*(P-[A-E]\d+)', linea)
        if match3:
            match_modo = re.search(r'\s(PC|PLD|PCE)\s', linea)
            if match_modo: return match_modo.group(1)
    return None

LOCALIDAD_A_PROVINCIA = {
    'ALMERIA': 'ALMERÍA', 'MOJONERA (LA)': 'ALMERÍA',
    'ALGECIRAS': 'CÁDIZ', 'CADIZ': 'CÁDIZ', 'CHIPIONA': 'CÁDIZ',
    'JEREZ DE LA FRONTERA': 'CÁDIZ', 'PUERTO DE SANTA MARI': 'CÁDIZ',
    'SANLUCAR DE BARRAMED': 'CÁDIZ',
    'CABRA': 'CÓRDOBA', 'CORDOBA': 'CÓRDOBA', 'HINOJOSA DEL DUQUE': 'CÓRDOBA',
    'PALMA DEL RIO': 'CÓRDOBA',
    'ARMILLA': 'GRANADA', 'GRANADA': 'GRANADA', 'MOTRIL': 'GRANADA',
    'CARTAYA': 'HUELVA', 'HUELVA': 'HUELVA',
    'JAEN': 'JAÉN', 'MENGIBAR': 'JAÉN',
    'CAMPANILLAS': 'MÁLAGA', 'CHURRIANA': 'MÁLAGA', 'MALAGA': 'MÁLAGA',
    'ALCALA DEL RIO': 'SEVILLA', 'AZNALCAZAR': 'SEVILLA',
    'PALACIOS Y VILLAFRAN': 'SEVILLA', 'SEVILLA': 'SEVILLA',
}

LOCALIDADES_INVALIDAS = {
    'DPL. INFORMATICA INFORMATICA SEVILLA', 'GRDO/A EN ING SEVILLA',
    'INFORMATICA MALAGA', 'INFORMATICA SEVILLA', 'INGENIERO EN SEVILLA',
    'INGENIERO SEVILLA',
}

def extraer_localidad(linea):
    match = re.search(r'[\d\.]+,\d{2}\s+(?:\d+\s+)?([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s\.\/\-\(\)]+?)\s*$', linea)
    if match:
        localidad = match.group(1).strip().upper()
        if len(localidad) >= 3 and localidad not in LOCALIDADES_INVALIDAS:
            return localidad
        if localidad in LOCALIDADES_INVALIDAS:
            partes = localidad.split()
            for n_palabras in range(1, min(4, len(partes))):
                candidata = ' '.join(partes[-n_palabras:])
                if candidata in LOCALIDAD_A_PROVINCIA:
                    return candidata
    return "NO ESPECIFICADA"

def localidad_a_provincia(localidad):
    return LOCALIDAD_A_PROVINCIA.get(localidad, "NO ESPECIFICADA")

def extraer_dotacion(linea):
    if "NO DOTADA" in linea.upper(): return "NO DOTADA"
    match = re.search(r'\.+\s+(\d+)\s+(\d+)\s', linea)
    if match: return "NO DOTADA" if match.group(2) == '0' else "DOTADA"
    match2 = re.search(r'\.+\s+(\d+)\s+(\d+)\s+[A-E]\d', linea)
    if match2: return "NO DOTADA" if match2.group(2) == '0' else "DOTADA"
    match3 = re.search(r'\s(\d+)\s+(\d+)\s+[A-E]\d(?:-[A-E]\d)?(?:\s|P-)', linea)
    if match3: return "NO DOTADA" if match3.group(2) == '0' else "DOTADA"
    match4 = re.search(r'\s(\d+)\s+(\d+)\s+[IVX]+\s', linea)
    if match4: return "NO DOTADA" if match4.group(2) == '0' else "DOTADA"
    partes = linea.split()
    if len(partes) > 2 and (partes[-1] == 'N' or partes[-2] == 'N'): return "NO DOTADA"
    return "NO DOTADA"

def extraer_fecha_pdf(archivo_bytes, nombre_archivo):
    try:
        with pdfplumber.open(io.BytesIO(archivo_bytes)) as pdf:
            if pdf.pages:
                texto = pdf.pages[0].extract_text()
                if texto:
                    for linea in texto.split('\n')[:10]:
                        if 'Fecha' in linea or 'fecha' in linea:
                            match = re.search(r'(\d{2}/\d{2}/\d{4})', linea)
                            if match:
                                return match.group(1)
    except Exception:
        pass
    return None

def procesar_pdf(archivo_bytes, nombre_archivo):
    registros = []
    try:
        buffer = io.BytesIO(archivo_bytes)
        with pdfplumber.open(buffer) as pdf:
            num_paginas = len(pdf.pages)
            todas_lineas = []
            paginas_sin_texto = []

            with st.spinner(f'📄 Procesando {nombre_archivo} ({num_paginas} páginas)...'):
                for num_pag, pagina in enumerate(pdf.pages, 1):
                    try:
                        texto = pagina.extract_text()
                        if texto:
                            todas_lineas.extend(texto.split('\n'))
                        else:
                            paginas_sin_texto.append(num_pag)
                    except Exception:
                        pass

                if paginas_sin_texto:
                    st.warning(f"⚠️ {len(paginas_sin_texto)} páginas sin texto en {nombre_archivo}")
                st.info(f"✅ {nombre_archivo}: {len(todas_lineas):,} líneas extraídas de {num_paginas} páginas")

            i = 0
            while i < len(todas_lineas):
                linea = todas_lineas[i]
                if es_linea_plaza(linea):
                    codigo = extraer_codigo_puesto(linea)
                    if not codigo:
                        i += 1
                        continue
                    nombre_ocupante = None
                    dni_ocupante = None
                    formacion_ocupante = None
                    for j in range(1, 6):
                        if (i + j) < len(todas_lineas):
                            sig = todas_lineas[i + j]
                            if es_linea_persona(sig):
                                nombre_ocupante = extraer_nombre_persona(sig)
                                dni_ocupante = extraer_dni(sig)
                                formacion_ocupante = extraer_formacion(sig)
                                if formacion_ocupante is None:
                                    for k in range(1, 4):
                                        if (i + j + k) < len(todas_lineas):
                                            sig2 = todas_lineas[i + j + k]
                                            if es_linea_plaza(sig2) or es_linea_persona(sig2):
                                                break
                                            formacion_ocupante = extraer_formacion(sig2)
                                            if formacion_ocupante:
                                                break
                                break
                            if es_linea_plaza(sig): break
                    _localidad = extraer_localidad(linea)
                    registros.append({
                        'Código':       codigo,
                        'Denominación': extraer_denominacion(linea),
                        'Grupo':        extraer_grupo(linea),
                        'Cuerpo':       extraer_cuerpo(linea),
                        'Provincia':    localidad_a_provincia(_localidad),
                        'Localidad':    _localidad,
                        'Dotación':     extraer_dotacion(linea),
                        'ADS':          extraer_ads(linea),
                        'Modo_Acceso':  extraer_modo_acceso(linea),
                        'Ocupante':     nombre_ocupante if nombre_ocupante else 'LIBRE',
                        'Estado_Plaza': 'OCUPADA' if nombre_ocupante else 'VACANTE',
                        'DNI':          dni_ocupante,
                        'Carácter':     formacion_ocupante
                    })
                i += 1

        df_resultado = pd.DataFrame(registros)
        if df_resultado.empty:
            st.error(f"❌ {nombre_archivo}: no se extrajeron plazas.")
            return pd.DataFrame()

        df_ocupadas = df_resultado[df_resultado['Estado_Plaza'] == 'OCUPADA'].copy()
        if not df_ocupadas.empty and 'DNI' in df_ocupadas.columns:
            df_ocupadas['_clave_persona'] = df_ocupadas['DNI'].fillna('') + '|' + df_ocupadas['Ocupante']
            duplicados = df_ocupadas[df_ocupadas.duplicated(subset=['_clave_persona'], keep=False)]
            if not duplicados.empty:
                for persona in duplicados['_clave_persona'].unique():
                    if '|' not in persona or persona.startswith('|'): continue
                    registros_persona = df_ocupadas[df_ocupadas['_clave_persona'] == persona]
                    if 'PROVISIONAL' in registros_persona['Carácter'].values:
                        definitivos = registros_persona[registros_persona['Carácter'] == 'DEFINITIVO']
                        nombre_func = persona.split('|', 1)[1]
                        for codigo in definitivos['Código'].tolist():
                            df_resultado.loc[df_resultado['Código'] == codigo, 'Estado_Plaza'] = 'VACANTE'
                            df_resultado.loc[df_resultado['Código'] == codigo, 'Ocupante'] = f'({nombre_func})'

        df_resultado = df_resultado.drop_duplicates(subset=['Código'])
        st.success(f"✅ {nombre_archivo}: {len(df_resultado):,} plazas únicas procesadas")
        return df_resultado

    except Exception as e:
        tb = traceback.format_exc()
        st.error(f"❌ Error procesando {nombre_archivo}: {e}")
        with st.expander("🔍 Ver detalles técnicos"):
            st.code(tb)
        return pd.DataFrame()

def ordenar_archivos_por_fecha(archivos_lista):
    archivos_con_fecha = []
    for nombre, archivo_bytes in archivos_lista:
        fecha_str = extraer_fecha_pdf(archivo_bytes, nombre)
        if fecha_str:
            try:
                fecha_obj = datetime.strptime(fecha_str, '%d/%m/%Y')
                archivos_con_fecha.append((nombre, archivo_bytes, fecha_obj, fecha_str))
            except ValueError:
                archivos_con_fecha.append((nombre, archivo_bytes, datetime.min, fecha_str))
        else:
            archivos_con_fecha.append((nombre, archivo_bytes, datetime.min, "Sin fecha"))
    archivos_con_fecha.sort(key=lambda x: x[2])
    return [(n, b, f) for n, b, _, f in archivos_con_fecha]

def enriquecer_dataframe_con_nombres(df_sin_nombres, df_con_nombres):
    if df_con_nombres.empty or df_sin_nombres.empty:
        return df_sin_nombres
    try:
        df_resultado = df_sin_nombres.copy()
        df_nombres_validos = df_con_nombres[df_con_nombres['Ocupante'] != 'LIBRE'].copy()
        if df_nombres_validos.empty:
            return df_resultado
        mapeo_nombres = dict(zip(df_nombres_validos['Código'], df_nombres_validos['Ocupante']))
        for idx, row in df_resultado.iterrows():
            codigo = row['Código']
            if codigo in mapeo_nombres and row['Ocupante'] == 'LIBRE':
                df_resultado.at[idx, 'Ocupante'] = mapeo_nombres[codigo]
                df_resultado.at[idx, 'Estado_Plaza'] = 'OCUPADA'
        st.info(f"✅ Se enriquecieron los datos: {len([x for x in mapeo_nombres.values() if x])} ocupantes relacionados")
        return df_resultado
    except Exception as e:
        st.warning(f"⚠️ No se pudo enriquecer los datos: {e}")
        return df_sin_nombres

# ============================================================================
# PÁGINAS
# ============================================================================

def _banner():
    try:
        if HEADER_MAIN_FILE.exists():
            st.image(str(HEADER_MAIN_FILE), width='stretch')
    except Exception:
        pass


def pagina_nueva_revision():
    _banner()

    # ── Pantalla de carga ──────────────────────────────────────────────
    if not st.session_state.comparacion_ejecutada:
        st.markdown("""
            <div style="text-align:center;margin:2rem 0">
                <div style="font-size:2.5rem;font-weight:700">👥 Gestor de Efectivos RPT</div>
                <div style="font-size:1.1rem;opacity:0.7;margin-top:0.5rem">Analiza un PDF individualmente o compara varios simultáneamente</div>
                <div style="font-size:0.95rem;opacity:0.7;font-weight:500">1 archivo → Revisión individual &nbsp;·&nbsp; 2 o más → Comparación evolutiva</div>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("---")

        st.markdown("### 📝 Nombre de la Revisión")
        nombre_revision = st.text_input("", placeholder="Ej: Revisión Marzo-Febrero 2026", label_visibility="collapsed")

        st.markdown("### 📁 Cargar Archivos PDF")
        st.info("💡 Con 1 PDF: revisión individual. Con 2 o más: comparación cronológica automática.")

        archivos_subidos = st.file_uploader(
            "Arrastra aquí tus PDFs",
            type=['pdf'], accept_multiple_files=True,
            key='uploader_multi', label_visibility="collapsed"
        )

        if archivos_subidos:
            st.success(f"✅ **{len(archivos_subidos)} {'archivo cargado' if len(archivos_subidos)==1 else 'archivos cargados'}**")
            for i, a in enumerate(archivos_subidos, 1):
                st.markdown(f"{i}. 📄 **{a.name}** ({a.size/1024:.1f} KB)")
            st.markdown("---")

            _, col_btn, _ = st.columns([1, 1, 1])
            with col_btn:
                lbl = "🔍 Analizar y Guardar" if len(archivos_subidos) == 1 else "🔍 Comparar y Guardar"
                if st.button(lbl, type="primary", use_container_width=True):
                    if not nombre_revision.strip():
                        dias_es = {'Monday':'Lunes','Tuesday':'Martes','Wednesday':'Miércoles',
                                   'Thursday':'Jueves','Friday':'Viernes','Saturday':'Sábado','Sunday':'Domingo'}
                        try:
                            from zoneinfo import ZoneInfo
                            ahora = datetime.now(ZoneInfo('Europe/Madrid'))
                        except Exception:
                            ahora = datetime.now(timezone(timedelta(hours=1)))
                        dia = dias_es.get(ahora.strftime('%A'), ahora.strftime('%A'))
                        nombre_revision = f"Revisión de {ahora.strftime('%d/%m/%Y %H:%M')} {dia}"

                    archivos_lista = []
                    nombres_vistos = {}
                    for archivo in archivos_subidos:
                        try:
                            cb = archivo.read()
                            if len(cb) == 0:
                                st.warning(f"Archivo vacío: {archivo.name}")
                                continue
                            nb = archivo.name
                            if nb in nombres_vistos:
                                nombres_vistos[nb] += 1
                                ei = nb.rfind('.')
                                nu = (nb[:ei]+f"_{nombres_vistos[nb]}"+nb[ei:]) if ei > 0 else nb+f"_{nombres_vistos[nb]}"
                            else:
                                nombres_vistos[nb] = 1
                                nu = nb
                            archivos_lista.append((nu, cb))
                        except Exception as e:
                            st.warning(f"Error leyendo {archivo.name}: {e}")

                    if archivos_lista:
                        try:
                            guardar_revision(nombre_revision, archivos_lista)
                        except Exception as e:
                            st.warning(f"⚠️ No se pudo guardar: {e}")
                        st.session_state.archivos_procesados = archivos_lista
                        st.session_state.comparacion_ejecutada = True
                        st.session_state.revision_activa = nombre_revision.strip()
                        nl = re.sub(r'[<>:"/\\|?*]', '_', nombre_revision.strip())
                        st.session_state.revision_activa_path = str(CARPETA_REVISIONES / nl)
                        st.rerun()
                    else:
                        st.error("❌ No se pudo leer ningún archivo válido.")
        else:
            st.info("👆 Carga 1 PDF para revisión individual, o 2 o más para comparar versiones")
        return

    # ── Resultados ─────────────────────────────────────────────────────
    titulo = f"📂 {st.session_state.revision_activa}" if st.session_state.revision_activa else "RPT: Análisis"
    st.title(titulo)
    st.markdown("---")

    if st.session_state.dataframes_procesados is None:
        with st.spinner('🔄 Procesando archivos...'):
            archivos_ordenados = ordenar_archivos_por_fecha(st.session_state.archivos_procesados)
            dataframes_procesados = []
            info_archivos = []
            st.markdown("### 📊 Progreso")
            for i, (nombre, archivo_bytes, fecha) in enumerate(archivos_ordenados):
                st.markdown(f"**{i+1}/{len(archivos_ordenados)}:** {nombre}")
                df = procesar_pdf(archivo_bytes, nombre)
                if not df.empty:
                    dataframes_procesados.append(df)
                    info_archivos.append({
                        'nombre': nombre, 'fecha': fecha,
                        'total_plazas': len(df),
                        'dotadas':    len(df[df['Dotación']=='DOTADA']),
                        'no_dotadas': len(df[df['Dotación']=='NO DOTADA']),
                        'ocupadas':   len(df[df['Estado_Plaza']=='OCUPADA']),
                        'libres':     len(df[df['Estado_Plaza']=='VACANTE'])
                    })
                else:
                    st.error(f"⚠️ Sin datos: {nombre}")
            st.markdown("---")

        st.session_state.dataframes_procesados = dataframes_procesados
        st.session_state.info_archivos = info_archivos
        if st.session_state.revision_activa_path:
            try:
                guardar_cache(Path(st.session_state.revision_activa_path), dataframes_procesados, info_archivos)
            except Exception:
                pass
    else:
        dataframes_procesados = st.session_state.dataframes_procesados
        info_archivos = st.session_state.info_archivos

    # Enriquecimiento
    if dataframes_procesados:
        with st.expander("🔗 Enriquecer Datos", expanded=False):
            arch_enr = st.file_uploader("PDF con nombres de ocupantes", type=['pdf'],
                                        key='uploader_enriquecimiento', label_visibility="collapsed")
            if arch_enr and st.button("🔗 Relacionar Datos", type="secondary", use_container_width=True):
                try:
                    cb = arch_enr.read()
                    df_n = procesar_pdf(cb, arch_enr.name)
                    if not df_n.empty:
                        st.session_state.dataframes_procesados = [enriquecer_dataframe_con_nombres(d, df_n) for d in dataframes_procesados]
                        st.rerun()
                    else:
                        st.error("❌ Sin datos en el archivo.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

    # ── Un solo archivo ────────────────────────────────────────────────
    if len(dataframes_procesados) == 1:
        df_solo = dataframes_procesados[0]
        info_solo = info_archivos[0]
        if info_solo.get('fecha') and info_solo['fecha'] != 'Sin fecha':
            st.caption(f"📅 Fecha: **{info_solo['fecha']}**")

        modos_disponibles = sorted([m for m in df_solo['Modo_Acceso'].unique() if pd.notna(m)])
        tiene_modo_acceso = bool(modos_disponibles)

        st.markdown("#### 🔎 Filtros")
        cf1, cf2, cf3, cf4 = st.columns(4)
        with cf1: f_prov  = st.multiselect("Provincia", options=sorted([p for p in df_solo['Provincia'].unique() if p!='NO ESPECIFICADA']), key="solo_prov")
        with cf2: f_grupo = st.multiselect("Grupo",     options=sorted([g for g in df_solo['Grupo'].unique() if pd.notna(g)]), key="solo_grupo")
        with cf3:
            if tiene_modo_acceso: f_modo = st.multiselect("Modo Acceso", options=modos_disponibles, key="solo_modo")
            else:                 f_dot  = st.multiselect("Dotación",    options=['DOTADA','NO DOTADA'], key="solo_dot")
        with cf4:
            if tiene_modo_acceso: f_ads = st.multiselect("ADS", options=sorted([a for a in df_solo['ADS'].unique() if pd.notna(a)]), key="solo_ads")
            else:                 f_est = st.multiselect("Estado", options=df_solo['Estado_Plaza'].unique(), key="solo_est")

        df_f = df_solo.copy()
        if f_prov:  df_f = df_f[df_f['Provincia'].isin(f_prov)]
        if f_grupo: df_f = df_f[df_f['Grupo'].isin(f_grupo)]
        if tiene_modo_acceso:
            if f_modo: df_f = df_f[df_f['Modo_Acceso'].isin(f_modo)]
            if f_ads:  df_f = df_f[df_f['ADS'].isin(f_ads)]
        else:
            if f_dot: df_f = df_f[df_f['Dotación'].isin(f_dot)]
            if f_est: df_f = df_f[df_f['Estado_Plaza'].isin(f_est)]

        st.markdown("### 📊 Resumen")
        if tiene_modo_acceso:
            st.metric("Total Plazas", len(df_f))
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Plazas", len(df_f))
            c2.metric("Ocupadas",     len(df_f[df_f['Estado_Plaza']=='OCUPADA']))
            c3.metric("Vacantes",     len(df_f[df_f['Estado_Plaza']=='VACANTE']))
            c4.metric("Dotadas",      len(df_f[df_f['Dotación']=='DOTADA']))
        st.markdown("---")
        cols_tabla = ['Código','Denominación','ADS','Modo_Acceso','Grupo','Cuerpo','Provincia','Localidad'] if tiene_modo_acceso \
            else ['Código','Denominación','Grupo','Cuerpo','Provincia','Localidad','Carácter','Dotación','Estado_Plaza','Ocupante']
        st.dataframe(df_f[cols_tabla], width='stretch', height=500)
        st.caption(f"Mostrando {len(df_f)} de {len(df_solo)} plazas")

    # ── Comparación múltiple ───────────────────────────────────────────
    elif len(dataframes_procesados) >= 2:
        tp_base  = len(dataframes_procesados[0])
        tp_final = len(dataframes_procesados[-1])
        c1, c2, c3 = st.columns(3)
        c1.metric("Plazas Iniciales",   tp_base,                    help=info_archivos[0]['nombre'])
        c2.metric("Plazas Finales",     tp_final, delta=tp_final-tp_base, help=info_archivos[-1]['nombre'])
        c3.metric("Total de Versiones", len(dataframes_procesados))
        st.markdown("---")
        st.markdown("## 🔀 Comparaciones Detalladas")

        nombres_tabs = []
        for i in range(len(info_archivos)-1):
            n1 = info_archivos[i]['nombre'][:15]+("..." if len(info_archivos[i]['nombre'])>15 else "")
            n2 = info_archivos[i+1]['nombre'][:15]+("..." if len(info_archivos[i+1]['nombre'])>15 else "")
            nombres_tabs.append(f"{n1} → {n2}")

        for idx, tab in enumerate(st.tabs(nombres_tabs)):
            with tab:
                df_old = dataframes_procesados[idx]
                df_new = dataframes_procesados[idx+1]

                cc1, cc2 = st.columns(2)
                with cc1: st.info(f"**📋 Versión Anterior**\n\n{info_archivos[idx]['nombre']}\n\n📅 {info_archivos[idx]['fecha']}")
                with cc2: st.success(f"**📋 Versión Nueva**\n\n{info_archivos[idx+1]['nombre']}\n\n📅 {info_archivos[idx+1]['fecha']}")

                df_comp = pd.merge(df_old, df_new, on='Código', how='outer', suffixes=('_ANT','_ACT'), indicator=True)

                def det_estado(row):
                    if row['_merge']=='left_only':  return '❌ ELIMINADA'
                    if row['_merge']=='right_only': return '🆕 NUEVA'
                    da, db = str(row.get('Dotación_ANT','')), str(row.get('Dotación_ACT',''))
                    oa, ob = str(row.get('Ocupante_ANT','')), str(row.get('Ocupante_ACT',''))
                    cd = da!=db and da!='nan' and db!='nan'
                    co = oa!=ob
                    if cd and co: return '🔄 CAMBIO OCUPANTE + DOTACIÓN'
                    if cd: return '💰 CAMBIO DOTACIÓN'
                    if co: return '🔄 CAMBIO OCUPANTE'
                    return '✅ SIN CAMBIOS'

                df_comp['Situación']         = df_comp.apply(det_estado, axis=1)
                df_comp['Denominación']      = df_comp['Denominación_ACT'].fillna(df_comp['Denominación_ANT'])
                df_comp['Grupo']             = df_comp['Grupo_ACT'].fillna(df_comp['Grupo_ANT'])
                df_comp['Cuerpo']            = df_comp['Cuerpo_ACT'].fillna(df_comp['Cuerpo_ANT'])
                df_comp['Provincia']         = df_comp['Provincia_ACT'].fillna(df_comp['Provincia_ANT'])
                df_comp['Localidad']         = df_comp['Localidad_ACT'].fillna(df_comp['Localidad_ANT'])
                df_comp['Modo_Acceso']       = df_comp['Modo_Acceso_ACT'].fillna(df_comp['Modo_Acceso_ANT'])
                df_comp['Ocupante Anterior'] = df_comp['Ocupante_ANT'].fillna('-')
                df_comp['Ocupante Actual']   = df_comp['Ocupante_ACT'].fillna('-')
                df_comp['Dotación Anterior'] = df_comp['Dotación_ANT'].fillna('-')
                df_comp['Dotación Actual']   = df_comp['Dotación_ACT'].fillna('-')
                df_comp['Dotación']          = df_comp['Dotación_ACT'].fillna(df_comp['Dotación_ANT'])
                df_comp['Estado']            = df_comp['Estado_Plaza_ACT'].fillna(df_comp['Estado_Plaza_ANT'])

                nuevas      = len(df_comp[df_comp['Situación']=='🆕 NUEVA'])
                eliminadas  = len(df_comp[df_comp['Situación']=='❌ ELIMINADA'])
                cambios_ocu = len(df_comp[df_comp['Situación']=='🔄 CAMBIO OCUPANTE'])
                cambios_dot = len(df_comp[df_comp['Situación']=='💰 CAMBIO DOTACIÓN'])

                m1,m2,m3,m4 = st.columns(4)
                m1.metric("🆕 Nuevas",         nuevas,     delta=f"+{nuevas}")
                m2.metric("❌ Eliminadas",      eliminadas, delta=f"-{eliminadas}")
                m3.metric("🔄 Cambio Ocupante", cambios_ocu)
                m4.metric("💰 Cambio Dotación", cambios_dot)
                st.markdown("---")

                st.markdown("#### 🔎 Filtros")
                fc1,fc2,fc3,fc4,fc5 = st.columns(5)
                with fc1: fp   = st.multiselect("Provincia",   options=sorted([p for p in df_comp['Provincia'].dropna().unique() if p!='NO ESPECIFICADA']), key=f"cp_{idx}")
                with fc2: fg   = st.multiselect("Grupo",       options=sorted([g for g in df_comp['Grupo'].dropna().unique()]), key=f"cg_{idx}")
                with fc3: fd   = st.multiselect("Dotación",    options=['DOTADA','NO DOTADA'], key=f"cd_{idx}")
                with fc4: fe   = st.multiselect("Estado Plaza",options=sorted(df_comp['Estado'].dropna().unique()), key=f"ce_{idx}")
                with fc5: fm   = st.multiselect("Modo Acceso", options=sorted([m for m in df_comp['Modo_Acceso'].dropna().unique()]), key=f"cm_{idx}")

                dfc = df_comp.copy()
                if fp: dfc = dfc[dfc['Provincia'].isin(fp)]
                if fg: dfc = dfc[dfc['Grupo'].isin(fg)]
                if fd: dfc = dfc[dfc['Dotación'].isin(fd)]
                if fe: dfc = dfc[dfc['Estado'].isin(fe)]
                if fm: dfc = dfc[dfc['Modo_Acceso'].isin(fm)]

                if any([fp,fg,fd,fe,fm]):
                    st.caption(f"🔎 {len(dfc)} de {len(df_comp)} plazas filtradas")
                st.markdown("---")

                MT = 20
                ta = f"📄 {info_archivos[idx]['nombre'][:MT]}..." if len(info_archivos[idx]['nombre'])>MT else f"📄 {info_archivos[idx]['nombre']}"
                tb_n = f"📄 {info_archivos[idx+1]['nombre'][:MT]}..." if len(info_archivos[idx+1]['nombre'])>MT else f"📄 {info_archivos[idx+1]['nombre']}"

                (st_todos, st_nuevas, st_elim, st_cambios, st_dot, st_ant, st_act) = st.tabs([
                    "🔍 TODOS","🆕 Nuevas","❌ Eliminadas","🔄 Cambio Ocupante","💰 Cambio Dotación", ta, tb_n
                ])

                cols_m = ['Código','Denominación','Modo_Acceso','Grupo','Cuerpo','Provincia','Localidad',
                          'Situación','Dotación Anterior','Dotación Actual','Estado','Ocupante Anterior','Ocupante Actual']

                COLORES = {
                    '❌ ELIMINADA':'#ffebee','🆕 NUEVA':'#e8f5e9',
                    '🔄 CAMBIO OCUPANTE':'#fffde7','💰 CAMBIO DOTACIÓN':'#e3f2fd',
                    '🔄 CAMBIO OCUPANTE + DOTACIÓN':'#f3e5f5','✅ SIN CAMBIOS':'#f1f8f4'
                }
                def color_rows(v): return f'background-color:{COLORES.get(v,"white")}'

                with st_todos:
                    st.dataframe(dfc[cols_m].style.map(color_rows, subset=['Situación']), width='stretch', height=500)
                    st.caption(f"Total: {len(dfc)}")
                with st_nuevas:
                    dn = dfc[dfc['Situación']=='🆕 NUEVA']
                    st.dataframe(dn[cols_m], width='stretch', height=500); st.caption(f"Total: {len(dn)}")
                with st_elim:
                    de = dfc[dfc['Situación']=='❌ ELIMINADA']
                    st.dataframe(de[cols_m], width='stretch', height=500); st.caption(f"Total: {len(de)}")
                with st_cambios:
                    dc = dfc[dfc['Situación']=='🔄 CAMBIO OCUPANTE']
                    st.dataframe(dc[cols_m], width='stretch', height=500); st.caption(f"Total: {len(dc)}")
                with st_dot:
                    dd = dfc[dfc['Situación']=='💰 CAMBIO DOTACIÓN']
                    st.dataframe(dd[cols_m], width='stretch', height=500); st.caption(f"Total: {len(dd)}")

                def _sub_pdf(df_src, info_src, suf):
                    st.markdown(f"#### {info_src['nombre']}")
                    st.caption(f"📅 {info_src['fecha']}")
                    c1,c2,c3,c4 = st.columns(4)
                    with c1: fp2 = st.multiselect("Provincia", options=sorted([p for p in df_src['Provincia'].unique() if p!='NO ESPECIFICADA']), key=f"p{suf}_{idx}")
                    with c2: fg2 = st.multiselect("Grupo",     options=sorted([g for g in df_src['Grupo'].unique() if pd.notna(g)]), key=f"g{suf}_{idx}")
                    with c3: fd2 = st.multiselect("Dotación",  options=['DOTADA','NO DOTADA'], key=f"d{suf}_{idx}")
                    with c4: fe2 = st.multiselect("Estado",    options=df_src['Estado_Plaza'].unique(), key=f"e{suf}_{idx}")
                    df_s = df_src.copy()
                    if fp2: df_s = df_s[df_s['Provincia'].isin(fp2)]
                    if fg2: df_s = df_s[df_s['Grupo'].isin(fg2)]
                    if fd2: df_s = df_s[df_s['Dotación'].isin(fd2)]
                    if fe2: df_s = df_s[df_s['Estado_Plaza'].isin(fe2)]
                    a,b,c,d = st.columns(4)
                    a.metric("Total",    len(df_s))
                    b.metric("Ocupadas", len(df_s[df_s['Estado_Plaza']=='OCUPADA']))
                    c.metric("Vacantes", len(df_s[df_s['Estado_Plaza']=='VACANTE']))
                    d.metric("Dotadas",  len(df_s[df_s['Dotación']=='DOTADA']))
                    st.markdown("---")
                    st.dataframe(df_s[['Código','Denominación','Modo_Acceso','Grupo','Cuerpo','Provincia','Localidad','Carácter','Dotación','Estado_Plaza','Ocupante']], width='stretch', height=500)
                    st.caption(f"Mostrando {len(df_s)} de {len(df_src)}")

                with st_ant: _sub_pdf(df_old, info_archivos[idx],   "ant")
                with st_act: _sub_pdf(df_new, info_archivos[idx+1], "act")

        st.markdown("---")
        if st.button("🔄 Cargar Nuevos Archivos", type="secondary"):
            st.session_state.archivos_procesados  = None
            st.session_state.comparacion_ejecutada = False
            st.session_state.dataframes_procesados = None
            st.session_state.info_archivos         = None
            st.session_state.revision_activa       = None
            st.rerun()

    elif len(dataframes_procesados) == 0:
        st.error("⚠️ No se pudieron procesar los archivos.")
        if st.button("🔄 Volver"):
            st.session_state.archivos_procesados  = None
            st.session_state.comparacion_ejecutada = False
            st.session_state.dataframes_procesados = None
            st.session_state.info_archivos         = None
            st.session_state.revision_activa       = None
            st.rerun()


def pagina_mis_revisiones():
    _banner()
    st.title("📁 Mis Revisiones")
    st.markdown("---")

    revisiones = listar_revisiones()
    if not revisiones:
        st.info("No hay revisiones guardadas. Ve a **Nueva Revisión** para empezar.")
        return

    st.markdown(f"**{len(revisiones)} revisión{'es' if len(revisiones)!=1 else ''} guardada{'s' if len(revisiones)!=1 else ''}**")
    st.markdown("")

    for carpeta_rev in revisiones:
        fecha_mod = datetime.fromtimestamp(carpeta_rev.stat().st_mtime).strftime('%d/%m/%Y %H:%M')
        pdfs = list(carpeta_rev.glob("*.pdf"))
        es_activa = st.session_state.revision_activa == carpeta_rev.name

        col_info, col_abrir, col_ren, col_del = st.columns([4, 1.5, 1, 1])
        with col_info:
            icono = "▶ " if es_activa else "📂 "
            activa_txt = " *(activa)*" if es_activa else ""
            st.markdown(f"**{icono}{carpeta_rev.name}**{activa_txt}")
            st.caption(f"📅 {fecha_mod} · {len(pdfs)} PDF{'s' if len(pdfs)!=1 else ''}")
        with col_abrir:
            if st.button("📂 Abrir", key=f"abrir_{carpeta_rev.name}", use_container_width=True):
                dfs_cache, info_cache = cargar_cache(carpeta_rev)
                archivos = cargar_revision(carpeta_rev)
                if archivos:
                    st.session_state.archivos_procesados  = archivos
                    st.session_state.comparacion_ejecutada = True
                    st.session_state.revision_activa       = carpeta_rev.name
                    st.session_state.revision_activa_path  = str(carpeta_rev)
                    st.session_state.dataframes_procesados = dfs_cache
                    st.session_state.info_archivos         = info_cache
                    st.rerun()
                else:
                    st.warning("Esta revisión no tiene PDFs.")
        with col_ren:
            if st.session_state.renombrando != str(carpeta_rev):
                if st.button("✏️", key=f"ren_{carpeta_rev.name}", help="Renombrar", use_container_width=True):
                    st.session_state.renombrando = str(carpeta_rev)
                    st.rerun()
        with col_del:
            if st.button("🗑️", key=f"del_{carpeta_rev.name}", help="Eliminar", use_container_width=True):
                st.session_state.confirmando_borrar = str(carpeta_rev)
                st.rerun()

        if st.session_state.renombrando == str(carpeta_rev):
            nv = st.text_input("Nuevo nombre", value=carpeta_rev.name, key=f"inp_ren_{carpeta_rev.name}")
            co, cx, _ = st.columns([1, 1, 3])
            with co:
                if st.button("✅ Guardar", key=f"ok_ren_{carpeta_rev.name}"):
                    if nv.strip() and nv.strip() != carpeta_rev.name:
                        nc = renombrar_revision(carpeta_rev, nv.strip())
                        if st.session_state.revision_activa == carpeta_rev.name:
                            st.session_state.revision_activa      = nc.name
                            st.session_state.revision_activa_path = str(nc)
                    st.session_state.renombrando = None
                    st.rerun()
            with cx:
                if st.button("❌ Cancelar", key=f"cx_ren_{carpeta_rev.name}"):
                    st.session_state.renombrando = None
                    st.rerun()

        if st.session_state.confirmando_borrar == str(carpeta_rev):
            st.warning(f"⚠️ ¿Eliminar **{carpeta_rev.name}**? No se puede deshacer.")
            cs, cn, _ = st.columns([1, 1, 3])
            with cs:
                if st.button("✅ Sí, eliminar", key=f"si_del_{carpeta_rev.name}"):
                    eliminar_revision(carpeta_rev)
                    if st.session_state.revision_activa == carpeta_rev.name:
                        for k in ['comparacion_ejecutada','archivos_procesados','dataframes_procesados',
                                  'info_archivos','revision_activa','revision_activa_path']:
                            st.session_state[k] = False if k == 'comparacion_ejecutada' else None
                    st.session_state.confirmando_borrar = None
                    st.rerun()
            with cn:
                if st.button("❌ Cancelar", key=f"cn_del_{carpeta_rev.name}"):
                    st.session_state.confirmando_borrar = None
                    st.rerun()

        st.divider()


def pagina_gestion_usuarios():
    _banner()
    st.title("⚙️ Gestión de Usuarios")
    st.markdown("Gestiona los usuarios que tienen acceso a la aplicación.")
    st.markdown("---")

    usuarios_actuales = cargar_usuarios()

    st.markdown("### 👥 Usuarios registrados")
    for uname, udata in list(usuarios_actuales.items()):
        cu, cn, cr, cd = st.columns([2, 2, 1, 1])
        with cu: st.markdown(f"**`{uname}`**")
        with cn: st.markdown(udata.get('nombre', '—'))
        with cr:
            icono_rol = "🔑" if udata.get('rol') == 'admin' else "👤"
            st.markdown(f"{icono_rol} {udata.get('rol','usuario')}")
        with cd:
            admins = [u for u,d in usuarios_actuales.items() if d.get('rol')=='admin']
            puede = not (uname==st.session_state.usuario_actual or (udata.get('rol')=='admin' and len(admins)<=1))
            if puede:
                if st.button("🗑️", key=f"del_u_{uname}", help=f"Eliminar {uname}"):
                    del usuarios_actuales[uname]
                    guardar_usuarios(usuarios_actuales)
                    st.success(f"Usuario **{uname}** eliminado.")
                    st.rerun()
            else:
                st.markdown("—")

    st.markdown("---")
    st.markdown("### 🔑 Cambiar contraseña")
    ca, cb = st.columns(2)
    with ca: usr_c = st.selectbox("Usuario", options=list(usuarios_actuales.keys()), key="c_usr")
    with cb: np1   = st.text_input("Nueva contraseña",    type="password", key="np1")
    np2 = st.text_input("Confirmar contraseña", type="password", key="np2")
    if st.button("💾 Guardar contraseña", use_container_width=True):
        if not np1:          st.error("La contraseña no puede estar vacía.")
        elif np1 != np2:     st.error("Las contraseñas no coinciden.")
        elif len(np1) < 6:   st.error("Mínimo 6 caracteres.")
        else:
            usuarios_actuales[usr_c]['password_hash'] = hash_password(np1)
            guardar_usuarios(usuarios_actuales)
            st.success(f"✅ Contraseña de **{usr_c}** actualizada.")

    st.markdown("---")
    st.markdown("### ➕ Añadir nuevo usuario")
    c1, c2 = st.columns(2)
    with c1:
        nu_user = st.text_input("Nombre de usuario", placeholder="ej: usuario1", key="nu_user")
        nu_name = st.text_input("Nombre completo",   placeholder="ej: Ana Pérez", key="nu_name")
    with c2:
        nu_pass = st.text_input("Contraseña", type="password", key="nu_pass")
        nu_rol  = st.selectbox("Rol", options=["usuario","admin"], key="nu_rol")
    if st.button("➕ Crear usuario", use_container_width=True):
        nu = nu_user.strip()
        if not nu:                                    st.error("El nombre de usuario no puede estar vacío.")
        elif nu in usuarios_actuales:                 st.error(f"El usuario **{nu}** ya existe.")
        elif not nu_pass:                             st.error("La contraseña no puede estar vacía.")
        elif len(nu_pass) < 6:                        st.error("Mínimo 6 caracteres.")
        elif not re.match(r'^[a-zA-Z0-9_\-\.]+$', nu): st.error("Solo letras, números, guiones y puntos.")
        else:
            usuarios_actuales[nu] = {
                "password_hash": hash_password(nu_pass),
                "nombre": nu_name.strip() or nu,
                "rol": nu_rol
            }
            guardar_usuarios(usuarios_actuales)
            st.success(f"✅ Usuario **{nu}** creado.")
            st.rerun()


# ============================================================================
# MAIN: navegación con st.navigation (igual que la segunda app)
# ============================================================================

def main():
    # Cabecera del sidebar: usuario + botón cerrar sesión
    with st.sidebar:
        usuarios = cargar_usuarios()
        nombre_mostrar = usuarios.get(st.session_state.usuario_actual, {}).get('nombre', st.session_state.usuario_actual)
        st.markdown(f"👤 **{nombre_mostrar}**")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            for k in list(defaults.keys()):
                st.session_state[k] = defaults[k]
            st.rerun()
        st.markdown("---")

    # Definición de páginas (mismo patrón que la segunda app)
    p_nueva     = st.Page(pagina_nueva_revision,    title="Nueva Revisión",      icon="📄", default=True)
    p_revisiones = st.Page(pagina_mis_revisiones,   title="Mis Revisiones",      icon="📁")
    p_usuarios  = st.Page(pagina_gestion_usuarios,  title="Gestión de Usuarios", icon="⚙️")

    pg = st.navigation({
        "RPT – Gestor de Efectivos": [p_nueva, p_revisiones],
        "Administración":            [p_usuarios],
    })

    pg.run()


if __name__ == "__main__":
    main()
