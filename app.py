
# ============================================================
# OBSERVATÓRIO CLIMÁTICO DE PERNAMBUCO
# Temperatura do Ar e da Superfície | 1991–2026
#
# AUTORES

#
# AJUSTES:
# 1. Valores-p pequenos: p < 0,01
# 2. Legendas, títulos e eixos sempre legíveis
# ============================================================

from pathlib import Path
import re
import unicodedata
import warnings

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import rasterio
import streamlit as st

from rasterio.enums import Resampling
from scipy import stats
from scipy.ndimage import convolve

from statsmodels.tsa.stattools import (
    adfuller, kpss, acf, pacf
)
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.holtwinters import ExponentialSmoothing


# ============================================================
# 1. CONFIGURAÇÕES
# ============================================================

st.set_page_config(
    page_title="Observatório Climático de Pernambuco",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE = Path(__file__).resolve().parent

NOME_EXCEL = (
    "Temperaturas_diarias_Pernambuco_1991_2026.xlsx"
)

CANDIDATOS_EXCEL = [
    BASE / NOME_EXCEL,
    BASE / "dados" / NOME_EXCEL,
    BASE.parent / NOME_EXCEL,
    BASE.parent / "dados" / NOME_EXCEL
]

EXCEL = next(
    (p for p in CANDIDATOS_EXCEL if p.is_file()),
    CANDIDATOS_EXCEL[0]
)

CANDIDATOS_ATLAS = [
    BASE / "ATLAS_TERMICO_PERNAMBUCO",
    BASE.parent / "ATLAS_TERMICO_PERNAMBUCO",
    BASE
]

PASTA_ATLAS = next(
    (
        p for p in CANDIDATOS_ATLAS
        if (p / "02_MAPAS_INDIVIDUAIS").is_dir()
    ),
    CANDIDATOS_ATLAS[0]
)

PASTA_INDIVIDUAIS = (
    PASTA_ATLAS / "02_MAPAS_INDIVIDUAIS"
)
PASTA_PAINEIS = (
    PASTA_ATLAS / "01_PAINEIS_GERAIS"
)
PASTA_COMPARACOES = (
    PASTA_ATLAS / "03_COMPARACOES"
)

TIFF_EM_KELVIN = False

UNIDADE = "°C"
ALTURA_GRAFICO = 440

VAR_AR = "Temperatura do ar"
VAR_SUP = "Temperatura da superfície"

VARIAVEIS = [VAR_AR, VAR_SUP]

COLUNAS = {
    VAR_AR: "temperatura_ar_c",
    VAR_SUP: "temperatura_superficie_c"
}

PERIODOS = [
    "1991-1995",
    "1996-2000",
    "2001-2005",
    "2006-2010",
    "2011-2015",
    "2016-2020",
    "2021-2026"
]


# ============================================================
# 2. PALETA AZUL–VERMELHO
# ============================================================

FUNDO = "#F3F7FA"
PAPEL = "#FFFFFF"
TEXTO = "#172B3D"
PRETO = "#111111"

AZUL_ESCURO = "#163E78"
AZUL = "#3379AC"
AZUL_CLARO = "#82B7D3"

VERMELHO = "#AE303D"
CORAL = "#E67852"

CORES_VAR = {
    VAR_AR: AZUL,
    VAR_SUP: VERMELHO
}

PALETA_TERMICA = [
    "#163E78",
    "#3379AC",
    "#82B7D3",
    "#E5ECED",
    "#F1CCA9",
    "#E67852",
    "#AE303D"
]

PALETA_ANOMALIA = [
    "#163E78",
    "#82B7D3",
    "#F5F7F8",
    "#E67852",
    "#AE303D"
]


# ============================================================
# 3. CSS — LAYOUT ORIGINAL COM CONTRASTE CORRIGIDO
# ============================================================

st.markdown("""
<style>

:root {
    color-scheme: light;
}

html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background: #F3F7FA !important;
    color: #172B3D !important;
}

[data-testid="stMainBlockContainer"] {
    max-width: 1500px;
    padding-top: 1.4rem;
    padding-bottom: 3rem;
}

/* TÍTULOS */

[data-testid="stMain"] h1,
[data-testid="stMain"] h2,
[data-testid="stMain"] h3,
[data-testid="stMain"] h4 {
    color: #163E78 !important;
    font-family: "Segoe UI", Arial, sans-serif;
    font-weight: 750;
}

[data-testid="stMain"] p,
[data-testid="stMain"] li,
[data-testid="stMain"] label {
    color: #172B3D;
}

/* BARRA LATERAL */

[data-testid="stSidebar"],
[data-testid="stSidebarContent"] {
    background: #163E78 !important;
    color: #FFFFFF !important;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {
    color: #FFFFFF !important;
}

[data-testid="stSidebar"] hr {
    border-color: #7599B8 !important;
}

/* BOTÕES */

.stButton > button,
.stDownloadButton > button,
.stFormSubmitButton > button {
    background: #163E78 !important;
    color: #FFFFFF !important;
    border: 1px solid #163E78 !important;
    border-radius: 10px !important;
    min-height: 43px;
    font-weight: 650 !important;
}

.stButton > button *,
.stDownloadButton > button *,
.stFormSubmitButton > button * {
    color: #FFFFFF !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
.stFormSubmitButton > button:hover {
    background: #AE303D !important;
    color: #FFFFFF !important;
    border-color: #AE303D !important;
}

.stButton > button:hover *,
.stDownloadButton > button:hover *,
.stFormSubmitButton > button:hover * {
    color: #FFFFFF !important;
}

.stButton > button:focus,
.stButton > button:active {
    background: #913141 !important;
    color: #FFFFFF !important;
}

.stButton > button:focus *,
.stButton > button:active * {
    color: #FFFFFF !important;
}

/* ABAS */

button[data-baseweb="tab"] {
    background: #DFEBF3 !important;
    border-radius: 9px 9px 0 0;
    padding: 12px 14px !important;
    margin-right: 4px;
}

button[data-baseweb="tab"] * {
    color: #163E78 !important;
    font-weight: 650 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background: #163E78 !important;
}

button[data-baseweb="tab"][aria-selected="true"] * {
    color: #FFFFFF !important;
}

/* INDICADORES */

[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid #CADCE9;
    border-top: 4px solid #3379AC;
    border-radius: 12px;
    padding: 16px;
}

[data-testid="stMetric"] * {
    color: #172B3D !important;
}

/* SELETORES */

[data-baseweb="select"] > div,
[data-baseweb="input"] > div {
    background: #FFFFFF !important;
    color: #172B3D !important;
    border-color: #B8D1E3 !important;
}

[data-baseweb="popover"],
[data-baseweb="popover"] ul,
[data-baseweb="popover"] li {
    background: #FFFFFF !important;
    color: #172B3D !important;
}

[data-baseweb="popover"] * {
    color: #172B3D !important;
}

/* CARTÕES */

[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: #CADCE9 !important;
    border-radius: 12px;
}

[data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #CADCE9;
    border-radius: 11px;
}

/* CABEÇALHO */

.clima-topo {
    background: #FFFFFF;
    border: 1px solid #CADCE9;
    border-left: 7px solid #3379AC;
    border-radius: 14px;
    padding: 29px 34px;
    margin-bottom: 23px;
}

.clima-selo {
    color: #3379AC;
    font-size: 11px;
    letter-spacing: 2.6px;
    font-weight: 750;
    text-transform: uppercase;
    margin-bottom: 12px;
}

.clima-titulo {
    color: #163E78;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: clamp(25px, 3vw, 39px);
    font-weight: 800;
}

.clima-subtitulo {
    color: #365D78;
    font-size: 15px;
    margin-top: 12px;
}

.clima-faixa {
    height: 7px;
    margin-top: 24px;
    border-radius: 6px;
    background: linear-gradient(
        90deg,
        #163E78,
        #3379AC,
        #82B7D3,
        #E5ECED,
        #F1CCA9,
        #E67852,
        #AE303D
    );
}

/* DOCUMENTAÇÃO */

.texto-cientifico {
    color: #172B3D;
    text-align: justify;
    line-height: 1.95;
    font-size: 16px;
    margin-bottom: 18px;
}

/* RODAPÉ */

.rodape {
    margin-top: 42px;
    padding: 22px;
    border-top: 1px solid #CADCE9;
    text-align: center;
    color: #365D78;
    font-size: 12px;
}

/* O contraste dos textos Plotly é configurado
   diretamente em exibir(), preservando
   ícones e controles da interface. */

</style>
""", unsafe_allow_html=True)


# ============================================================
# 4. FUNÇÕES VISUAIS
# ============================================================

def texto(conteudo):

    st.markdown(
        '<div class="texto-cientifico">'
        + conteudo +
        '</div>',
        unsafe_allow_html=True
    )


# ------------------------------------------------------------
# CORREÇÃO 1:
# LEGENDAS, TÍTULOS E EIXOS PRETOS
# ------------------------------------------------------------

def exibir(fig, altura=ALTURA_GRAFICO):

    fig.update_layout(
        template="plotly_white",
        height=altura,
        paper_bgcolor=PAPEL,
        plot_bgcolor=PAPEL,

        font=dict(
            family="Arial",
            size=12,
            color=PRETO
        ),

        title=dict(
            x=0.03,
            font=dict(
                size=17,
                color=PRETO
            )
        ),

        legend=dict(
            bgcolor="rgba(255,255,255,0.96)",
            bordercolor="#DCE5EB",
            borderwidth=0,
            font=dict(
                family="Arial",
                size=12,
                color=PRETO
            ),
            title=dict(
                font=dict(
                    color=PRETO,
                    size=12
                )
            )
        ),

        hoverlabel=dict(
            bgcolor=AZUL_ESCURO,
            font=dict(
                color="#FFFFFF"
            )
        ),

        margin=dict(
            l=43,
            r=25,
            t=65,
            b=65
        )
    )

    fig.update_xaxes(
        showgrid=False,
        tickfont=dict(color=PRETO),
        title_font=dict(color=PRETO)
    )

    fig.update_yaxes(
        gridcolor="#E5ECED",
        tickfont=dict(color=PRETO),
        title_font=dict(color=PRETO)
    )

    # Textos das escalas de cores
    fig.update_coloraxes(
        colorbar=dict(
            tickfont=dict(color=PRETO),
            title=dict(
                font=dict(color=PRETO)
            )
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "scale": 3
            }
        }
    )


