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

# Archivo donde se guardan los usuarios
USUARIOS_FILE = BASE_DIR / "usuarios.json"

# ============================================================================
# GESTIÓN DE USUARIOS
# ============================================================================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def cargar_usuarios() -> dict:
    """Carga usuarios desde el archivo JSON. Si no existe, crea uno por defecto."""
    if USUARIOS_FILE.exists():
        try:
            with open(USUARIOS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    # Usuarios por defecto
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
    """Guarda el diccionario de usuarios en disco."""
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
    'mostrar_config_usuarios': False,
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

    /* ── Header ─────────────────────────────────────────────────────── */
    header[data-testid="stHeader"] {
        border-bottom: 4px solid var(--verde-junta);
        padding: 0.5rem;
    }
    header::after { display: none !important; }
    header img { max-height: 60px !important; object-fit: contain; }

    /* ── Sidebar (siempre verde) ───────────────────────────────────── */
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

    /* ── Collapsed control ─────────────────────────────────────────── */
    [data-testid="collapsedControl"] { border-radius: 4px; }

    /* ── General ───────────────────────────────────────────────────── */
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

    /* ── Login page ────────────────────────────────────────────────── */
    .login-container {
        max-width: 420px;
        margin: 4rem auto;
        padding: 2.5rem 2rem;
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 4px 24px rgba(11, 110, 60, 0.12);
        border-top: 5px solid var(--verde-junta);
    }
    .login-title {
        text-align: center;
        color: var(--verde-junta);
        font-size: 1.6rem;
        font-weight: 700;
        margin-bottom: 0.3rem;
    }
    .login-subtitle {
        text-align: center;
        color: #666;
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# PANTALLA DE LOGIN
# ============================================================================
def mostrar_login():
    # Ocultamos sidebar en el login
    st.markdown("""
        <style>
        section[data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"]  { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

    # Banner si existe
    try:
        if HEADER_MAIN_FILE.exists():
            col_l, col_c, col_r = st.columns([1, 2, 1])
            with col_c:
                st.image(str(HEADER_MAIN_FILE), use_container_width=True)
    except Exception:
        pass

    st.markdown("""
        <div class="login-container">
            <div class="login-title">🔐 Acceso al Sistema</div>
            <div class="login-subtitle">RPT – Gestor de Efectivos</div>
        </div>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 1.4, 1])
    with col_c:
        with st.container():
            st.markdown("#### Iniciar Sesión")
            username = st.text_input("👤 Usuario", placeholder="Introduce tu usuario", key="login_user")
            password = st.text_input("🔑 Contraseña", type="password", placeholder="Introduce tu contraseña", key="login_pass")

            if st.button("Entrar →", type="primary", use_container_width=True):
                if username.strip() == "":
                    st.error("Por favor, introduce tu usuario.")
                elif password == "":
                    st.error("Por favor, introduce tu contraseña.")
                elif verificar_credenciales(username.strip(), password):
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = username.strip()
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")

# Si no está autenticado, mostramos login y detenemos la ejecución
if not st.session_state.autenticado:
    mostrar_login()
    st.stop()

# ============================================================================
# A PARTIR DE AQUÍ: USUARIO AUTENTICADO
# ============================================================================

# --- Banner principal ---
try:
    if HEADER_MAIN_FILE.exists():
        st.image(str(HEADER_MAIN_FILE), width='stretch')
except Exception:
    pass

# ============================================================================
# FUNCIONES DE REVISIONES (almacenamiento local en servidor)
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
        if modo in ('PC', 'PLD', 'PCE'):
            return modo
        elif modo.startswith('RD'):
            return 'RD (Art.7.1.A)'
        elif modo.startswith('D.') or modo.startswith('/'):
            return 'DTO 2/2002'
        return modo
    match_pld_ax = re.search(r'1F\s+(PLD)\s+AX\s+[A-E]\d', linea)
    if match_pld_ax:
        return 'PLD'
    match_laboral = re.search(r'1L\s+([A-Z]{1,3}(?:,\w+)?)\s+[IVX]+\s', linea)
    if match_laboral:
        modo = match_laboral.group(1).strip()
        if modo == 'S,PC':
            return 'PC,S'
        return modo
    match2 = re.search(r'\d{6,8}\s*[A-ZÁÉÍÓÚÑ][^\d]*?\s+(\d+)\s+(\d+)\s+([A-E]\d)', linea)
    if not match2:
        match3 = re.search(r'\.+\s+([A-E]\d(?:-[A-E]\d)?)\s*(P-[A-E]\d+)', linea)
        if match3:
            match_modo = re.search(r'\s(PC|PLD|PCE)\s', linea)
            if match_modo:
                return match_modo.group(1)
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
# SIDEBAR
# ============================================================================
with st.sidebar:

    # ── Usuario actual + cerrar sesión ─────────────────────────────────
    usuarios = cargar_usuarios()
    nombre_mostrar = usuarios.get(st.session_state.usuario_actual, {}).get('nombre', st.session_state.usuario_actual)
    st.markdown(f"👤 **{nombre_mostrar}**")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.session_state.usuario_actual = None
        st.session_state.comparacion_ejecutada = False
        st.session_state.archivos_procesados = None
        st.session_state.dataframes_procesados = None
        st.session_state.info_archivos = None
        st.session_state.revision_activa = None
        st.session_state.revision_activa_path = None
        st.rerun()

    st.markdown("---")

    # ── Revisiones Guardadas ────────────────────────────────────────────
    st.markdown("## 📁 Revisiones Guardadas")
    revisiones = listar_revisiones()

    if not revisiones:
        st.info("No hay revisiones guardadas aún.")
    else:
        for carpeta_rev in revisiones:
            if st.session_state.renombrando == str(carpeta_rev):
                nuevo_nombre = st.text_input(
                    "Nuevo nombre",
                    value=carpeta_rev.name,
                    key=f"input_rename_{carpeta_rev.name}",
                    label_visibility="collapsed"
                )
                col_ok, col_cancel = st.columns(2)
                with col_ok:
                    if st.button("✅", key=f"ok_{carpeta_rev.name}", help="Confirmar"):
                        if nuevo_nombre.strip() and nuevo_nombre.strip() != carpeta_rev.name:
                            nueva_carpeta = renombrar_revision(carpeta_rev, nuevo_nombre.strip())
                            if st.session_state.revision_activa == carpeta_rev.name:
                                st.session_state.revision_activa = nueva_carpeta.name
                                st.session_state.revision_activa_path = str(nueva_carpeta)
                        st.session_state.renombrando = None
                        st.rerun()
                with col_cancel:
                    if st.button("❌", key=f"cancel_{carpeta_rev.name}", help="Cancelar"):
                        st.session_state.renombrando = None
                        st.rerun()
            else:
                fecha_mod = datetime.fromtimestamp(carpeta_rev.stat().st_mtime).strftime('%d/%m/%Y')
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    es_activa = st.session_state.revision_activa == carpeta_rev.name
                    label = f"{'▶ ' if es_activa else '📂 '}{carpeta_rev.name}"
                    if st.button(label, key=f"rev_{carpeta_rev.name}", help=fecha_mod):
                        dfs_cache, info_cache = cargar_cache(carpeta_rev)
                        archivos = cargar_revision(carpeta_rev)
                        if len(archivos) >= 1:
                            st.session_state.archivos_procesados = archivos
                            st.session_state.comparacion_ejecutada = True
                            st.session_state.revision_activa = carpeta_rev.name
                            st.session_state.revision_activa_path = str(carpeta_rev)
                            if dfs_cache is not None:
                                st.session_state.dataframes_procesados = dfs_cache
                                st.session_state.info_archivos = info_cache
                            else:
                                st.session_state.dataframes_procesados = None
                                st.session_state.info_archivos = None
                            st.rerun()
                        else:
                            st.warning("Esta revisión no tiene PDFs.")
                with col2:
                    if st.button("✏️", key=f"ren_{carpeta_rev.name}", help="Renombrar"):
                        st.session_state.renombrando = str(carpeta_rev)
                        st.rerun()
                with col3:
                    if st.button("🗑️", key=f"del_{carpeta_rev.name}", help="Eliminar revisión"):
                        st.session_state.confirmando_borrar = str(carpeta_rev)
                        st.rerun()

            if st.session_state.confirmando_borrar == str(carpeta_rev):
                st.warning(f"⚠️ ¿Eliminar **{carpeta_rev.name}**?")
                col_si, col_no = st.columns(2)
                with col_si:
                    if st.button("✅ Sí, eliminar", key=f"confirm_del_{carpeta_rev.name}"):
                        eliminar_revision(carpeta_rev)
                        if st.session_state.revision_activa == carpeta_rev.name:
                            st.session_state.comparacion_ejecutada = False
                            st.session_state.archivos_procesados = None
                            st.session_state.dataframes_procesados = None
                            st.session_state.info_archivos = None
                            st.session_state.revision_activa = None
                            st.session_state.revision_activa_path = None
                        st.session_state.confirmando_borrar = None
                        st.rerun()
                with col_no:
                    if st.button("❌ Cancelar", key=f"cancel_del_{carpeta_rev.name}"):
                        st.session_state.confirmando_borrar = None
                        st.rerun()

    st.markdown("---")
    if st.button("🔄 Nueva Revisión"):
        st.session_state.archivos_procesados = None
        st.session_state.comparacion_ejecutada = False
        st.session_state.dataframes_procesados = None
        st.session_state.info_archivos = None
        st.session_state.revision_activa = None
        st.session_state.revision_activa_path = None
        st.rerun()

    # ── Configuración de Usuarios ───────────────────────────────────────
    st.markdown("---")
    st.markdown("## ⚙️ Configuración")

    toggle_label = "🔒 Cerrar Gestión de Usuarios" if st.session_state.mostrar_config_usuarios else "👥 Gestionar Usuarios"
    if st.button(toggle_label):
        st.session_state.mostrar_config_usuarios = not st.session_state.mostrar_config_usuarios
        st.rerun()

# ============================================================================
# PANEL DE GESTIÓN DE USUARIOS (se muestra en el área principal si está activo)
# ============================================================================
if st.session_state.mostrar_config_usuarios:
    st.markdown("## ⚙️ Configuración de Usuarios")
    st.markdown("Gestiona los usuarios que tienen acceso a la aplicación.")
    st.markdown("---")

    usuarios_actuales = cargar_usuarios()

    # ── Tabla de usuarios existentes ────────────────────────────────────
    st.markdown("### 👥 Usuarios registrados")

    for uname, udata in list(usuarios_actuales.items()):
        col_u, col_n, col_r, col_del = st.columns([2, 2, 1, 1])
        with col_u:
            st.markdown(f"**`{uname}`**")
        with col_n:
            st.markdown(udata.get('nombre', '—'))
        with col_r:
            rol_icon = "🔑" if udata.get('rol') == 'admin' else "👤"
            st.markdown(f"{rol_icon} {udata.get('rol', 'usuario')}")
        with col_del:
            # No permitir eliminar el propio usuario ni el último admin
            admins = [u for u, d in usuarios_actuales.items() if d.get('rol') == 'admin']
            puede_borrar = not (uname == st.session_state.usuario_actual or (udata.get('rol') == 'admin' and len(admins) <= 1))
            if puede_borrar:
                if st.button("🗑️", key=f"del_user_{uname}", help=f"Eliminar {uname}"):
                    del usuarios_actuales[uname]
                    guardar_usuarios(usuarios_actuales)
                    st.success(f"Usuario **{uname}** eliminado.")
                    st.rerun()
            else:
                st.markdown("—")

    st.markdown("---")

    # ── Cambiar contraseña de un usuario existente ──────────────────────
    st.markdown("### 🔑 Cambiar contraseña")
    with st.container():
        col_a, col_b = st.columns(2)
        with col_a:
            usuario_cambio = st.selectbox(
                "Usuario",
                options=list(usuarios_actuales.keys()),
                key="cambio_pass_user"
            )
        with col_b:
            nueva_pass = st.text_input("Nueva contraseña", type="password", key="nueva_pass_input")

        confirmar_pass = st.text_input("Confirmar contraseña", type="password", key="confirmar_pass_input")

        if st.button("💾 Guardar nueva contraseña", use_container_width=True):
            if not nueva_pass:
                st.error("La contraseña no puede estar vacía.")
            elif nueva_pass != confirmar_pass:
                st.error("Las contraseñas no coinciden.")
            elif len(nueva_pass) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
            else:
                usuarios_actuales[usuario_cambio]['password_hash'] = hash_password(nueva_pass)
                guardar_usuarios(usuarios_actuales)
                st.success(f"✅ Contraseña de **{usuario_cambio}** actualizada correctamente.")

    st.markdown("---")

    # ── Añadir nuevo usuario ─────────────────────────────────────────────
    st.markdown("### ➕ Añadir nuevo usuario")
    with st.container():
        col_1, col_2 = st.columns(2)
        with col_1:
            nuevo_username = st.text_input("Nombre de usuario", placeholder="ej: usuario1", key="nuevo_user")
            nuevo_nombre = st.text_input("Nombre completo", placeholder="ej: Juan García", key="nuevo_nombre")
        with col_2:
            nuevo_password = st.text_input("Contraseña", type="password", key="nuevo_password")
            nuevo_rol = st.selectbox("Rol", options=["usuario", "admin"], key="nuevo_rol")

        if st.button("➕ Crear usuario", use_container_width=True):
            nu = nuevo_username.strip()
            if not nu:
                st.error("El nombre de usuario no puede estar vacío.")
            elif nu in usuarios_actuales:
                st.error(f"El usuario **{nu}** ya existe.")
            elif not nuevo_password:
                st.error("La contraseña no puede estar vacía.")
            elif len(nuevo_password) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
            elif not re.match(r'^[a-zA-Z0-9_\-\.]+$', nu):
                st.error("El nombre de usuario solo puede contener letras, números, guiones y puntos.")
            else:
                usuarios_actuales[nu] = {
                    "password_hash": hash_password(nuevo_password),
                    "nombre": nuevo_nombre.strip() or nu,
                    "rol": nuevo_rol
                }
                guardar_usuarios(usuarios_actuales)
                st.success(f"✅ Usuario **{nu}** creado correctamente.")
                st.rerun()

    st.markdown("---")
    st.stop()   # No mostramos el resto de la app mientras estamos en config

# ============================================================================
# PANTALLA DE CARGA
# ============================================================================
if not st.session_state.comparacion_ejecutada:

    st.markdown("""
        <div style="text-align:center; margin: 2rem 0">
            <div style="font-size:2.5rem; font-weight:700">👥 Gestor de Efectivos RPT</div>
            <div style="font-size:1.1rem; opacity:0.7; margin-top:0.5rem">Analiza un PDF individualmente o compara varios simultáneamente</div>
            <div style="font-size:0.95rem; opacity:0.7; font-weight:500">1 archivo → Revisión individual &nbsp;·&nbsp; 2 o más archivos → Comparación evolutiva</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("### 📝 Nombre de la Revisión")
    nombre_revision = st.text_input(
        "Ponle un nombre a esta revisión",
        placeholder="Ej: Revisión Marzo-Febrero 2026",
        label_visibility="collapsed"
    )

    st.markdown("### 📁 Cargar Archivos PDF")
    st.info("💡 **Tip:** Con 1 PDF puedes hacer una revisión individual con filtros completos. Con 2 o más, los archivos se ordenan automáticamente por fecha para mostrar la evolución cronológica.")

    archivos_subidos = st.file_uploader(
        "Arrastra aquí tus archivos PDF (puedes seleccionar varios a la vez)",
        type=['pdf'],
        accept_multiple_files=True,
        key='uploader_multi',
        label_visibility="collapsed"
    )

    if archivos_subidos and len(archivos_subidos) >= 1:
        st.success(f"✅ **{len(archivos_subidos)} {'archivo cargado' if len(archivos_subidos) == 1 else 'archivos cargados'}**")
        st.markdown(f"### 📋 {'Archivo a revisar:' if len(archivos_subidos) == 1 else 'Archivos que se compararán:'}")
        for i, archivo in enumerate(archivos_subidos, 1):
            st.markdown(f"{i}. 📄 **{archivo.name}** ({archivo.size / 1024:.1f} KB)")
        st.markdown("---")

        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        with col_btn2:
            btn_label = "🔍 Analizar y Guardar" if len(archivos_subidos) == 1 else "🔍 Comparar y Guardar"
            if st.button(btn_label, type="primary", use_container_width=True):

                if not nombre_revision.strip():
                    dias_es = {'Monday':'Lunes','Tuesday':'Martes','Wednesday':'Miércoles','Thursday':'Jueves','Friday':'Viernes','Saturday':'Sábado','Sunday':'Domingo'}
                    try:
                        from zoneinfo import ZoneInfo
                        ahora = datetime.now(ZoneInfo('Europe/Madrid'))
                    except Exception:
                        ahora = datetime.now(timezone(timedelta(hours=1)))
                    dia_semana = dias_es.get(ahora.strftime('%A'), ahora.strftime('%A'))
                    nombre_revision = f"Revisión de {ahora.strftime('%d/%m/%Y %H:%M')} {dia_semana}"

                archivos_lista = []
                nombres_vistos = {}

                for archivo in archivos_subidos:
                    try:
                        contenido_bytes = archivo.read()
                        if len(contenido_bytes) == 0:
                            st.warning(f"Archivo vacío: {archivo.name}")
                            continue
                        nombre_base = archivo.name
                        if nombre_base in nombres_vistos:
                            nombres_vistos[nombre_base] += 1
                            ext_idx = nombre_base.rfind('.')
                            if ext_idx > 0:
                                nombre_unico = nombre_base[:ext_idx] + f"_{nombres_vistos[nombre_base]}" + nombre_base[ext_idx:]
                            else:
                                nombre_unico = nombre_base + f"_{nombres_vistos[nombre_base]}"
                        else:
                            nombres_vistos[nombre_base] = 1
                            nombre_unico = nombre_base
                        archivos_lista.append((nombre_unico, contenido_bytes))
                    except Exception as e:
                        st.warning(f"Error leyendo {archivo.name}: {e}")

                if len(archivos_lista) >= 1:
                    try:
                        guardar_revision(nombre_revision, archivos_lista)
                        st.success(f"✅ Revisión '{nombre_revision}' guardada correctamente")
                    except Exception as e:
                        st.warning(f"⚠️ No se pudo guardar la revisión: {e}")

                    st.session_state.archivos_procesados = archivos_lista
                    st.session_state.comparacion_ejecutada = True
                    st.session_state.revision_activa = nombre_revision.strip()
                    nombre_limpio = re.sub(r'[<>:"/\\|?*]', '_', nombre_revision.strip())
                    st.session_state.revision_activa_path = str(CARPETA_REVISIONES / nombre_limpio)
                    st.rerun()
                else:
                    st.error("❌ No se pudo leer ningún archivo válido.")

    else:
        st.info("👆 Carga 1 PDF para revisión individual, o 2 o más para comparar versiones")


# ============================================================================
# PANTALLA DE RESULTADOS
# ============================================================================
if st.session_state.comparacion_ejecutada and st.session_state.archivos_procesados:

    if st.session_state.revision_activa:
        st.title(f"📂 {st.session_state.revision_activa}")
    else:
        st.title("RPT: Análisis de Archivos")
    st.markdown("---")

    if st.session_state.dataframes_procesados is None:
        with st.spinner('🔄 Procesando y ordenando archivos cronológicamente...'):
            archivos_ordenados = ordenar_archivos_por_fecha(st.session_state.archivos_procesados)
            dataframes_procesados = []
            info_archivos = []

            st.markdown("### 📊 Progreso de Procesamiento")

            for i, (nombre, archivo_bytes, fecha) in enumerate(archivos_ordenados):
                st.markdown(f"**Procesando archivo {i+1}/{len(archivos_ordenados)}:** {nombre}")
                df = procesar_pdf(archivo_bytes, nombre)
                if not df.empty:
                    dataframes_procesados.append(df)
                    info_archivos.append({
                        'nombre':       nombre,
                        'fecha':        fecha,
                        'total_plazas': len(df),
                        'dotadas':      len(df[df['Dotación'] == 'DOTADA']),
                        'no_dotadas':   len(df[df['Dotación'] == 'NO DOTADA']),
                        'ocupadas':     len(df[df['Estado_Plaza'] == 'OCUPADA']),
                        'libres':       len(df[df['Estado_Plaza'] == 'VACANTE'])
                    })
                else:
                    st.error(f"⚠️ No se pudieron extraer datos de {nombre}")

            st.markdown("---")

        if len(dataframes_procesados) >= 2:
            st.success(f"✅ PDFs procesados correctamente")

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

    if len(dataframes_procesados) >= 1:
        with st.expander("🔗 Enriquecer Datos (Relacionar códigos con nombres)", expanded=False):
            st.markdown("**Si tienes un archivo con nombres que falta agregar a los códigos, cárgalo aquí:**")

            archivo_enriquecimiento = st.file_uploader(
                "Selecciona un PDF con nombres de ocupantes para enriquecer los datos",
                type=['pdf'],
                key='uploader_enriquecimiento',
                label_visibility="collapsed"
            )

            if archivo_enriquecimiento:
                if st.button("🔗 Relacionar Datos", type="secondary", use_container_width=True):
                    try:
                        contenido_bytes = archivo_enriquecimiento.read()
                        df_nombres = procesar_pdf(contenido_bytes, archivo_enriquecimiento.name)

                        if not df_nombres.empty:
                            dataframes_enriquecidos = []
                            for df in dataframes_procesados:
                                df_enriquecido = enriquecer_dataframe_con_nombres(df, df_nombres)
                                dataframes_enriquecidos.append(df_enriquecido)

                            st.session_state.dataframes_procesados = dataframes_enriquecidos
                            st.rerun()
                        else:
                            st.error("❌ No se pudo extraer información del archivo de nombres.")
                    except Exception as e:
                        st.error(f"❌ Error procesando el archivo: {e}")

    if len(dataframes_procesados) == 1:
        df_solo = dataframes_procesados[0]
        info_solo = info_archivos[0]

        if info_solo.get('fecha') and info_solo['fecha'] != 'Sin fecha':
            st.caption(f"📅 Fecha del archivo: **{info_solo['fecha']}**")

        modos_disponibles = sorted([m for m in df_solo['Modo_Acceso'].unique() if pd.notna(m)])
        tiene_modo_acceso = len(modos_disponibles) > 0

        st.markdown("#### 🔎 Filtros")
        cf1, cf2, cf3, cf4 = st.columns(4)
        with cf1:
            f_prov = st.multiselect("Provincia", options=sorted([p for p in df_solo['Provincia'].unique() if p != 'NO ESPECIFICADA']), key="solo_prov")
        with cf2:
            f_grupo = st.multiselect("Grupo", options=sorted([g for g in df_solo['Grupo'].unique() if pd.notna(g)]), key="solo_grupo")
        with cf3:
            if tiene_modo_acceso:
                f_modo = st.multiselect("Modo Acceso", options=modos_disponibles, key="solo_modo")
            else:
                f_dot = st.multiselect("Dotación", options=['DOTADA', 'NO DOTADA'], key="solo_dot")
        with cf4:
            if tiene_modo_acceso:
                ads_disponibles = sorted([a for a in df_solo['ADS'].unique() if pd.notna(a)])
                f_ads = st.multiselect("ADS", options=ads_disponibles, key="solo_ads")
            else:
                f_est = st.multiselect("Estado", options=df_solo['Estado_Plaza'].unique(), key="solo_est")

        df_f = df_solo.copy()
        if f_prov:  df_f = df_f[df_f['Provincia'].isin(f_prov)]
        if f_grupo: df_f = df_f[df_f['Grupo'].isin(f_grupo)]
        if tiene_modo_acceso:
            if f_modo:  df_f = df_f[df_f['Modo_Acceso'].isin(f_modo)]
            if f_ads:   df_f = df_f[df_f['ADS'].isin(f_ads)]
        else:
            if f_dot:   df_f = df_f[df_f['Dotación'].isin(f_dot)]
            if f_est:   df_f = df_f[df_f['Estado_Plaza'].isin(f_est)]

        st.markdown("### 📊 Resumen")
        if tiene_modo_acceso:
            st.metric("Total Plazas", len(df_f))
        else:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Plazas", len(df_f))
            col2.metric("Ocupadas",     len(df_f[df_f['Estado_Plaza'] == 'OCUPADA']))
            col3.metric("Vacantes",     len(df_f[df_f['Estado_Plaza'] == 'VACANTE']))
            col4.metric("Dotadas",      len(df_f[df_f['Dotación'] == 'DOTADA']))
        st.markdown("---")

        if tiene_modo_acceso:
            cols_tabla = ['Código','Denominación','ADS','Modo_Acceso','Grupo','Cuerpo','Provincia','Localidad']
        else:
            cols_tabla = ['Código','Denominación','Grupo','Cuerpo','Provincia','Localidad','Carácter','Dotación','Estado_Plaza','Ocupante']

        st.dataframe(df_f[cols_tabla], width='stretch', height=500)
        st.caption(f"Mostrando {len(df_f)} de {len(df_solo)} plazas")

    elif len(dataframes_procesados) >= 2:

        st.markdown("### 📊 Resumen General")
        total_plazas_base  = len(dataframes_procesados[0])
        total_plazas_final = len(dataframes_procesados[-1])
        diferencia = total_plazas_final - total_plazas_base

        col1, col2, col3 = st.columns(3)
        col1.metric("Plazas Iniciales",   total_plazas_base,  help=f"Archivo: {info_archivos[0]['nombre']}")
        col2.metric("Plazas Finales",     total_plazas_final, delta=diferencia, help=f"Archivo: {info_archivos[-1]['nombre']}")
        col3.metric("Total de Versiones", len(dataframes_procesados))
        st.markdown("---")

        st.markdown("## 🔀 Comparaciones Detalladas Entre Versiones")

        nombres_comparaciones = []
        for i in range(len(info_archivos) - 1):
            n1 = info_archivos[i]['nombre'][:15] + ("..." if len(info_archivos[i]['nombre']) > 15 else "")
            n2 = info_archivos[i+1]['nombre'][:15] + ("..." if len(info_archivos[i+1]['nombre']) > 15 else "")
            nombres_comparaciones.append(f"{n1} → {n2}")

        tabs_comparacion = st.tabs(nombres_comparaciones)

        for idx, tab in enumerate(tabs_comparacion):
            with tab:
                df_old = dataframes_procesados[idx]
                df_new = dataframes_procesados[idx + 1]

                col_comp1, col_comp2 = st.columns(2)
                with col_comp1:
                    st.info(f"**📋 Versión Anterior**\n\n{info_archivos[idx]['nombre']}\n\n📅 {info_archivos[idx]['fecha']}")
                with col_comp2:
                    st.success(f"**📋 Versión Nueva**\n\n{info_archivos[idx+1]['nombre']}\n\n📅 {info_archivos[idx+1]['fecha']}")

                df_comp = pd.merge(df_old, df_new, on='Código', how='outer', suffixes=('_ANT','_ACT'), indicator=True)

                def det_estado_comp(row):
                    if row['_merge'] == 'left_only':  return '❌ ELIMINADA'
                    if row['_merge'] == 'right_only': return '🆕 NUEVA'
                    dot_ant = str(row.get('Dotación_ANT', ''))
                    dot_act = str(row.get('Dotación_ACT', ''))
                    ocu_ant = str(row.get('Ocupante_ANT', ''))
                    ocu_act = str(row.get('Ocupante_ACT', ''))
                    cambio_dot = dot_ant != dot_act and dot_ant != 'nan' and dot_act != 'nan'
                    cambio_ocu = ocu_ant != ocu_act
                    if cambio_dot and cambio_ocu: return '🔄 CAMBIO OCUPANTE + DOTACIÓN'
                    if cambio_dot:  return '💰 CAMBIO DOTACIÓN'
                    if cambio_ocu:  return '🔄 CAMBIO OCUPANTE'
                    return '✅ SIN CAMBIOS'

                df_comp['Situación']          = df_comp.apply(det_estado_comp, axis=1)
                df_comp['Denominación']       = df_comp['Denominación_ACT'].fillna(df_comp['Denominación_ANT'])
                df_comp['Grupo']              = df_comp['Grupo_ACT'].fillna(df_comp['Grupo_ANT'])
                df_comp['Cuerpo']             = df_comp['Cuerpo_ACT'].fillna(df_comp['Cuerpo_ANT'])
                df_comp['Provincia']          = df_comp['Provincia_ACT'].fillna(df_comp['Provincia_ANT'])
                df_comp['Localidad']          = df_comp['Localidad_ACT'].fillna(df_comp['Localidad_ANT'])
                df_comp['Modo_Acceso']        = df_comp['Modo_Acceso_ACT'].fillna(df_comp['Modo_Acceso_ANT'])
                df_comp['Ocupante Anterior']  = df_comp['Ocupante_ANT'].fillna('-')
                df_comp['Ocupante Actual']    = df_comp['Ocupante_ACT'].fillna('-')
                df_comp['Dotación Anterior']  = df_comp['Dotación_ANT'].fillna('-')
                df_comp['Dotación Actual']    = df_comp['Dotación_ACT'].fillna('-')
                df_comp['Dotación']           = df_comp['Dotación_ACT'].fillna(df_comp['Dotación_ANT'])
                df_comp['Estado']             = df_comp['Estado_Plaza_ACT'].fillna(df_comp['Estado_Plaza_ANT'])

                nuevas        = len(df_comp[df_comp['Situación'] == '🆕 NUEVA'])
                eliminadas    = len(df_comp[df_comp['Situación'] == '❌ ELIMINADA'])
                cambios_ocu   = len(df_comp[df_comp['Situación'] == '🔄 CAMBIO OCUPANTE'])
                cambios_dot   = len(df_comp[df_comp['Situación'] == '💰 CAMBIO DOTACIÓN'])

                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("🆕 Nuevas",         nuevas,     delta=f"+{nuevas}")
                col_m2.metric("❌ Eliminadas",      eliminadas, delta=f"-{eliminadas}")
                col_m3.metric("🔄 Cambio Ocupante", cambios_ocu)
                col_m4.metric("💰 Cambio Dotación", cambios_dot)
                st.markdown("---")

                st.markdown("#### 🔎 Filtros")
                cf1, cf2, cf3, cf4, cf5 = st.columns(5)
                with cf1:
                    comp_filtro_prov = st.multiselect("Provincia", options=sorted([p for p in df_comp['Provincia'].dropna().unique() if p != 'NO ESPECIFICADA']), key=f"comp_prov_{idx}")
                with cf2:
                    comp_filtro_grupo = st.multiselect("Grupo", options=sorted([g for g in df_comp['Grupo'].dropna().unique()]), key=f"comp_grupo_{idx}")
                with cf3:
                    comp_filtro_dot = st.multiselect("Dotación", options=['DOTADA', 'NO DOTADA'], key=f"comp_dot_{idx}")
                with cf4:
                    comp_filtro_estado = st.multiselect("Estado Plaza", options=sorted(df_comp['Estado'].dropna().unique()), key=f"comp_estado_{idx}")
                with cf5:
                    modos_comp = sorted([m for m in df_comp['Modo_Acceso'].dropna().unique()])
                    comp_filtro_modo = st.multiselect("Modo Acceso", options=modos_comp, key=f"comp_modo_{idx}")

                df_comp_filtrado = df_comp.copy()
                if comp_filtro_prov:   df_comp_filtrado = df_comp_filtrado[df_comp_filtrado['Provincia'].isin(comp_filtro_prov)]
                if comp_filtro_grupo:  df_comp_filtrado = df_comp_filtrado[df_comp_filtrado['Grupo'].isin(comp_filtro_grupo)]
                if comp_filtro_dot:    df_comp_filtrado = df_comp_filtrado[df_comp_filtrado['Dotación'].isin(comp_filtro_dot)]
                if comp_filtro_estado: df_comp_filtrado = df_comp_filtrado[df_comp_filtrado['Estado'].isin(comp_filtro_estado)]
                if comp_filtro_modo:   df_comp_filtrado = df_comp_filtrado[df_comp_filtrado['Modo_Acceso'].isin(comp_filtro_modo)]

                nuevas_f      = len(df_comp_filtrado[df_comp_filtrado['Situación'] == '🆕 NUEVA'])
                eliminadas_f  = len(df_comp_filtrado[df_comp_filtrado['Situación'] == '❌ ELIMINADA'])
                cambios_ocu_f = len(df_comp_filtrado[df_comp_filtrado['Situación'] == '🔄 CAMBIO OCUPANTE'])
                cambios_dot_f = len(df_comp_filtrado[df_comp_filtrado['Situación'] == '💰 CAMBIO DOTACIÓN'])

                if any([comp_filtro_prov, comp_filtro_grupo, comp_filtro_dot, comp_filtro_estado, comp_filtro_modo]):
                    st.caption(f"🔎 Filtro activo — mostrando {len(df_comp_filtrado)} de {len(df_comp)} plazas "
                            f"| +{nuevas_f} nuevas | -{eliminadas_f} eliminadas "
                            f"| {cambios_ocu_f} cambio ocupante | {cambios_dot_f} cambio dotación")

                st.markdown("---")

                MAX_TAB = 20
                nombre_ant_corto = info_archivos[idx]['nombre']
                nombre_act_corto = info_archivos[idx+1]['nombre']
                tab_ant = (f"📄 {nombre_ant_corto[:MAX_TAB]}..." if len(nombre_ant_corto) > MAX_TAB else f"📄 {nombre_ant_corto}")
                tab_act = (f"📄 {nombre_act_corto[:MAX_TAB]}..." if len(nombre_act_corto) > MAX_TAB else f"📄 {nombre_act_corto}")

                (
                    sub_tab_todos, sub_tab_nuevas, sub_tab_eliminadas,
                    sub_tab_cambios, sub_tab_dot,
                    sub_tab_pdf_ant, sub_tab_pdf_act,
                ) = st.tabs([
                    "🔍 TODOS", "🆕 Nuevas", "❌ Eliminadas",
                    "🔄 Cambio Ocupante", "💰 Cambio Dotación",
                    tab_ant, tab_act,
                ])

                cols_mostrar = [
                    'Código', 'Denominación', 'Modo_Acceso', 'Grupo', 'Cuerpo', 'Provincia', 'Localidad', 'Situación',
                    'Dotación Anterior', 'Dotación Actual', 'Estado',
                    'Ocupante Anterior', 'Ocupante Actual'
                ]

                def color_rows(val):
                    if val == '❌ ELIMINADA':                    return 'background-color: #ffebee'
                    elif val == '🆕 NUEVA':                      return 'background-color: #e8f5e9'
                    elif val == '🔄 CAMBIO OCUPANTE':            return 'background-color: #fffde7'
                    elif val == '💰 CAMBIO DOTACIÓN':            return 'background-color: #e3f2fd'
                    elif val == '🔄 CAMBIO OCUPANTE + DOTACIÓN': return 'background-color: #f3e5f5'
                    elif val == '✅ SIN CAMBIOS':                return 'background-color: #f1f8f4'
                    return 'background-color: white'

                with sub_tab_todos:
                    st.dataframe(df_comp_filtrado[cols_mostrar].style.map(color_rows, subset=['Situación']), width='stretch', height=500)
                    st.caption(f"Total: {len(df_comp_filtrado)} plazas")

                with sub_tab_nuevas:
                    df_n = df_comp_filtrado[df_comp_filtrado['Situación'] == '🆕 NUEVA']
                    st.dataframe(df_n[cols_mostrar], width='stretch', height=500)
                    st.caption(f"Total: {len(df_n)} plazas nuevas")

                with sub_tab_eliminadas:
                    df_e = df_comp_filtrado[df_comp_filtrado['Situación'] == '❌ ELIMINADA']
                    st.dataframe(df_e[cols_mostrar], width='stretch', height=500)
                    st.caption(f"Total: {len(df_e)} plazas eliminadas")

                with sub_tab_cambios:
                    df_c = df_comp_filtrado[df_comp_filtrado['Situación'] == '🔄 CAMBIO OCUPANTE']
                    st.dataframe(df_c[cols_mostrar], width='stretch', height=500)
                    st.caption(f"Total: {len(df_c)} plazas con cambio de ocupante")

                with sub_tab_dot:
                    df_d = df_comp_filtrado[df_comp_filtrado['Situación'] == '💰 CAMBIO DOTACIÓN']
                    st.dataframe(df_d[cols_mostrar], width='stretch', height=500)
                    st.caption(f"Total: {len(df_d)} plazas con cambio de dotación")

                with sub_tab_pdf_ant:
                    st.markdown(f"#### {info_archivos[idx]['nombre']}")
                    st.caption(f"📅 Fecha: {info_archivos[idx]['fecha']}")
                    cf1, cf2, cf3, cf4 = st.columns(4)
                    with cf1:
                        f_prov = st.multiselect("Provincia", options=sorted([p for p in df_old['Provincia'].unique() if p != 'NO ESPECIFICADA']), key=f"pdf1_prov_{idx}")
                    with cf2:
                        f_grupo = st.multiselect("Grupo", options=sorted([g for g in df_old['Grupo'].unique() if pd.notna(g)]), key=f"pdf1_grupo_{idx}")
                    with cf3:
                        f_dot = st.multiselect("Dotación", options=['DOTADA', 'NO DOTADA'], key=f"pdf1_dot_{idx}")
                    with cf4:
                        f_est = st.multiselect("Estado", options=df_old['Estado_Plaza'].unique(), key=f"pdf1_est_{idx}")
                    df_f = df_old.copy()
                    if f_prov:  df_f = df_f[df_f['Provincia'].isin(f_prov)]
                    if f_grupo: df_f = df_f[df_f['Grupo'].isin(f_grupo)]
                    if f_dot:   df_f = df_f[df_f['Dotación'].isin(f_dot)]
                    if f_est:   df_f = df_f[df_f['Estado_Plaza'].isin(f_est)]
                    col_a, col_b, col_c, col_d = st.columns(4)
                    col_a.metric("Total Plazas", len(df_f))
                    col_b.metric("Ocupadas",     len(df_f[df_f['Estado_Plaza'] == 'OCUPADA']))
                    col_c.metric("Vacantes",     len(df_f[df_f['Estado_Plaza'] == 'VACANTE']))
                    col_d.metric("Dotadas",      len(df_f[df_f['Dotación'] == 'DOTADA']))
                    st.markdown("---")
                    st.dataframe(df_f[['Código','Denominación','Modo_Acceso','Grupo','Cuerpo','Provincia','Localidad','Carácter','Dotación','Estado_Plaza','Ocupante']], width='stretch', height=500)
                    st.caption(f"Mostrando {len(df_f)} de {len(df_old)} plazas")

                with sub_tab_pdf_act:
                    st.markdown(f"#### {info_archivos[idx+1]['nombre']}")
                    st.caption(f"📅 Fecha: {info_archivos[idx+1]['fecha']}")
                    cf1, cf2, cf3, cf4 = st.columns(4)
                    with cf1:
                        f_prov = st.multiselect("Provincia", options=sorted([p for p in df_new['Provincia'].unique() if p != 'NO ESPECIFICADA']), key=f"pdf2_prov_{idx}")
                    with cf2:
                        f_grupo = st.multiselect("Grupo", options=sorted([g for g in df_new['Grupo'].unique() if pd.notna(g)]), key=f"pdf2_grupo_{idx}")
                    with cf3:
                        f_dot = st.multiselect("Dotación", options=['DOTADA', 'NO DOTADA'], key=f"pdf2_dot_{idx}")
                    with cf4:
                        f_est = st.multiselect("Estado", options=df_new['Estado_Plaza'].unique(), key=f"pdf2_est_{idx}")
                    df_f = df_new.copy()
                    if f_prov:  df_f = df_f[df_f['Provincia'].isin(f_prov)]
                    if f_grupo: df_f = df_f[df_f['Grupo'].isin(f_grupo)]
                    if f_dot:   df_f = df_f[df_f['Dotación'].isin(f_dot)]
                    if f_est:   df_f = df_f[df_f['Estado_Plaza'].isin(f_est)]
                    col_a, col_b, col_c, col_d = st.columns(4)
                    col_a.metric("Total Plazas", len(df_f))
                    col_b.metric("Ocupadas",     len(df_f[df_f['Estado_Plaza'] == 'OCUPADA']))
                    col_c.metric("Vacantes",     len(df_f[df_f['Estado_Plaza'] == 'VACANTE']))
                    col_d.metric("Dotadas",      len(df_f[df_f['Dotación'] == 'DOTADA']))
                    st.markdown("---")
                    st.dataframe(df_f[['Código','Denominación','Modo_Acceso','Grupo','Cuerpo','Provincia','Localidad','Carácter','Dotación','Estado_Plaza','Ocupante']], width='stretch', height=500)
                    st.caption(f"Mostrando {len(df_f)} de {len(df_new)} plazas")

        st.markdown("---")
        if st.button("🔄 Cargar Nuevos Archivos", type="secondary"):
            st.session_state.archivos_procesados = None
            st.session_state.comparacion_ejecutada = False
            st.session_state.dataframes_procesados = None
            st.session_state.info_archivos = None
            st.session_state.revision_activa = None
            st.rerun()

    elif len(dataframes_procesados) == 0:
        st.error("⚠️ No se pudieron procesar los archivos. Revisa que los PDFs son válidos.")
        if st.button("🔄 Volver a cargar archivos"):
            st.session_state.archivos_procesados = None
            st.session_state.comparacion_ejecutada = False
            st.session_state.dataframes_procesados = None
            st.session_state.info_archivos = None
            st.session_state.revision_activa = None
            st.rerun()