def numero(valor, casas=2):

    if pd.isna(valor):
        return "—"

    return f"{valor:.{casas}f}".replace(".", ",")


# ------------------------------------------------------------
# CORREÇÃO 2:
# FORMATAR VALORES-P MUITO PEQUENOS
# ------------------------------------------------------------

def formatar_p_valor(valor):

    if pd.isna(valor):
        return "—"

    valor = float(valor)

    if valor < 0.01:
        return "p < 0,01"

    return f"{valor:.4f}".replace(".", ",")


def formatar_tabela_testes(df):

    resultado = df.copy()

    if "Estatistica" in resultado.columns:

        resultado["Estatistica"] = (
            resultado["Estatistica"]
            .apply(lambda v: numero(v, 4))
        )

    if "p_valor" in resultado.columns:

        resultado["p_valor"] = (
            resultado["p_valor"]
            .apply(formatar_p_valor)
        )

    return resultado


def exportar(df, nome):

    st.download_button(
        "Baixar resultados CSV",
        data=df.to_csv(
            index=False
        ).encode("utf-8-sig"),
        file_name=nome,
        mime="text/csv"
    )


def normalizar(valor):

    s = unicodedata.normalize(
        "NFKD",
        str(valor).strip().lower()
    )

    s = "".join(
        c for c in s
        if not unicodedata.combining(c)
    )

    return re.sub(
        r"[^a-z0-9]+",
        "_",
        s
    ).strip("_")


def anos_arquivo(arquivo):

    return re.findall(
        r"(?:19|20)\d{2}",
        arquivo.stem
    )


def para_numero(coluna):

    if pd.api.types.is_numeric_dtype(coluna):

        return pd.to_numeric(
            coluna,
            errors="coerce"
        )

    return pd.to_numeric(
        coluna.astype(str)
        .str.strip()
        .str.replace(",", ".", regex=False),
        errors="coerce"
    )


# ============================================================
# 5. CARREGAR EXCEL
# ============================================================

@st.cache_data(
    show_spinner="Carregando dados de temperatura..."
)
def ler_excel(caminho, modificacao):

    with pd.ExcelFile(caminho) as xls:

        abas = xls.sheet_names

        correspondentes = [
            a for a in abas
            if normalizar(a) == "dados_diarios"
        ]

        if not correspondentes:
            raise ValueError(
                "A aba Dados_diarios não foi encontrada."
            )

        aba = correspondentes[0]

        tabela = pd.read_excel(
            xls,
            sheet_name=aba
        )

    return tabela, abas, aba


def preparar_excel(df):

    df = df.copy()

    df.columns = [
        normalizar(c)
        for c in df.columns
    ]

    aliases = {
        "temperatura_ar": "temperatura_ar_c",
        "temperatura_superficie":
            "temperatura_superficie_c"
    }

    for antigo, novo in aliases.items():

        if novo not in df.columns and antigo in df.columns:

            df = df.rename(
                columns={antigo: novo}
            )

    obrigatorias = [
        "data",
        "temperatura_ar_c",
        "temperatura_superficie_c"
    ]

    faltantes = [
        c for c in obrigatorias
        if c not in df.columns
    ]

    if faltantes:

        raise ValueError(
            "Colunas não encontradas: "
            + ", ".join(faltantes)
        )

    if pd.api.types.is_numeric_dtype(df["data"]):

        df["data"] = pd.to_datetime(
            df["data"],
            unit="D",
            origin="1899-12-30",
            errors="coerce"
        )

    else:

        df["data"] = pd.to_datetime(
            df["data"],
            errors="coerce"
        )

    for coluna in [
        "temperatura_ar_c",
        "temperatura_superficie_c"
    ]:

        df[coluna] = para_numero(
            df[coluna]
        )

    df = df.dropna(
        subset=["data"]
    ).sort_values("data")

    df = (
        df.groupby("data", as_index=False)
        .agg(
            temperatura_ar_c=(
                "temperatura_ar_c", "mean"
            ),
            temperatura_superficie_c=(
                "temperatura_superficie_c", "mean"
            )
        )
    )

    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.month
    df["dia"] = df["data"].dt.day

    df["dia_do_ano"] = (
        df["data"].dt.dayofyear
    )

    inicio = (
        1991 + 5 * ((df["ano"] - 1991) // 5)
    )

    inicio = np.minimum(
        inicio,
        2021
    )

    fim = np.where(
        inicio == 2021,
        2026,
        inicio + 4
    )

    df["periodo"] = (
        inicio.astype(str)
        + "-"
        + fim.astype(str)
    )

    df["diferenca_termica"] = (
        df["temperatura_superficie_c"]
        - df["temperatura_ar_c"]
    )

    return df


dados = None
abas_excel = []
aba_excel = None
erro_excel = None

if EXCEL.is_file():

    try:

        bruto, abas_excel, aba_excel = ler_excel(
            str(EXCEL),
            EXCEL.stat().st_mtime_ns
        )

        dados = preparar_excel(bruto)

        if dados.empty:

            dados = None
            erro_excel = "Planilha vazia."

    except Exception as erro:

        erro_excel = str(erro)

else:

    erro_excel = (
        "Planilha não encontrada: "
        + str(EXCEL)
    )


# ============================================================
# 6. SÉRIES TEMPORAIS
# ============================================================

def serie_diaria(df, variavel):

    return (
        df.set_index("data")[
            COLUNAS[variavel]
        ]
        .sort_index()
        .asfreq("D")
    )


def serie_mensal(df, variavel):

    return (
        serie_diaria(df, variavel)
        .resample("MS")
        .mean()
    )


def resumo_periodos(df):

    longo = df.melt(
        id_vars=[
            "data", "ano", "periodo"
        ],
        value_vars=[
            "temperatura_ar_c",
            "temperatura_superficie_c"
        ],
        var_name="variavel",
        value_name="temperatura"
    )

    longo["variavel"] = longo["variavel"].map({
        "temperatura_ar_c": VAR_AR,
        "temperatura_superficie_c": VAR_SUP
    })

    return (
        longo.groupby(
            ["periodo", "variavel"],
            as_index=False
        )
        .agg(
            media=("temperatura", "mean"),
            mediana=("temperatura", "median"),
            minimo=("temperatura", "min"),
            maximo=("temperatura", "max"),
            desvio=("temperatura", "std"),
            n=("temperatura", "count")
        )
    )


def anomalias_mensais(df, variavel):

    s = serie_mensal(df, variavel)

    resultado = s.rename(
        "temperatura"
    ).to_frame()

    resultado["mes"] = (
        resultado.index.month
    )

    resultado["referencia"] = (
        resultado.groupby("mes")["temperatura"]
        .transform("mean")
    )

    resultado["anomalia"] = (
        resultado["temperatura"]
        - resultado["referencia"]
    )

    resultado["ano"] = (
        resultado.index.year
    )

    return resultado.reset_index()


# ============================================================
# 7. TESTES ESTATÍSTICOS
# ============================================================

def testes_temporais(serie):

    s = serie.dropna().astype(float)

    registros = []

    if len(s) < 36:
        return pd.DataFrame()

    # ADF
    try:

        teste = adfuller(
            s,
            autolag="AIC"
        )

        registros.append({
            "Teste": "ADF",
            "Estatistica": teste[0],
            "p_valor": teste[1],
            "Hipotese_nula": "Raiz unitária"
        })

    except Exception:
        pass

    # KPSS
    try:

        with warnings.catch_warnings():

            warnings.simplefilter("ignore")

            teste = kpss(
                s,
                regression="c",
                nlags="auto"
            )

        registros.append({
            "Teste": "KPSS",
            "Estatistica": teste[0],
            "p_valor": teste[1],
            "Hipotese_nula": "Estacionariedade"
        })

    except Exception:
        pass

    # Ljung-Box
    try:

        teste = acorr_ljungbox(
            s - s.mean(),
            lags=[12],
            return_df=True
        )

        registros.append({
            "Teste": "Ljung-Box",
            "Estatistica": teste["lb_stat"].iloc[-1],
            "p_valor": teste["lb_pvalue"].iloc[-1],
            "Hipotese_nula":
                "Sem autocorrelação até lag 12"
        })

    except Exception:
        pass

    # Kendall anual
    anual = (
        s.resample("YS")
        .mean()
        .dropna()
    )

    if len(anual) >= 5:

        tau, p_valor = stats.kendalltau(
            np.arange(len(anual)),
            anual.values
        )

        registros.append({
            "Teste": "Kendall anual",
            "Estatistica": tau,
            "p_valor": p_valor,
            "Hipotese_nula":
                "Sem associação monotônica"
        })

    return pd.DataFrame(registros)


# ============================================================
# 8. PREVISÃO
# ============================================================

def preparar_serie_modelo(s):

    s = s.asfreq("MS")

    if len(s) < 36:

        raise ValueError(
            "São necessários 36 meses."
        )

    if s.isna().mean() > 0.05:

        raise ValueError(
            "Mais de 5% dos meses estão ausentes."
        )

    s = s.interpolate(
        method="time",
        limit=2,
        limit_direction="both"
    )

    if s.isna().any():

        raise ValueError(
            "Ainda existem meses sem dados."
        )

    return s


@st.cache_data(
    show_spinner="Calculando previsão..."
)
def previsao_validada(serie, horizonte):

    s = preparar_serie_modelo(serie)

    treino = s.iloc[:-12]
    teste = s.iloc[-12:]

    def ajustar(serie_entrada):

        with warnings.catch_warnings():

            warnings.simplefilter("ignore")

            modelo = ExponentialSmoothing(
                serie_entrada,
                trend="add",
                seasonal="add",
                seasonal_periods=12,
                initialization_method="estimated"
            )

            return modelo.fit(
                optimized=True
            )

    ajuste = ajustar(treino)

    previsto_ets = ajuste.forecast(12)

    previsto_sazonal = pd.Series(
        treino.iloc[-12:].values,
        index=teste.index
    )

    def metricas(previsao):

        erro = (
            teste.to_numpy()
            - previsao.to_numpy()
        )

        return (
            np.mean(np.abs(erro)),
            np.sqrt(np.mean(erro ** 2))
        )

    mae_ets, rmse_ets = metricas(
        previsto_ets
    )

    mae_sazonal, rmse_sazonal = metricas(
        previsto_sazonal
    )

    final = ajustar(s)

    futuro = final.forecast(horizonte)

    validacao = pd.DataFrame({
        "Data": teste.index,
        "Observado": teste.values,
        "Holt_Winters": previsto_ets.values,
        "Sazonal_ingenua": previsto_sazonal.values
    })

    desempenho = pd.DataFrame({
        "Modelo": [
            "Holt-Winters",
            "Sazonal ingênuo"
        ],
        "MAE": [
            mae_ets,
            mae_sazonal
        ],
        "RMSE": [
            rmse_ets,
            rmse_sazonal
        ]
    })

    return futuro, validacao, desempenho


# ============================================================
# 9. LOCALIZAR TIFFS ORIGINAIS
# ============================================================

def identificar_tiff(arquivo):

    nome = normalizar(arquivo.stem)

    if nome.startswith("t_ar_media"):

        variavel = VAR_AR

    elif nome.startswith("t_superficie_media"):

        variavel = VAR_SUP

    else:

        return None

    anos = anos_arquivo(arquivo)

    if len(anos) < 2:
        return None

    return (
        variavel,
        f"{anos[0]}-{anos[1]}"
    )


def localizar_tiffs():

    pastas = [
        BASE / "TIFF_ORIGINAIS",
        BASE / "dados",
        BASE
    ]

    encontrados = {}

    for pasta in pastas:

        if not pasta.exists():
            continue

        for arquivo in pasta.rglob("*"):

            if not arquivo.is_file():
                continue

            if arquivo.suffix.lower() not in [
                ".tif", ".tiff"
            ]:
                continue

            if "suavizado" in str(arquivo).lower():
                continue

            chave = identificar_tiff(
                arquivo
            )

            if chave:

                encontrados.setdefault(
                    chave,
                    arquivo
                )

    return encontrados


TIFFS = localizar_tiffs()


# ============================================================
# 10. ESTATÍSTICAS RASTER
# ============================================================

@st.cache_data(
    show_spinner="Analisando GeoTIFF..."
)
def estatisticas_raster(caminho, mtime, kelvin):

    soma = 0.0
    soma2 = 0.0
    n = 0

    minimo = np.inf
    maximo = -np.inf

    with rasterio.open(caminho) as src:

        for _, janela in src.block_windows(1):

            bloco = src.read(
                1,
                window=janela,
                masked=True
            )

            valores = (
                bloco.compressed()
                .astype(float)
            )

            valores = valores[
                np.isfinite(valores)
            ]

            if len(valores) == 0:
                continue

            if kelvin:
                valores -= 273.15

            soma += valores.sum()
            soma2 += np.square(valores).sum()

            n += len(valores)

            minimo = min(
                minimo,
                valores.min()
            )

            maximo = max(
                maximo,
                valores.max()
            )

        if n == 0:

            raise ValueError(
                "Raster sem valores válidos."
            )

        fator = max(
            1,
            int(np.ceil(
                max(src.shape) / 350
            ))
        )

        amostra = src.read(
            1,
            out_shape=(
                max(1, src.height // fator),
                max(1, src.width // fator)
            ),
            resampling=Resampling.nearest,
            masked=True
        ).compressed().astype(float)

    amostra = amostra[
        np.isfinite(amostra)
    ]

    if kelvin:
        amostra -= 273.15

    media = soma / n

    desvio = np.sqrt(
        max(
            0,
            soma2 / n - media ** 2
        )
    )

    return {
        "media": media,
        "desvio": desvio,
        "minimo": minimo,
        "maximo": maximo,
        "n_pixels": n,
        "amostra": amostra
    }


# ============================================================
# 11. MORAN GLOBAL
# ============================================================

@st.cache_data(
    show_spinner="Calculando Moran..."
)
def moran_raster(
    caminho,
    mtime,
    n_perm=199
):

    with rasterio.open(caminho) as src:

        fator = max(
            1,
            int(np.ceil(
                max(src.shape) / 180
            ))
        )

        raster = src.read(
            1,
            out_shape=(
                max(1, src.height // fator),
                max(1, src.width // fator)
            ),
            resampling=Resampling.nearest,
            masked=True
        )

    valores = raster.filled(
        np.nan
    ).astype(float)

    validos = np.isfinite(valores)

    if validos.sum() < 30:

        raise ValueError(
            "Poucas células válidas."
        )

    kernel = np.array([
        [0, 1, 0],
        [1, 0, 1],
        [0, 1, 0]
    ], dtype=float)

    vizinhos = convolve(
        validos.astype(float),
        kernel,
        mode="constant",
        cval=0
    )

    n = int(validos.sum())

    s0 = float(
        vizinhos[validos].sum()
    )

    if s0 == 0:

        raise ValueError(
            "Sem vizinhos válidos."
        )

    def calcular_indice(v):

        z = np.zeros_like(valores)

        z[validos] = (
            v - np.mean(v)
        )

        lag = convolve(
            z,
            kernel,
            mode="constant",
            cval=0
        )

        numerador = np.sum(
            z[validos] * lag[validos]
        )

        denominador = np.sum(
            z[validos] ** 2
        )

        if denominador <= 0:
            return np.nan

        return (
            n / s0
        ) * (
            numerador / denominador
        )

    original = valores[validos]

    observado = calcular_indice(
        original
    )

    rng = np.random.default_rng(42)

    simulacoes = np.array([
        calcular_indice(
            rng.permutation(original)
        )
        for _ in range(n_perm)
    ])

    simulacoes = simulacoes[
        np.isfinite(simulacoes)
    ]

    if len(simulacoes) == 0:
        return observado, np.nan, n

    centro = simulacoes.mean()

    p_valor = (
        1 + np.sum(
            np.abs(simulacoes - centro)
            >= abs(observado - centro)
        )
    ) / (len(simulacoes) + 1)

    return observado, p_valor, n


# ============================================================
# 12. MAPAS
# ============================================================

def listar_png(pasta):

    if not pasta.is_dir():
        return []

    return sorted([
        p for p in pasta.iterdir()
        if p.suffix.lower() == ".png"
    ])


GALERIAS = {
    "individuais": listar_png(PASTA_INDIVIDUAIS),
    "paineis": listar_png(PASTA_PAINEIS),
    "comparacoes": listar_png(PASTA_COMPARACOES)
}


def titulo_mapa(arquivo):

    nome = normalizar(arquivo.stem)
    anos = anos_arquivo(arquivo)

    periodo = (
        f"{anos[0]}–{anos[1]}"
        if len(anos) >= 2
        else ""
    )

    if "painel" in nome:

        if "superficie" in nome:

            return "Painel — Superfície"

        return "Painel — Temperatura do ar"

    if nome.startswith("t_ar"):

        return f"Temperatura do ar | {periodo}"

    if nome.startswith("t_superficie"):

        return f"Temperatura da superfície | {periodo}"

    if nome.startswith("comparacao"):

        return f"Comparação térmica | {periodo}"

    return arquivo.stem.replace("_", " ")


# ============================================================
# 13. NAVEGAÇÃO DOS MAPAS
# ============================================================

if "tela_mapa" not in st.session_state:
    st.session_state.tela_mapa = "menu"

if "categoria_mapa" not in st.session_state:
    st.session_state.categoria_mapa = None

if "arquivo_mapa" not in st.session_state:
    st.session_state.arquivo_mapa = None


def abrir_categoria(categoria):

    st.session_state.categoria_mapa = categoria
    st.session_state.tela_mapa = "galeria"


def abrir_imagem(arquivo):

    st.session_state.arquivo_mapa = str(arquivo)
    st.session_state.tela_mapa = "imagem"


def voltar_categoria():

    st.session_state.tela_mapa = "galeria"


def voltar_mapas():

    st.session_state.tela_mapa = "menu"


def galeria(arquivos):

    if not arquivos:

        st.warning(
            "Nenhum mapa PNG encontrado."
        )

        return

    for i in range(0, len(arquivos), 3):

        colunas = st.columns(
            3,
            gap="medium"
        )

        for coluna, arquivo in zip(
            colunas,
            arquivos[i:i + 3]
        ):

            with coluna:

                with st.container(border=True):

                    st.markdown(
                        f"#### {titulo_mapa(arquivo)}"
                    )

                    st.image(
                        str(arquivo),
                        use_container_width=True
                    )

                    st.button(
                        "Visualizar mapa →",
                        key=f"mapa_{arquivo.stem}",
                        use_container_width=True,
                        on_click=abrir_imagem,
                        args=(arquivo,)
                    )


# ============================================================
# 14. BARRA LATERAL
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🌡️ OBSERVATÓRIO CLIMÁTICO"
    )

    st.divider()

    st.markdown("### REGIÃO ANALISADA")

    st.write("Estado de Pernambuco")
    st.write("Período: 1991–2026")

    st.divider()

    st.markdown("### BASE TEMPORAL")

    if dados is not None:

        st.success(
            "Planilha Excel conectada"
        )

        st.write(
            f"Registros: {len(dados):,}"
        )

        st.write(
            f"Abas: {len(abas_excel)}"
        )

        st.write(
            f"Aba utilizada: {aba_excel}"
        )

        st.write(
            f"Início: {dados['data'].min():%d/%m/%Y}"
        )

        st.write(
            f"Fim: {dados['data'].max():%d/%m/%Y}"
        )

    else:

        st.warning(
            "Planilha não encontrada."
        )

        if erro_excel:
            st.caption(erro_excel)

    st.divider()

    st.markdown("### PRODUTOS ESPACIAIS")

    st.write(
        f"GeoTIFFs: {len(TIFFS)}"
    )

    st.write(
        f"Mapas individuais: "
        f"{len(GALERIAS['individuais'])}"
    )

    st.write(
        f"Painéis: "
        f"{len(GALERIAS['paineis'])}"
    )

    st.write(
        f"Comparações: "
        f"{len(GALERIAS['comparacoes'])}"
    )

    st.divider()

    st.markdown("### PESQUISADORES")

    st.write("Denilson")
    st.write("Jader")
    st.write("Silvio")
    st.write("Débora")

# ============================================================
# 15. CABEÇALHO
# ============================================================

st.markdown(
    '<div class="clima-topo">'
    '<div class="clima-selo">'
    'Monitoramento e análise ambiental'
    '</div>'
    '<div class="clima-titulo">'
    'Observatório Climático de Pernambuco'
    '</div>'
    '<div class="clima-subtitulo">'
    'Dinâmica da Temperatura do Ar e da Superfície '
    '| 1991–2026'
    '</div>'
    '<div class="clima-faixa"></div>'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# 16. ABAS
# ============================================================

abas = st.tabs([
    "Autores",
    "Documentação",
    "Mapas",
    "Descritiva",
    "Séries temporais",
    "Testes",
    "Análise espacial",
    "Previsão",
    "Conclusão"
])


# ============================================================
# ABA 1 — AUTORES
# ============================================================


# ============================================================
# ABA 1 — AUTORES COMPLETOS
# ============================================================

with abas[0]:

    st.header("Equipe de Pesquisadores")

    st.write(
        "O Observatório Climático de Pernambuco integra "
        "análises estatísticas, séries temporais e informações "
        "cartográficas relacionadas à temperatura do ar "
        "e à temperatura da superfície."
    )

    autores = [
        {
            "nome": "Denilson de Oliveira Silva",
            "instituicao":
                "Universidade Federal Rural de Pernambuco",
            "vinculo":
                "Programa de Pós-Graduação em "
                "Biometria e Estatística Aplicada",
            "email": "denilson.oliveira@ufrpe.br",
            "orcid": "0009-0000-4031-7772",
            "lattes": None
        },
        {
            "nome": "Jader da Silva Jale",
            "instituicao":
                "Universidade Federal Rural de Pernambuco",
            "vinculo":
                "Programa de Pós-Graduação em "
                "Biometria e Estatística Aplicada",
            "email": "jader.silvajale@ufrpe.br",
            "orcid": "0000-0001-7414-1154",
            "lattes": None
        },
        {
            "nome": "Silvio Fernando Alves Xavier",
            "instituicao":
                "Universidade Estadual da Paraíba",
            "vinculo": "Departamento de Estatística",
            "email": "silvio@servidor.uepb.edu.br",
            "orcid": "0000-0002-4832-0711",
            "lattes": None
        },
        {
            "nome": "Débora de Sousa Cordeiro",
            "instituicao":
                "Universidade Federal Rural de Pernambuco",
            "vinculo":
                "Programa de Pós-Graduação em "
                "Biometria e Estatística Aplicada",
            "email": "debora.scordeiro@ufrpe.br",
            "orcid": "0009-0006-1410-4718",
            "lattes":
                "http://lattes.cnpq.br/1980673256363690"
        }
    ]

    # Quatro autores em duas colunas
    for inicio in range(0, len(autores), 2):

        colunas = st.columns(2, gap="medium")

        for coluna, autor in zip(
            colunas, autores[inicio:inicio + 2]
        ):

            with coluna:

                with st.container(border=True):

                    st.markdown(
                        f"### {autor['nome']}"
                    )

                    st.write(autor["instituicao"])

                    st.write(autor["vinculo"])

                    st.divider()

                    st.markdown(
                        f"[E-mail](mailto:{autor['email']})"
                    )

                    st.markdown(
                        f"[ORCID: {autor['orcid']}]"
                        f"(https://orcid.org/{autor['orcid']})"
                    )

                    if autor.get("lattes"):
                        st.markdown(
                            f"[Currículo Lattes]"
                            f"({autor['lattes']})"
                        )


# ============================================================
# ABA 2 — DOCUMENTAÇÃO
# ============================================================

with abas[1]:

    st.header("Documentação Científica")

    st.subheader("Resumo")

    texto(
        "O Observatório Climático de Pernambuco "
        "é uma aplicação interativa voltada ao estudo "
        "da dinâmica temporal e espacial da "
        "temperatura do ar e da superfície. "
        "A plataforma integra registros diários "
        "entre 1991 e 2026, produtos raster "
        "organizados por períodos e mapas temáticos. "
        "São disponibilizadas análises descritivas, "
        "técnicas de suavização, decomposição sazonal, "
        "testes estatísticos, autocorrelação espacial "
        "e previsões exploratórias."
    )

    st.subheader("Materiais")

    texto(
        "A base temporal é constituída por uma "
        "planilha Excel com registros diários "
        "de temperatura do ar e da superfície "
        "em graus Celsius. Os dados espaciais "
        "compreendem arquivos GeoTIFF relativos "
        "aos períodos de 1991–1995 até 2021–2026, "
        "com produtos cartográficos em PNG. "
        "A implementação utiliza Python, "
        "Pandas, NumPy, Plotly, Streamlit, "
        "SciPy, Statsmodels e Rasterio."
    )

    st.subheader("Métodos")

    texto(
        "Os registros diários são organizados "
        "cronologicamente e submetidos à verificação "
        "de datas e valores numéricos. "
        "A caracterização descritiva utiliza "
        "medidas de tendência central, dispersão, "
        "frequência e correlação. A evolução "
        "temporal é examinada por médias móveis "
        "e suavização exponencial."
    )

    st.latex(
        r"MM_t(k)=\frac{1}{k}"
        r"\sum_{j=0}^{k-1}T_{t-j}"
    )

    texto(
        "A decomposição STL separa tendência, "
        "sazonalidade e resíduos. As anomalias "
        "mensais são obtidas pela diferença "
        "entre cada observação e a média histórica "
        "do mesmo mês do ano."
    )

    st.latex(
        r"T_t=Tend_t+Saz_t+R_t"
    )

    st.latex(
        r"A_{m,t}=T_{m,t}-\overline{T}_m"
    )

    texto(
        "Os testes ADF e KPSS investigam "
        "propriedades de estacionariedade, "
        "enquanto o teste de Ljung–Box avalia "
        "a autocorrelação temporal. O coeficiente "
        "de Kendall é empregado para examinar "
        "associações monotônicas. Na componente "
        "espacial, utiliza-se o índice global "
        "de Moran para avaliar a semelhança "
        "entre células vizinhas."
    )

    st.latex(
        r"I=\frac{n}{S_0}"
        r"\frac{\sum_i\sum_jw_{ij}"
        r"(x_i-\bar{x})(x_j-\bar{x})}"
        r"{\sum_i(x_i-\bar{x})^2}"
    )

    texto(
        "A previsão é obtida por suavização "
        "exponencial de Holt–Winters e comparada "
        "à previsão sazonal ingênua utilizando "
        "validação retrospectiva. Os resultados "
        "devem ser interpretados considerando "
        "a sazonalidade, a autocorrelação "
        "e as limitações dos dados."
    )


# ============================================================
# ABA 3 — MAPAS
# ============================================================

with abas[2]:

    st.header("Cartografia das Temperaturas")

    categorias = {
        "individuais": "Mapas individuais",
        "paineis": "Painéis gerais",
        "comparacoes": "Comparações térmicas"
    }

    tela = st.session_state.tela_mapa
    categoria = st.session_state.categoria_mapa

    if tela == "menu":

        texto(
            "Explore a distribuição espacial "
            "das temperaturas por período, "
            "os painéis gerais e as comparações "
            "entre temperatura do ar e da superfície."
        )

        cols = st.columns(3)

        for coluna, (chave, titulo) in zip(
            cols,
            categorias.items()
        ):

            with coluna:

                with st.container(border=True):

                    st.subheader(titulo)

                    st.metric(
                        "Mapas disponíveis",
                        len(GALERIAS[chave])
                    )

                    st.button(
                        "Visualizar →",
                        key=f"categoria_{chave}",
                        use_container_width=True,
                        on_click=abrir_categoria,
                        args=(chave,)
                    )

    elif tela == "galeria":

        st.button(
            "← Voltar ao menu",
            key="voltar_menu_galeria",
            on_click=voltar_mapas
        )

        st.subheader(
            categorias[categoria]
        )

        galeria(
            GALERIAS[categoria]
        )

    elif tela == "imagem":

        c1, c2 = st.columns(2)

        with c1:

            st.button(
                "← Voltar à galeria",
                key="voltar_galeria",
                use_container_width=True,
                on_click=voltar_categoria
            )

        with c2:

            st.button(
                "⌂ Menu de mapas",
                key="voltar_menu",
                use_container_width=True,
                on_click=voltar_mapas
            )

        caminho = (
            st.session_state.arquivo_mapa
        )

        arquivo = (
            Path(caminho)
            if caminho
            else None
        )

        if arquivo and arquivo.is_file():

            st.subheader(
                titulo_mapa(arquivo)
            )

            st.image(
                str(arquivo),
                use_container_width=True
            )

            arquivos = GALERIAS[categoria]

            if arquivo in arquivos:

                pos = arquivos.index(arquivo)

                ca, cb, cc = st.columns(
                    [1, 2, 1]
                )

                with ca:

                    if pos > 0:

                        st.button(
                            "← Anterior",
                            key="mapa_anterior",
                            use_container_width=True,
                            on_click=abrir_imagem,
                            args=(arquivos[pos - 1],)
                        )

                with cb:

                    st.markdown(
                        f"**Mapa {pos + 1} "
                        f"de {len(arquivos)}**"
                    )

                with cc:

                    if pos < len(arquivos) - 1:

                        st.button(
                            "Próximo →",
                            key="mapa_proximo",
                            use_container_width=True,
                            on_click=abrir_imagem,
                            args=(arquivos[pos + 1],)
                        )

        else:

            st.warning(
                "Imagem cartográfica não encontrada."
            )


# ============================================================
# ABA 4 — DESCRITIVA
# ============================================================

with abas[3]:

    st.header(
        "Análise Descritiva das Temperaturas"
    )

    if dados is None:

        st.info(
            "Aguardando conexão com o Excel."
        )

    else:

        primeiro = int(
            dados["ano"].min()
        )

        ultimo = int(
            dados["ano"].max()
        )

        intervalo = st.slider(
            "Intervalo de anos",
            primeiro,
            ultimo,
            (primeiro, ultimo)
        )

        df = dados[
            dados["ano"].between(*intervalo)
        ].copy()

        longo = df.melt(
            id_vars=["data", "ano", "mes"],
            value_vars=[
                "temperatura_ar_c",
                "temperatura_superficie_c"
            ],
            var_name="variavel",
            value_name="temperatura"
        ).dropna(subset=["temperatura"])

        longo["variavel"] = longo["variavel"].map({
            "temperatura_ar_c": VAR_AR,
            "temperatura_superficie_c": VAR_SUP
        })

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Temperatura média do ar",
            numero(
                df["temperatura_ar_c"].mean()
            ) + " °C"
        )

        c2.metric(
            "Temperatura média da superfície",
            numero(
                df["temperatura_superficie_c"].mean()
            ) + " °C"
        )

        c3.metric(
            "Diferença média",
            numero(
                df["diferenca_termica"].mean()
            ) + " °C"
        )

        c4.metric(
            "Correlação",
            numero(
                df["temperatura_ar_c"].corr(
                    df["temperatura_superficie_c"]
                ),
                3
            )
        )

        st.divider()

        ca, cb = st.columns(2)

        with ca:

            fig = px.histogram(
                longo,
                x="temperatura",
                color="variavel",
                barmode="overlay",
                nbins=45,
                opacity=0.65,
                color_discrete_map=CORES_VAR,
                title="Distribuição das temperaturas"
            )

            fig.update_layout(
                xaxis_title="Temperatura (°C)",
                yaxis_title="Frequência"
            )

            exibir(fig)

        with cb:

            fig = px.box(
                longo,
                x="variavel",
                y="temperatura",
                color="variavel",
                color_discrete_map=CORES_VAR,
                title="Boxplots das temperaturas"
            )

            exibir(fig)

        cc, cd = st.columns(2)

        with cc:

            fig = px.violin(
                longo,
                x="variavel",
                y="temperatura",
                color="variavel",
                box=True,
                color_discrete_map=CORES_VAR,
                title="Distribuição e quartis"
            )

            exibir(fig)

        with cd:

            amostra = df.dropna(
                subset=[
                    "temperatura_ar_c",
                    "temperatura_superficie_c"
                ]
            )

            fig = px.scatter(
                amostra,
                x="temperatura_ar_c",
                y="temperatura_superficie_c",
                opacity=0.35,
                title="Relação ar × superfície",
                color_discrete_sequence=[AZUL]
            )

            fig.update_layout(
                xaxis_title="Temperatura do ar (°C)",
                yaxis_title="Temperatura da superfície (°C)"
            )

            exibir(fig)

        ce, cf = st.columns(2)

        with ce:

            mensal = (
                longo.groupby(
                    ["mes", "variavel"],
                    as_index=False
                )["temperatura"].mean()
            )

            fig = px.line(
                mensal,
                x="mes",
                y="temperatura",
                color="variavel",
                markers=True,
                color_discrete_map=CORES_VAR,
                title="Ciclo médio mensal"
            )

            fig.update_layout(
                xaxis_title="Mês",
                yaxis_title="Temperatura média (°C)"
            )

            exibir(fig)

        with cf:

            fig = px.histogram(
                df,
                x="diferenca_termica",
                nbins=40,
                title="Diferença entre as temperaturas",
                color_discrete_sequence=[VERMELHO]
            )

            fig.update_layout(
                xaxis_title="Superfície − Ar (°C)",
                yaxis_title="Frequência"
            )

            exibir(fig)

        st.subheader("Resumo estatístico")

        tabela = (
            longo.groupby("variavel")["temperatura"]
            .agg([
                "count",
                "mean",
                "median",
                "std",
                "min",
                "max"
            ])
            .reset_index()
        )

        st.dataframe(
            tabela,
            use_container_width=True,
            hide_index=True
        )

        exportar(
            tabela,
            "descritiva_temperatura_pe.csv"
        )


# ============================================================
# ABA 5 — SÉRIES TEMPORAIS
# ============================================================

with abas[4]:

    st.header(
        "Dinâmica das Séries Temporais"
    )

    if dados is None:

        st.info(
            "Aguardando dados de temperatura."
        )

    else:

        escolha = st.selectbox(
            "Variável",
            VARIAVEIS,
            key="variavel_series"
        )

        diaria = serie_diaria(
            dados,
            escolha
        )

        mensal = serie_mensal(
            dados,
            escolha
        )

        tecnica = st.radio(
            "Técnica temporal",
            [
                "Série bruta",
                "Médias móveis",
                "Suavização exponencial",
                "Decomposição STL",
                "Anomalias",
                "ACF e PACF"
            ],
            horizontal=True
        )

        # SÉRIE BRUTA

        if tecnica == "Série bruta":

            fig = go.Figure()

            fig.add_trace(
                go.Scattergl(
                    x=diaria.index,
                    y=diaria.values,
                    mode="lines",
                    name="Observado",
                    line=dict(
                        color=CORES_VAR[escolha],
                        width=1.2
                    )
                )
            )

            fig.update_layout(
                title="Série diária original",
                xaxis_title="Data",
                yaxis_title="Temperatura (°C)"
            )

            exibir(fig, 510)

            anual = (
                diaria.resample("YS").mean()
            )

            quinquenal = (
                dados.groupby("periodo")[
                    COLUNAS[escolha]
                ].mean()
            )

            ca, cb = st.columns(2)

            with ca:

                fig = px.line(
                    x=anual.index,
                    y=anual.values,
                    markers=True,
                    title="Temperaturas médias anuais"
                )

                fig.update_traces(
                    line_color=CORES_VAR[escolha]
                )

                exibir(fig)

            with cb:

                fig = px.bar(
                    x=quinquenal.index,
                    y=quinquenal.values,
                    color=quinquenal.values,
                    color_continuous_scale=PALETA_TERMICA,
                    title="Temperaturas por período"
                )

                fig.update_layout(
                    coloraxis_showscale=False
                )

                exibir(fig)

        # MÉDIAS MÓVEIS

        elif tecnica == "Médias móveis":

            janelas = st.multiselect(
                "Janelas (dias)",
                [7, 15, 30, 60, 90, 180, 365],
                default=[30, 90, 365]
            )

            fig = go.Figure()

            fig.add_trace(
                go.Scattergl(
                    x=diaria.index,
                    y=diaria.values,
                    name="Original",
                    line=dict(
                        color="#CAD6DF",
                        width=1
                    )
                )
            )

            cores_janelas = [
                AZUL,
                VERMELHO,
                CORAL,
                AZUL_CLARO,
                "#744E98",
                "#347F7F",
                AZUL_ESCURO
            ]

            for i, janela in enumerate(janelas):

                movel = diaria.rolling(
                    janela,
                    min_periods=max(
                        1, janela // 2
                    )
                ).mean()

                fig.add_trace(
                    go.Scatter(
                        x=movel.index,
                        y=movel.values,
                        name=f"MM {janela} dias",
                        line=dict(
                            color=cores_janelas[i],
                            width=2.4
                        )
                    )
                )

            fig.update_layout(
                title="Suavização por médias móveis",
                xaxis_title="Data",
                yaxis_title="Temperatura (°C)",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0,
                    font=dict(
                        color=PRETO,
                        size=12
                    ),
                    bgcolor="#FFFFFF"
                ),
                margin=dict(
                    l=43,
                    r=25,
                    t=100,
                    b=65
                )
            )

            exibir(fig, 510)

        # SUAVIZAÇÃO EXPONENCIAL

        elif tecnica == "Suavização exponencial":

            alfa = st.slider(
                "Parâmetro alfa",
                0.05,
                0.95,
                0.25,
                0.05
            )

            suavizada = mensal.ewm(
                alpha=alfa,
                adjust=False
            ).mean()

            fig = go.Figure()

            fig.add_trace(
                go.Scatter(
                    x=mensal.index,
                    y=mensal.values,
                    name="Observado",
                    line=dict(color=AZUL)
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=suavizada.index,
                    y=suavizada.values,
                    name="Suavizado",
                    line=dict(
                        color=VERMELHO,
                        width=3
                    )
                )
            )

            fig.update_layout(
                title="Suavização exponencial",
                xaxis_title="Data",
                yaxis_title="Temperatura (°C)"
            )

            exibir(fig, 510)

        # DECOMPOSIÇÃO STL

        elif tecnica == "Decomposição STL":

            try:

                s = preparar_serie_modelo(
                    mensal
                )

                decomposicao = STL(
                    s,
                    period=12,
                    robust=True
                ).fit()

                componentes = [
                    ("Observada", s),
                    ("Tendência", decomposicao.trend),
                    ("Sazonalidade", decomposicao.seasonal),
                    ("Resíduos", decomposicao.resid)
                ]

                for i in range(0, 4, 2):

                    cols = st.columns(2)

                    for coluna, (nome, serie_comp) in zip(
                        cols,
                        componentes[i:i + 2]
                    ):

                        with coluna:

                            fig = px.line(
                                x=serie_comp.index,
                                y=serie_comp.values,
                                title=nome
                            )

                            fig.update_traces(
                                line_color=(
                                    AZUL
                                    if nome in [
                                        "Observada",
                                        "Tendência"
                                    ]
                                    else VERMELHO
                                )
                            )

                            exibir(fig)

            except Exception as erro:

                st.warning(str(erro))

        # ANOMALIAS

        elif tecnica == "Anomalias":

            anomalias = anomalias_mensais(
                dados,
                escolha
            )

            fig = px.bar(
                anomalias,
                x="data",
                y="anomalia",
                color="anomalia",
                color_continuous_scale=PALETA_ANOMALIA,
                color_continuous_midpoint=0,
                title="Anomalias mensais"
            )

            fig.add_hline(
                y=0,
                line_color=AZUL_ESCURO
            )

            fig.update_layout(
                coloraxis_showscale=False,
                xaxis_title="Data",
                yaxis_title="Anomalia (°C)"
            )

            exibir(fig, 500)

            anual = (
                anomalias.groupby(
                    "ano",
                    as_index=False
                )["anomalia"].mean()
            )

            fig2 = px.bar(
                anual,
                x="ano",
                y="anomalia",
                color="anomalia",
                color_continuous_scale=PALETA_ANOMALIA,
                color_continuous_midpoint=0,
                title="Anomalias médias anuais"
            )

            fig2.add_hline(
                y=0,
                line_color=AZUL_ESCURO
            )

            fig2.update_layout(
                coloraxis_showscale=False
            )

            exibir(fig2)

        # ACF E PACF

        elif tecnica == "ACF e PACF":

            limpa = mensal.dropna()

            if len(limpa) < 30:

                st.warning(
                    "Série insuficiente."
                )

            else:

                n_lags = min(
                    36,
                    len(limpa) // 3
                )

                try:

                    valores_acf = acf(
                        limpa,
                        nlags=n_lags,
                        fft=True
                    )

                    valores_pacf = pacf(
                        limpa,
                        nlags=n_lags,
                        method="ywm"
                    )

                    ca, cb = st.columns(2)

                    with ca:

                        fig = px.bar(
                            x=np.arange(len(valores_acf)),
                            y=valores_acf,
                            color_discrete_sequence=[AZUL],
                            title="Autocorrelação (ACF)"
                        )

                        exibir(fig)

                    with cb:

                        fig = px.bar(
                            x=np.arange(len(valores_pacf)),
                            y=valores_pacf,
                            color_discrete_sequence=[VERMELHO],
                            title="Autocorrelação parcial (PACF)"
                        )

                        exibir(fig)

                except Exception as erro:

                    st.warning(str(erro))


# ============================================================
# ABA 6 — TESTES ESTATÍSTICOS
# ============================================================

with abas[5]:

    st.header("Testes Estatísticos Temporais")

    if dados is None:

        st.info(
            "Aguardando a base Excel."
        )

    else:

        variavel = st.selectbox(
            "Variável",
            VARIAVEIS,
            key="variavel_testes"
        )

        mensal = serie_mensal(
            dados,
            variavel
        )

        resultado = testes_temporais(
            mensal
        )

        if resultado.empty:

            st.warning(
                "Dados insuficientes para os testes."
            )

        else:

            # TABELA FORMATADA
            # Mantém valores originais em resultado.
            tabela_visual = formatar_tabela_testes(
                resultado
            )

            st.dataframe(
                tabela_visual,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Teste": st.column_config.TextColumn(
                        "Teste",
                        width="medium"
                    ),
                    "Estatistica": st.column_config.TextColumn(
                        "Estatística",
                        width="medium"
                    ),
                    "p_valor": st.column_config.TextColumn(
                        "Valor-p",
                        width="medium"
                    ),
                    "Hipotese_nula": st.column_config.TextColumn(
                        "Hipótese nula",
                        width="large"
                    )
                }
            )

            # Exportação com os valores numéricos originais
            exportar(
                resultado,
                "testes_temperatura_pe.csv"
            )

            ca, cb = st.columns(2)

            with ca:

                # Usar valores-p verdadeiros no gráfico.
                fig = px.bar(
                    resultado,
                    x="Teste",
                    y="p_valor",
                    color_discrete_sequence=[AZUL],
                    title="Valores-p dos testes"
                )

                fig.add_hline(
                    y=0.05,
                    line_dash="dash",
                    line_color=VERMELHO
                )

                fig.update_layout(
                    xaxis_title="Teste",
                    yaxis_title="Valor-p"
                )

                exibir(fig)

            with cb:

                diferencas = (
                    mensal.diff().dropna()
                )

                fig = px.histogram(
                    x=diferencas,
                    nbins=35,
                    color_discrete_sequence=[VERMELHO],
                    title="Diferenças mensais"
                )

                fig.update_layout(
                    xaxis_title="Variação de temperatura (°C)",
                    yaxis_title="Frequência"
                )

                exibir(fig)

            texto(
                "Os testes apresentam hipóteses "
                "nulas distintas. No teste ADF, "
                "a hipótese nula considera a "
                "presença de raiz unitária, "
                "enquanto no KPSS considera-se "
                "a estacionariedade. O teste "
                "de Ljung–Box avalia a ausência "
                "de autocorrelação até a defasagem "
                "considerada. Valores-p inferiores "
                "a 0,01 são apresentados na tabela "
                "como p &lt; 0,01 para facilitar "
                "a leitura, sem alterar os cálculos."
            )


# ============================================================
# ABA 7 — ANÁLISE ESPACIAL
# ============================================================

with abas[6]:

    st.header("Análise Espacial das Temperaturas")

    if not TIFFS:

        st.warning(
            "Nenhum GeoTIFF original encontrado."
        )

    else:

        opcoes = sorted(
            TIFFS.keys(),
            key=lambda x: (x[0], x[1])
        )

        selecao = st.selectbox(
            "Raster",
            opcoes,
            format_func=lambda x: (
                f"{x[0]} | {x[1]}"
            )
        )

        arquivo = TIFFS[selecao]

        try:

            r = estatisticas_raster(
                str(arquivo),
                arquivo.stat().st_mtime_ns,
                TIFF_EM_KELVIN
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Média",
                numero(r["media"]) + " °C"
            )

            c2.metric(
                "Desvio-padrão",
                numero(r["desvio"]) + " °C"
            )

            c3.metric(
                "Mínimo",
                numero(r["minimo"]) + " °C"
            )

            c4.metric(
                "Máximo",
                numero(r["maximo"]) + " °C"
            )

            ca, cb = st.columns(2)

            with ca:

                fig = px.histogram(
                    x=r["amostra"],
                    nbins=45,
                    color_discrete_sequence=[AZUL],
                    title="Distribuição espacial"
                )

                exibir(fig)

            with cb:

                fig = px.box(
                    y=r["amostra"],
                    color_discrete_sequence=[VERMELHO],
                    title="Dispersão dos pixels"
                )

                exibir(fig)

            st.subheader(
                "Autocorrelação espacial"
            )

            if st.button(
                "Calcular índice global de Moran",
                key="moran"
            ):

                indice, p_valor, n = moran_raster(
                    str(arquivo),
                    arquivo.stat().st_mtime_ns
                )

                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "Moran I",
                    numero(indice, 4)
                )

                # MESMA FORMATAÇÃO PARA VALOR-P
                c2.metric(
                    "Valor-p",
                    formatar_p_valor(p_valor)
                )

                c3.metric(
                    "Células",
                    f"{n:,}"
                )

                texto(
                    "O índice global de Moran "
                    "investiga a semelhança "
                    "espacial entre células "
                    "vizinhas. Valores positivos "
                    "indicam agrupamento de valores "
                    "semelhantes, enquanto valores "
                    "negativos sugerem contrastes "
                    "entre vizinhos. O cálculo "
                    "utiliza uma grade reduzida "
                    "e é exploratório."
                )

            st.caption(
                "Utilize os TIFFs originais "
                "recortados a Pernambuco. "
                "As médias dos pixels não são "
                "ponderadas pela área."
            )

        except Exception as erro:

            st.error(
                f"Erro na análise espacial: {erro}"
            )


# ============================================================
# ABA 8 — PREVISÃO
# ============================================================

with abas[7]:

    st.header("Modelagem e Previsão Térmica")

    if dados is None:

        st.info(
            "Aguardando dados diários."
        )

    else:

        variavel = st.selectbox(
            "Variável",
            VARIAVEIS,
            key="variavel_previsao"
        )

        horizonte = st.select_slider(
            "Horizonte",
            options=[3, 6, 12, 18, 24],
            value=12,
            format_func=lambda x: f"{x} meses"
        )

        mensal = serie_mensal(
            dados,
            variavel
        )

        try:

            futuro, validacao, desempenho = (
                previsao_validada(
                    mensal,
                    horizonte
                )
            )

            ca, cb = st.columns(2)

            with ca:

                fig = go.Figure()

                fig.add_trace(
                    go.Scatter(
                        x=mensal.index,
                        y=mensal.values,
                        name="Observado",
                        line=dict(color=AZUL)
                    )
                )

                fig.add_trace(
                    go.Scatter(
                        x=futuro.index,
                        y=futuro.values,
                        name="Previsto",
                        line=dict(
                            color=VERMELHO,
                            dash="dash",
                            width=3
                        )
                    )
                )

                fig.update_layout(
                    title="Histórico e previsão",
                    xaxis_title="Data",
                    yaxis_title="Temperatura (°C)"
                )

                exibir(fig)

            with cb:

                fig = px.bar(
                    x=futuro.index,
                    y=futuro.values,
                    color=futuro.values,
                    color_continuous_scale=PALETA_TERMICA,
                    title="Temperaturas previstas"
                )

                fig.update_layout(
                    coloraxis_showscale=False
                )

                exibir(fig)

            st.subheader(
                "Validação retrospectiva"
            )

            cc, cd = st.columns(2)

            with cc:

                fig = px.line(
                    validacao,
                    x="Data",
                    y=[
                        "Observado",
                        "Holt_Winters",
                        "Sazonal_ingenua"
                    ],
                    title="Modelos e valores observados"
                )

                exibir(fig)

            with cd:

                fig = px.bar(
                    desempenho,
                    x="Modelo",
                    y="MAE",
                    color="Modelo",
                    color_discrete_sequence=[
                        AZUL,
                        VERMELHO
                    ],
                    title="Erro absoluto médio"
                )

                exibir(fig)

            st.dataframe(
                desempenho,
                use_container_width=True,
                hide_index=True
            )

            exportar(
                desempenho,
                "validacao_previsao_pe.csv"
            )

            texto(
                "A previsão por Holt–Winters "
                "é comparada ao modelo sazonal "
                "ingênuo por validação retrospectiva "
                "nos últimos 12 meses observados. "
                "MAE e RMSE menores indicam "
                "melhor desempenho nesse "
                "intervalo, mas não asseguram "
                "o mesmo desempenho futuro."
            )

        except Exception as erro:

            st.warning(
                "Previsão indisponível: "
                + str(erro)
            )


# ============================================================
# ABA 9 — CONCLUSÃO
# ============================================================

with abas[8]:

    st.header("Conclusão")

    if dados is None:

        st.info(
            "A conclusão será calculada "
            "após a leitura da planilha."
        )

    else:

        tabela = resumo_periodos(
            dados
        )

        for variavel in VARIAVEIS:

            r = tabela[
                tabela["variavel"] == variavel
            ].dropna(subset=["media"])

            if r.empty:
                continue

            maior = r.loc[
                r["media"].idxmax()
            ]

            menor = r.loc[
                r["media"].idxmin()
            ]

            media_geral = dados[
                COLUNAS[variavel]
            ].mean()

            st.subheader(variavel)

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Média geral",
                numero(media_geral) + " °C"
            )

            c2.metric(
                "Maior média por período",
                numero(maior["media"]) + " °C"
            )

            c3.metric(
                "Menor média por período",
                numero(menor["media"]) + " °C"
            )

            texto(
                f"A análise da {variavel.lower()} "
                f"em Pernambuco apresentou "
                f"média geral de "
                f"{media_geral:.2f} °C entre "
                f"os registros disponíveis. "
                f"A maior média por período "
                f"foi observada em "
                f"{maior['periodo']}, atingindo "
                f"{maior['media']:.2f} °C. "
                f"A menor média ocorreu em "
                f"{menor['periodo']}, com "
                f"{menor['media']:.2f} °C."
            )

        st.subheader(
            "Considerações finais"
        )

        texto(
            "A integração de séries temporais "
            "e informações cartográficas "
            "permite caracterizar diferentes "
            "aspectos da dinâmica térmica "
            "de Pernambuco. As análises "
            "descritivas identificam padrões "
            "de distribuição e variabilidade, "
            "enquanto as técnicas temporais "
            "permitem examinar oscilações, "
            "sazonalidade e persistência "
            "dos registros. As medidas de "
            "dependência espacial contribuem "
            "para investigar a organização "
            "geográfica das temperaturas. "
            "As projeções estatísticas "
            "representam resultados exploratórios "
            "e devem ser interpretadas conforme "
            "sua validação e as limitações "
            "dos dados utilizados."
        )


# ============================================================
# RODAPÉ
# ============================================================

st.markdown(
    '<div class="rodape">'
    'OBSERVATÓRIO CLIMÁTICO DE PERNAMBUCO'
    '<br>'
    'Temperatura do Ar e da Superfície | 1991–2026'
    '<br>'
    'Denilson • Jader • Silvio • Débora' 
    '</div>',
    unsafe_allow_html=True
)
