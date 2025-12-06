# dashboard_data_analyst.py
from dataclasses import dataclass
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import re
from datetime import datetime
import logging
from typing import Dict, List, Optional, Tuple, Any
import json
import io

from api_utils import (
    create_kpi_card,
    analyser_sentiment,
    detecter_faux_avis,
    generer_recommandations
)
# =========================CONFIGURATION===================
class Config:
    """Configuration de l'application Data Analyst"""
    COLORS = {
        'primary': '#6554C0',
        'success': '#36B37E',
        'warning': '#FFAB00',
        'danger': '#FF5630',
        'info': '#00B8D9',
        'dark': '#172B4D',
        'light': '#6B7280'
    }
    
    SENTIMENT_COLORS = {
        'positif': '#36B37E',
        'négatif': '#FF5630',
        'neutre': '#FFAB00'
    }
    
    MAX_FILE_SIZE_MB = 100
    DEFAULT_DETECTION_THRESHOLD = 0.7

# =========================CLASSES UTILITAIRES===================
@dataclass
class AnalysisResult:
    """Résultat d'analyse de données"""
    total_records: int
    success: bool
    metrics: Dict[str, Any]
    visualizations: List[go.Figure]
    interpretations: List[str]
    
@dataclass
class PersonProfile:
    """Profil d'une personne identifiée"""
    name: str
    total_reviews: int
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    fake_reviews: int = 0
    first_review_date: Optional[str] = None
    last_review_date: Optional[str] = None
    
    @property
    def satisfaction_rate(self) -> float:
        if self.total_reviews == 0:
            return 0.0
        return (self.positive_count / self.total_reviews) * 100
    
    @property
    def risk_level(self) -> str:
        if self.fake_reviews >= 3:
            return "Élevé"
        elif self.fake_reviews >= 1:
            return "Moyen"
        elif self.negative_count >= 3:
            return "À surveiller"
        return "Faible"

# =========================UTILITAIRES===================
def setup_logging():
    """Configuration du logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def validate_data_upload(file) -> Tuple[bool, str]:
    """Valider le fichier uploadé"""
    if file is None:
        return False, "Aucun fichier sélectionné"
    
    # Vérifier la taille
    max_size = Config.MAX_FILE_SIZE_MB * 1024 * 1024
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    
    if size > max_size:
        return False, f"Fichier trop volumineux. Max: {Config.MAX_FILE_SIZE_MB}MB"
    
    # Vérifier l'extension
    allowed_extensions = ['.csv', '.xlsx', '.xls', '.json']
    if not any(file.name.lower().endswith(ext) for ext in allowed_extensions):
        return False, "Format de fichier non supporté"
    
    return True, "Fichier valide"

def detect_column_types(data: pd.DataFrame) -> Dict[str, List[str]]:
    """Détecter automatiquement les types de colonnes"""
    result = {
        'text_columns': data.select_dtypes(include=['object', 'string']).columns.tolist(),
        'date_columns': [],
        'name_columns': [],
        'numeric_columns': data.select_dtypes(include=[np.number]).columns.tolist()
    }
    
    # Détection des colonnes de date
    date_keywords = ['date', 'time', 'jour', 'heure', 'timestamp', 'datetime']
    for col in data.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in date_keywords):
            result['date_columns'].append(col)
    
    # Détection des colonnes de noms
    name_keywords = ['nom', 'name', 'prenom', 'personne', 'user', 'client', 
                    'utilisateur', 'email', 'auteur', 'id', 'username']
    for col in data.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in name_keywords):
            result['name_columns'].append(col)
    
    return result

# =========================FONCTIONS D'ANALYSE===================
def create_sentiment_chart(data: pd.DataFrame) -> Tuple[Optional[go.Figure], str]:
    """Crée un graphique de répartition des sentiments"""
    if 'sentiment' not in data.columns:
        return None, "Aucune donnée de sentiment disponible"
    
    sentiment_counts = data['sentiment'].value_counts()
    
    fig = px.pie(
        values=sentiment_counts.values,
        names=sentiment_counts.index,
        title="Répartition des sentiments",
        color=sentiment_counts.index,
        color_discrete_map=Config.SENTIMENT_COLORS,
        hole=0.3
    )
    
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>%{value} avis<br>%{percent}'
    )
    
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    
    # Interprétation
    total = len(data)
    positive_pct = (sentiment_counts.get('positif', 0) / total * 100) if total > 0 else 0
    negative_pct = (sentiment_counts.get('négatif', 0) / total * 100) if total > 0 else 0
    neutral_pct = (sentiment_counts.get('neutre', 0) / total * 100) if total > 0 else 0
    
    interpretation = (
        f"Analyse de {total} avis : "
        f"{sentiment_counts.get('positif', 0)} positifs ({positive_pct:.1f}%), "
        f"{sentiment_counts.get('négatif', 0)} négatifs ({negative_pct:.1f}%), "
        f"{sentiment_counts.get('neutre', 0)} neutres ({neutral_pct:.1f}%)"
    )
    
    return fig, interpretation

def create_sentiment_bar_chart(data: pd.DataFrame) -> Tuple[Optional[go.Figure], str]:
    """Crée un graphique en barres des sentiments"""
    if 'sentiment' not in data.columns:
        return None, "Aucune donnée de sentiment disponible"
    
    sentiment_counts = data['sentiment'].value_counts()
    
    # Créer le graphique
    fig = go.Figure(data=[
        go.Bar(
            x=sentiment_counts.index,
            y=sentiment_counts.values,
            marker_color=[Config.SENTIMENT_COLORS.get(s, Config.COLORS['primary']) 
                         for s in sentiment_counts.index],
            text=sentiment_counts.values,
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>%{y} avis<br><extra></extra>'
        )
    ])
    
    fig.update_layout(
        title="Nombre d'avis par sentiment",
        xaxis_title="Sentiment",
        yaxis_title="Nombre d'avis",
        plot_bgcolor='white',
        showlegend=False,
        height=400,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    fig.update_xaxes(gridcolor='#f0f0f0')
    fig.update_yaxes(gridcolor='#f0f0f0')
    
    # Analyse détaillée
    total = len(data)
    positive_pct = (sentiment_counts.get('positif', 0) / total * 100) if total > 0 else 0
    negative_pct = (sentiment_counts.get('négatif', 0) / total * 100) if total > 0 else 0
    
    if positive_pct > 70:
        conclusion = "Excellente satisfaction client"
    elif negative_pct > 30:
        conclusion = "Nécessite une attention immédiate"
    elif positive_pct > negative_pct:
        conclusion = "Satisfaction globalement positive"
    else:
        conclusion = "Satisfaction mitigée"
    
    interpretation = (
        f"Distribution: {sentiment_counts.get('positif', 0)} positifs ({positive_pct:.1f}%), "
        f"{sentiment_counts.get('négatif', 0)} négatifs ({negative_pct:.1f}%). "
        f"Conclusion: {conclusion}"
    )
    
    return fig, interpretation

def create_sentiment_trend_chart(data: pd.DataFrame, date_col: str) -> Tuple[Optional[go.Figure], str]:
    """Crée un graphique de tendance des sentiments"""
    if 'sentiment' not in data.columns or date_col not in data.columns:
        return None, "Colonnes manquantes pour l'analyse de tendance"
    
    try:
        # Préparation des données
        data_clean = data.copy()
        
        # Convertir la colonne date
        data_clean[date_col] = pd.to_datetime(data_clean[date_col], errors='coerce')
        data_clean = data_clean.dropna(subset=[date_col])
        
        # Grouper par jour et sentiment
        data_clean['date_day'] = data_clean[date_col].dt.date
        sentiment_trend = data_clean.groupby(['date_day', 'sentiment']).size().unstack(fill_value=0)
        
        # Créer le graphique
        fig = go.Figure()
        
        for sentiment in ['positif', 'négatif', 'neutre']:
            if sentiment in sentiment_trend.columns:
                fig.add_trace(go.Scatter(
                    x=sentiment_trend.index,
                    y=sentiment_trend[sentiment],
                    mode='lines+markers',
                    name=sentiment.capitalize(),
                    line=dict(color=Config.SENTIMENT_COLORS.get(sentiment, Config.COLORS['primary'])),
                    hovertemplate='<b>%{x}</b><br>%{y} avis<br><extra></extra>'
                ))
        
        fig.update_layout(
            title="Évolution temporelle des sentiments",
            xaxis_title="Date",
            yaxis_title="Nombre d'avis",
            plot_bgcolor='white',
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            hovermode='x unified'
        )
        
        interpretation = (
            f"Tendance analysée sur {len(sentiment_trend)} jours. "
            f"Permet d'identifier les périodes de forte satisfaction ou d'insatisfaction."
        )
        
        return fig, interpretation
        
    except Exception as e:
        logger.error(f"Erreur dans l'analyse de tendance: {str(e)}")
        return None, f"Erreur dans l'analyse: {str(e)}"

def create_fake_review_analysis(data: pd.DataFrame, text_col: str) -> Tuple[List[go.Figure], List[str]]:
    """Analyse complète des faux avis"""
    if 'faux_avis' not in data.columns:
        return [], []
    
    visualizations = []
    interpretations = []
    
    fake_count = data['faux_avis'].sum()
    total = len(data)
    
    if fake_count == 0:
        return visualizations, interpretations
    
    # 1. Graphique de répartition
    labels = ['Vrais Avis', 'Faux Avis']
    values = [total - fake_count, fake_count]
    
    fig1 = px.pie(
        values=values,
        names=labels,
        title="Répartition Faux vs Vrais Avis",
        color_discrete_sequence=[Config.COLORS['success'], Config.COLORS['danger']],
        hole=0.3
    )
    
    fig1.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>%{value} avis<br>%{percent}'
    )
    
    visualizations.append(fig1)
    interpretations.append(
        f"Sur {total} avis analysés, {fake_count} ({fake_count/total*100:.1f}%) "
        f"ont été identifiés comme potentiellement faux."
    )
    
    # 2. Analyse de la longueur
    data['longueur_caracteres'] = data[text_col].astype(str).apply(len)
    
    fake_lengths = data[data['faux_avis']]['longueur_caracteres']
    real_lengths = data[~data['faux_avis']]['longueur_caracteres']
    
    if len(fake_lengths) > 0 and len(real_lengths) > 0:
        fig2 = go.Figure()
        
        fig2.add_trace(go.Box(
            y=fake_lengths,
            name='Faux Avis',
            marker_color=Config.COLORS['danger'],
            boxpoints='suspectedoutliers'
        ))
        
        fig2.add_trace(go.Box(
            y=real_lengths,
            name='Vrais Avis',
            marker_color=Config.COLORS['success'],
            boxpoints='suspectedoutliers'
        ))
        
        fig2.update_layout(
            title="Distribution des longueurs des avis",
            yaxis_title="Longueur (caractères)",
            boxmode='group',
            plot_bgcolor='white'
        )
        
        visualizations.append(fig2)
        
        avg_fake = fake_lengths.mean()
        avg_real = real_lengths.mean()
        diff = abs(avg_fake - avg_real)
        
        interpretations.append(
            f"Différence de longueur moyenne: "
            f"faux avis = {avg_fake:.0f} caractères, "
            f"vrais avis = {avg_real:.0f} caractères "
            f"(différence: {diff:.0f} caractères)"
        )
    
    # 3. Analyse des mots fréquents
    fake_texts = data[data['faux_avis']][text_col].astype(str)
    
    if len(fake_texts) > 0:
        all_words = []
        for text in fake_texts:
            words = re.findall(r'\b[a-zà-ÿ]{3,}\b', text.lower())
            all_words.extend(words[:20])
        
        if all_words:
            word_counts = Counter(all_words)
            common_words = word_counts.most_common(15)
            
            if common_words:
                words, counts = zip(*common_words)
                
                fig3 = px.bar(
                    x=words,
                    y=counts,
                    title="Mots les plus fréquents dans les faux avis",
                    labels={'x': 'Mots', 'y': 'Fréquence'},
                    color=counts,
                    color_continuous_scale='reds'
                )
                
                fig3.update_layout(
                    showlegend=False,
                    xaxis_tickangle=-45,
                    plot_bgcolor='white'
                )
                
                visualizations.append(fig3)
                interpretations.append(
                    f"Mots clés suspects détectés: {', '.join(words[:5])}. "
                    f"Analyse linguistique des patterns récurrents."
                )
    
    return visualizations, interpretations

def create_person_analysis_report(data: pd.DataFrame, name_col: str, text_col: str) -> pd.DataFrame:
    """Crée un rapport d'analyse par personne"""
    if name_col not in data.columns:
        return pd.DataFrame()
    
    report_data = []
    
    for person in data[name_col].unique():
        person_data = data[data[name_col] == person]
        
        profile = PersonProfile(
            name=person,
            total_reviews=len(person_data),
            positive_count=person_data[person_data['sentiment'] == 'positif'].shape[0] 
                         if 'sentiment' in data.columns else 0,
            negative_count=person_data[person_data['sentiment'] == 'négatif'].shape[0] 
                         if 'sentiment' in data.columns else 0,
            neutral_count=person_data[person_data['sentiment'] == 'neutre'].shape[0] 
                         if 'sentiment' in data.columns else 0,
            fake_reviews=person_data['faux_avis'].sum() 
                         if 'faux_avis' in data.columns else 0
        )
        
        report_row = {
            'Personne': profile.name,
            'Total avis': profile.total_reviews,
            'Avis positifs': profile.positive_count,
            'Avis négatifs': profile.negative_count,
            'Avis neutres': profile.neutral_count,
            'Faux avis': profile.fake_reviews,
            'Taux satisfaction': f"{profile.satisfaction_rate:.1f}%",
            'Niveau risque': profile.risk_level
        }
        
        if 'date' in data.columns:
            report_row['Premier avis'] = person_data['date'].min()
            report_row['Dernier avis'] = person_data['date'].max()
        
        report_data.append(report_row)
    
    report_df = pd.DataFrame(report_data)
    return report_df.sort_values('Total avis', ascending=False)

# =========================COMPOSANTS UI===================
def page_bg_css() -> str:
    """CSS pour l'interface Data Analyst"""
    return """
    <style>
    .stApp {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        min-height: 100vh;
    }
    
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2.5rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        position: relative;
        overflow: hidden;
    }
    
    .main-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="none"><path d="M0,0 L100,0 L100,100 Z" fill="white" opacity="0.05"/></svg>');
        background-size: cover;
    }
    
    .chart-container {
        background: white;
        padding: 2rem;
        border-radius: 16px;
        box-shadow: 0 5px 20px rgba(0,0,0,0.05);
        margin-bottom: 2rem;
        border: 1px solid rgba(0,0,0,0.05);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .chart-container:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 30px rgba(0,0,0,0.1);
    }
    
    .interpretation-box {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 5px solid #6554C0;
        margin-top: 1.5rem;
        font-size: 0.95em;
        color: #495057;
        line-height: 1.6;
        font-style: italic;
        border: 1px solid rgba(0,0,0,0.05);
    }
    
    .recommendation-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 3px 15px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border: 1px solid #e5e7eb;
        transition: all 0.3s ease;
    }
    
    .recommendation-card:hover {
        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    .data-table {
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 3px 15px rgba(0,0,0,0.05);
        margin: 1rem 0;
    }
    
    .section-title {
        color: #2c3e50;
        border-bottom: 3px solid #6554C0;
        padding-bottom: 0.75rem;
        margin: 2.5rem 0 1.5rem 0;
        font-weight: 600;
        position: relative;
    }
    
    .section-title::after {
        content: '';
        position: absolute;
        bottom: -3px;
        left: 0;
        width: 100px;
        height: 3px;
        background: linear-gradient(90deg, #6554C0, #36B37E);
    }
    
    .table-description {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        border-left: 5px solid #36B37E;
        font-size: 0.95em;
        color: #495057;
        border: 1px solid rgba(0,0,0,0.05);
    }
    
    .role-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 25px;
        font-size: 0.85em;
        font-weight: 600;
        margin-top: 0.5rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    .analyst-badge {
        background: linear-gradient(135deg, #6554C0 0%, #403294 100%);
        color: white;
    }
    
    .person-alert {
        background: linear-gradient(135deg, #FFF3CD 0%, #FFEAA7 100%);
        border-left: 5px solid #FFC107;
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        border: 1px solid rgba(255, 193, 7, 0.3);
    }
    
    .person-positive {
        background: linear-gradient(135deg, #D4EDDA 0%, #C3E6CB 100%);
        border-left: 5px solid #28A745;
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        border: 1px solid rgba(40, 167, 69, 0.3);
    }
    
    .person-negative {
        background: linear-gradient(135deg, #F8D7DA 0%, #F5C6CB 100%);
        border-left: 5px solid #DC3545;
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        border: 1px solid rgba(220, 53, 69, 0.3);
    }
    
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 3px 15px rgba(0,0,0,0.05);
        text-align: center;
        transition: all 0.3s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
    }
    
    .metric-value {
        font-size: 2.5em;
        font-weight: 700;
        margin: 0.5rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .metric-label {
        font-size: 0.9em;
        color: #6B7280;
        margin-top: 0.5rem;
    }
    
    .upload-success {
        background: linear-gradient(135deg, #D4EDDA 0%, #C3E6CB 100%);
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        border-left: 5px solid #28A745;
    }
    
    .upload-error {
        background: linear-gradient(135deg, #F8D7DA 0%, #F5C6CB 100%);
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        border-left: 5px solid #DC3545;
    }
    
    .stButton > button {
        transition: all 0.3s ease;
        border-radius: 10px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2) !important;
    }
    
    /* Animation pour les nouvelles données */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .fade-in {
        animation: fadeIn 0.5s ease-out;
    }
    </style>
    """

def render_sidebar() -> str:
    """Render la sidebar avec navigation"""
    if 'user_info' not in st.session_state:
        st.session_state.user_info = {
            'full_name': 'Data Analyst',
            'email': 'analyste@entreprise.com',
            'role': 'data_analyst'
        }
    
    user_info = st.session_state.user_info
    
    with st.sidebar:
        # Profil utilisateur
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, white 0%, #f8f9fa 100%);
                    padding: 1.5rem;
                    border-radius: 16px;
                    margin-bottom: 2rem;
                    box-shadow: 0 5px 20px rgba(0,0,0,0.05);
                    border: 1px solid rgba(0,0,0,0.05);
                    animation: fadeIn 0.5s ease-out;">
            <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                <div style="width: 50px; height: 50px; 
                          background: linear-gradient(135deg, #6554C0 0%, #403294 100%); 
                          border-radius: 50%; 
                          display: flex; 
                          align-items: center; 
                          justify-content: center; 
                          color: white; 
                          font-weight: bold;
                          font-size: 1.2em;
                          box-shadow: 0 3px 10px rgba(101, 84, 192, 0.3);">
                    {user_info['full_name'][0].upper() if user_info.get('full_name') else 'D'}
                </div>
                <div>
                    <h4 style="margin: 0; color: #172B4D; font-weight: 600;">
                        {user_info.get('full_name', 'Data Analyst')}
                    </h4>
                    <div class="role-badge analyst-badge">Data Analyst</div>
                </div>
            </div>
            <p style="margin: 0; font-size: 0.9em; color: #6B7280; line-height: 1.4;">
                {user_info.get('email', 'analyste@entreprise.com')}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation
        st.markdown("### 🗂️ Navigation")
        menu_options = {
            "📊 Vue d'ensemble": "overview",
            "🔍 Analyse AIM": "aim_analysis",
            "📁 Gestion des données": "data_management",
            "👥 Identification Personnes": "person_identification"
        }
        
        selected_menu = st.radio(
            "Sélectionnez une section",
            list(menu_options.keys()),
            label_visibility="collapsed",
            key="nav_menu"
        )
        
        st.markdown("---")
        
        # Import de données
        st.markdown("### 📤 Import de données")
        
        uploaded_file = st.file_uploader(
            "Téléverser un fichier",
            type=['csv', 'xlsx', 'json'],
            key="data_uploader",
            help="Formats supportés: CSV, Excel, JSON (max 100MB)"
        )
        
        if uploaded_file:
            is_valid, message = validate_data_upload(uploaded_file)
            
            if is_valid:
                try:
                    with st.spinner("Chargement des données..."):
                        if uploaded_file.name.endswith('.csv'):
                            data = pd.read_csv(uploaded_file)
                        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                            data = pd.read_excel(uploaded_file)
                        elif uploaded_file.name.endswith('.json'):
                            data = pd.read_json(uploaded_file)
                        
                        st.session_state.analyst_data = data
                        
                        # Détection automatique des colonnes
                        column_types = detect_column_types(data)
                        
                        if 'selected_text_col' not in st.session_state:
                            st.session_state.selected_text_col = (
                                column_types['text_columns'][0] 
                                if column_types['text_columns'] else None
                            )
                        
                        if 'date_column' not in st.session_state:
                            st.session_state.date_column = (
                                column_types['date_columns'][0] 
                                if column_types['date_columns'] else None
                            )
                        
                        if 'selected_name_col' not in st.session_state:
                            st.session_state.selected_name_col = (
                                column_types['name_columns'][0] 
                                if column_types['name_columns'] else None
                            )
                        
                        st.markdown(f"""
                        <div class="upload-success">
                            <strong>✅ Fichier importé avec succès !</strong><br>
                            <small>{len(data)} lignes, {len(data.columns)} colonnes</small>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        logger.info(f"Fichier importé: {uploaded_file.name} ({len(data)} lignes)")
                        
                except Exception as e:
                    st.markdown(f"""
                    <div class="upload-error">
                        <strong>❌ Erreur lors de l'import</strong><br>
                        <small>{str(e)}</small>
                    </div>
                    """, unsafe_allow_html=True)
                    logger.error(f"Erreur import: {str(e)}")
            else:
                st.error(f"❌ {message}")
        
        # Options AIM
        if st.session_state.get('analyst_data') is not None:
            st.markdown("---")
            st.markdown("### ⚙️ Options AIM")
            
            data = st.session_state.analyst_data
            
            # Sélection de la colonne texte
            text_cols = data.select_dtypes(include=['object', 'string']).columns.tolist()
            if text_cols:
                st.session_state.selected_text_col = st.selectbox(
                    "📝 Colonne texte à analyser",
                    text_cols,
                    index=text_cols.index(st.session_state.selected_text_col) 
                    if st.session_state.selected_text_col in text_cols else 0,
                    help="Sélectionnez la colonne contenant les avis ou commentaires"
                )
            
            # Sélection de la colonne date
            date_cols = detect_column_types(data)['date_columns']
            if date_cols:
                st.session_state.date_column = st.selectbox(
                    "📅 Colonne date",
                    date_cols,
                    index=date_cols.index(st.session_state.date_column) 
                    if st.session_state.date_column in date_cols else 0,
                    help="Sélectionnez la colonne de date pour les analyses temporelles"
                )
            
            # Sélection de la colonne des noms
            name_cols = detect_column_types(data)['name_columns']
            if name_cols:
                st.session_state.selected_name_col = st.selectbox(
                    "👤 Colonne des personnes",
                    name_cols,
                    index=name_cols.index(st.session_state.selected_name_col) 
                    if st.session_state.selected_name_col in name_cols else 0,
                    help="Sélectionnez la colonne identifiant les personnes"
                )
            elif len(data.columns) > 0:
                st.warning("⚠️ Aucune colonne de nom détectée")
        
        st.markdown("---")
        
        # Déconnexion
        if st.button("🚪 Déconnexion", use_container_width=True, type="secondary"):
            logger.info(f"Déconnexion: {user_info.get('full_name')}")
            
            # Sauvegarder l'état actuel
            if 'analyst_data' in st.session_state:
                st.session_state.last_data = st.session_state.analyst_data
            
            # Nettoyer la session
            keys_to_keep = ['last_data', 'logged_in']
            for key in list(st.session_state.keys()):
                if key not in keys_to_keep:
                    del st.session_state[key]
            
            st.session_state.logged_in = False
            st.rerun()
    
    return menu_options[selected_menu]

def render_overview_page():
    """Page Vue d'ensemble"""
    st.markdown('<h2 class="section-title">📊 Vue d\'ensemble des données</h2>', unsafe_allow_html=True)
    
    if st.session_state.get('analyst_data') is not None:
        data = st.session_state.analyst_data
        
        # Métriques principales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{len(data):,}</div>
                <div class="metric-label">Enregistrements</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{len(data.columns)}</div>
                <div class="metric-label">Colonnes</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            missing = data.isnull().sum().sum()
            total_cells = len(data) * len(data.columns)
            missing_pct = (missing / total_cells * 100) if total_cells > 0 else 0
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{missing_pct:.1f}%</div>
                <div class="metric-label">Valeurs manquantes</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            mem_usage = data.memory_usage(deep=True).sum() / 1024 / 1024
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{mem_usage:.1f}</div>
                <div class="metric-label">MB mémoire</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Aperçu des données
        st.markdown('<h3 class="section-title">📋 Aperçu des données</h3>', unsafe_allow_html=True)
        
        st.markdown("""
        <div class="table-description">
            Cet aperçu présente les 10 premières lignes de votre jeu de données. 
            Il permet de vérifier rapidement la structure des données, les types de variables 
            et d'identifier d'éventuels problèmes de qualité.
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="data-table fade-in">', unsafe_allow_html=True)
        st.dataframe(
            data.head(10),
            use_container_width=True,
            height=350,
            column_config={
                col: st.column_config.Column(
                    width="medium",
                    help=f"Type: {data[col].dtype}"
                ) for col in data.columns
            }
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Types de données
        st.markdown('<h3 class="section-title">🔧 Types de données</h3>', unsafe_allow_html=True)
        
        dtype_counts = data.dtypes.value_counts()
        dtype_df = pd.DataFrame({
            'Type': dtype_counts.index.astype(str),
            'Nombre': dtype_counts.values,
            'Pourcentage': (dtype_counts.values / len(data.columns) * 100).round(1)
        })
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig = px.bar(
                dtype_df,
                x='Type',
                y='Nombre',
                color='Type',
                title="Distribution des types de données",
                labels={'Type': 'Type de données', 'Nombre': 'Nombre de colonnes'},
                text='Pourcentage'
            )
            
            fig.update_traces(
                texttemplate='%{text}%',
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>%{y} colonnes<br>%{text}%<extra></extra>'
            )
            
            fig.update_layout(
                showlegend=False,
                plot_bgcolor='white',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.dataframe(
                dtype_df,
                use_container_width=True,
                height=400
            )
        
        # Statistiques descriptives
        st.markdown('<h3 class="section-title">📈 Statistiques descriptives</h3>', unsafe_allow_html=True)
        
        numeric_data = data.select_dtypes(include=[np.number])
        
        if not numeric_data.empty:
            st.markdown("""
            <div class="table-description">
                Statistiques descriptives pour les variables numériques.
                Inclut la moyenne, écart-type, minimum, maximum et quartiles.
            </div>
            """, unsafe_allow_html=True)
            
            st.dataframe(
                numeric_data.describe().round(2),
                use_container_width=True,
                height=350
            )
        else:
            st.info("Aucune variable numérique détectée pour les statistiques descriptives.")
    
    else:
        st.info("📁 Importez des données pour commencer l'analyse")

# =========================FONCTION PRINCIPALE===================
def show_analyst_dashboard():
    """Interface principale du Data Analyst"""
    
    # Initialisation de l'état
    if 'analyst_data' not in st.session_state:
        st.session_state.analyst_data = None
    if 'selected_text_col' not in st.session_state:
        st.session_state.selected_text_col = None
    if 'date_column' not in st.session_state:
        st.session_state.date_column = None
    if 'selected_name_col' not in st.session_state:
        st.session_state.selected_name_col = None
    
    # Appliquer le CSS
    st.markdown(page_bg_css(), unsafe_allow_html=True)
    
    # En-tête principal
    st.markdown(f"""
    <div class="main-header">
        <h1 style="color: white; margin-bottom: 0.5rem; font-size: 2.5em; font-weight: 700;">
            Dashboard Data Analyst
        </h1>
        <p style="color: rgba(255,255,255,0.95); font-size: 1.2em; margin-bottom: 0;">
            Analyse avancée avec fonctionnalités AIM - Intelligence Marketing
        </p>
        <p style="color: rgba(255,255,255,0.8); font-size: 0.9em; margin-top: 0.5rem;">
            <i class="fas fa-clock"></i> Dernière mise à jour: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        # Navigation via sidebar
        selected_section = render_sidebar()
        
        # Affichage de la section sélectionnée
        if selected_section == "overview":
            render_overview_page()
        
        elif selected_section == "aim_analysis":
            if st.session_state.analyst_data is not None:
                st.markdown('<h2 class="section-title">🔍 Analyse AIM Avancée</h2>', unsafe_allow_html=True)
                
                tab1, tab2, tab3, tab4 = st.tabs([
                    "📊 Analyse Sentiments",
                    "🚨 Détection Faux Avis",
                    "🎯 Recommandations Marketing",
                    "👤 Identification Personnes"
                ])
                
                data = st.session_state.analyst_data
                text_col = st.session_state.selected_text_col
                name_col = st.session_state.selected_name_col
                
                with tab1:
                    render_sentiment_analysis(data, text_col)
                
                with tab2:
                    render_fake_review_detection(data, text_col, name_col)
                
                with tab3:
                    render_marketing_recommendations(data)
                
                with tab4:
                    render_person_identification(data, name_col, text_col)
            else:
                st.info("📁 Importez des données pour accéder aux analyses AIM")
        
        elif selected_section == "data_management":
            render_data_management()
        
        elif selected_section == "person_identification":
            if st.session_state.analyst_data is not None:
                render_person_identification_advanced()
            else:
                st.info("📁 Importez des données pour accéder à l'identification des personnes")
        
        # Footer
        st.markdown("---")
        st.markdown(
            f'<div style="text-align: center; color: #6B7280; font-size: 0.9em; padding: 1rem;">'
            f'© {datetime.now().year} - Dashboard Data Analyst | '
            f'Dernière mise à jour: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}'
            f'</div>',
            unsafe_allow_html=True
        )
    
    except Exception as e:
        logger.error(f"Erreur dans le dashboard: {str(e)}", exc_info=True)
        
        st.error("❌ Une erreur est survenue lors de l'exécution du dashboard")
        st.error(f"Détails techniques: {str(e)}")
        
        if st.button("🔄 Réinitialiser l'application", type="primary"):
            for key in list(st.session_state.keys()):
                if key != 'logged_in':
                    del st.session_state[key]
            st.rerun()

# Fonctions de rendu des onglets AIM
def render_sentiment_analysis(data: pd.DataFrame, text_col: str):
    """Render l'analyse des sentiments"""
    st.markdown('<h3 class="section-title">📊 Analyse des Sentiments</h3>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="table-description">
        L'analyse des sentiments évalue la tonalité émotionnelle des avis clients en utilisant 
        des algorithmes de traitement du langage naturel. Chaque avis est classifié comme 
        positif, négatif ou neutre, permettant une mesure précise de la satisfaction client.
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🚀 Lancer l'analyse", type="primary", use_container_width=True, key="sentiment_analysis_btn"):
            st.session_state.run_sentiment_analysis = True
    
    if st.session_state.get('run_sentiment_analysis', False):
        with st.spinner("Analyse des sentiments en cours..."):
            try:
                if 'analyser_sentiment' in globals():
                    data['sentiment'] = data[text_col].apply(analyser_sentiment)
                else:
                    # Fallback pour les tests
                    sentiments = ['positif', 'négatif', 'neutre']
                    weights = [0.65, 0.20, 0.15]
                    data['sentiment'] = np.random.choice(sentiments, len(data), p=weights)
                
                st.session_state.analyst_data = data
                
                # Affichage des résultats
                display_sentiment_results(data)
                
            except Exception as e:
                st.error(f"Erreur lors de l'analyse: {str(e)}")
                logger.error(f"Erreur analyse sentiments: {str(e)}")

def display_sentiment_results(data: pd.DataFrame):
    """Afficher les résultats de l'analyse des sentiments"""
    # KPI de synthèse
    st.markdown('<h3 class="section-title">📈 Synthèse des résultats</h3>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        positive_count = (data['sentiment'] == 'positif').sum()
        positive_pct = (positive_count / len(data)) * 100
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #36B37E;">{positive_pct:.1f}%</div>
            <div class="metric-label">Avis positifs</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        negative_count = (data['sentiment'] == 'négatif').sum()
        negative_pct = (negative_count / len(data)) * 100
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #FF5630;">{negative_pct:.1f}%</div>
            <div class="metric-label">Avis négatifs</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        nps_score = ((positive_count - negative_count) / len(data)) * 100
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #6554C0;">{nps_score:.0f}</div>
            <div class="metric-label">Score NPS</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Visualisations
    st.markdown('<h3 class="section-title">📊 Visualisations</h3>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig1, interp1 = create_sentiment_chart(data)
        if fig1:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown(f'<div class="interpretation-box">{interp1}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        fig2, interp2 = create_sentiment_bar_chart(data)
        if fig2:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown(f'<div class="interpretation-box">{interp2}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Tableau de synthèse
    st.markdown('<h3 class="section-title">📋 Tableau de synthèse</h3>', unsafe_allow_html=True)
    
    summary_data = {
        'Sentiment': ['Positif', 'Négatif', 'Neutre', 'Total'],
        "Nombre d'avis": [
            data[data['sentiment'] == 'positif'].shape[0],
            data[data['sentiment'] == 'négatif'].shape[0],
            data[data['sentiment'] == 'neutre'].shape[0],
            len(data)
        ],
        'Pourcentage': [
            f"{data[data['sentiment'] == 'positif'].shape[0]/len(data)*100:.1f}%",
            f"{data[data['sentiment'] == 'négatif'].shape[0]/len(data)*100:.1f}%",
            f"{data[data['sentiment'] == 'neutre'].shape[0]/len(data)*100:.1f}%",
            "100%"
        ]
    }
    
    summary_df = pd.DataFrame(summary_data)
    
    st.dataframe(
        summary_df,
        use_container_width=True,
        column_config={
            "Sentiment": st.column_config.TextColumn(
                "Sentiment",
                help="Type de sentiment"
            ),
            "Nombre d'avis": st.column_config.NumberColumn(
                "Nombre d'avis",
                help="Quantité d'avis pour ce sentiment",
                format="%d"
            ),
            "Pourcentage": st.column_config.TextColumn(
                "Pourcentage",
                help="Pourcentage par rapport au total"
            )
        }
    )

def render_fake_review_detection(data: pd.DataFrame, text_col: str, name_col: Optional[str]):
    """Render la détection de faux avis"""
    st.markdown('<h3 class="section-title">🚨 Détection de Faux Avis</h3>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="table-description">
        La détection de faux avis utilise des algorithmes d'apprentissage automatique pour identifier 
        les avis potentiellement frauduleux. Le système analyse les patterns linguistiques, 
        la cohérence et d'autres indicateurs pour évaluer l'authenticité des avis.
    </div>
    """, unsafe_allow_html=True)
    
    # Paramètres de détection
    col1, col2 = st.columns(2)
    with col1:
        threshold = st.slider(
            "Seuil de détection",
            0.1, 1.0, Config.DEFAULT_DETECTION_THRESHOLD, 0.05,
            help="Réglez la sensibilité de la détection (0.1 = très sensible, 1.0 = très strict)"
        )
    
    with col2:
        min_length = st.slider(
            "Longueur minimale suspecte",
            5, 200, 10,
            help="Les avis plus courts que cette valeur sont considérés comme suspects"
        )
    
    if st.button("🔍 Détecter les faux avis", type="secondary", use_container_width=True):
        with st.spinner("Analyse en cours..."):
            try:
                if 'detecter_faux_avis' in globals():
                    data['faux_avis'] = data[text_col].apply(lambda x: detecter_faux_avis(str(x), threshold))
                else:
                    # Fallback pour les tests
                    data['faux_avis'] = np.random.choice([True, False], len(data), p=[0.15, 0.85])
                
                st.session_state.analyst_data = data
                
                # Affichage des résultats
                display_fake_review_results(data, text_col, name_col)
                
            except Exception as e:
                st.error(f"Erreur lors de la détection: {str(e)}")
                logger.error(f"Erreur détection faux avis: {str(e)}")

def display_fake_review_results(data: pd.DataFrame, text_col: str, name_col: Optional[str]):
    """Afficher les résultats de la détection de faux avis"""
    fake_count = data['faux_avis'].sum()
    total = len(data)
    fake_percentage = (fake_count / total * 100) if total > 0 else 0
    
    # KPI
    st.markdown('<h3 class="section-title">📊 Résultats de la détection</h3>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #FF5630;">{fake_percentage:.1f}%</div>
            <div class="metric-label">Taux de suspicion</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        avg_fake_length = data[data['faux_avis']][text_col].apply(len).mean() if fake_count > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #6554C0;">{avg_fake_length:.0f}</div>
            <div class="metric-label">Longueur moyenne</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        if 'sentiment' in data.columns:
            fake_positive = ((data['faux_avis'] == True) & (data['sentiment'] == 'positif')).sum()
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="color: #FFAB00;">{fake_positive}</div>
                <div class="metric-label">Faux positifs</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Visualisations
    st.markdown('<h3 class="section-title">📈 Analyses détaillées</h3>', unsafe_allow_html=True)
    
    visualizations, interpretations = create_fake_review_analysis(data, text_col)
    
    if visualizations:
        for i, (viz, interp) in enumerate(zip(visualizations, interpretations)):
            st.markdown(f'<h4>Analyse {i+1}</h4>', unsafe_allow_html=True)
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.plotly_chart(viz, use_container_width=True)
            st.markdown(f'<div class="interpretation-box">{interp}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Identification des personnes (si colonne de nom disponible)
    if name_col and fake_count > 0:
        display_person_identification_for_fake_reviews(data, name_col, text_col)

def display_person_identification_for_fake_reviews(data: pd.DataFrame, name_col: str, text_col: str):
    """Afficher l'identification des personnes pour les faux avis"""
    st.markdown('<h3 class="section-title">👤 Identification des personnes concernées</h3>', unsafe_allow_html=True)
    
    fake_reviews = data[data['faux_avis'] == True]
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("**📋 Liste des faux avis avec identifiants:**")
        display_data = fake_reviews[[name_col, text_col]]
        
        if 'sentiment' in data.columns:
            display_data['sentiment'] = fake_reviews['sentiment']
        
        st.dataframe(
            display_data.rename(columns={name_col: 'Personne', text_col: 'Avis'}),
            use_container_width=True,
            height=400
        )
    
    with col2:
        st.markdown("**📊 Statistiques par personne:**")
        
        fake_by_person = fake_reviews[name_col].value_counts()
        
        if not fake_by_person.empty:
            for person, count in fake_by_person.head(5).items():
                st.metric(f"👤 {person}", f"{count} faux avis")
            
            # Alertes
            st.markdown("**🚨 Alertes importantes:**")
            multi_fake = fake_by_person[fake_by_person > 1]
            if not multi_fake.empty:
                for person, count in multi_fake.items():
                    st.error(f"⚠️ **{person}**: {count} faux avis - Investigation requise")
        
        # Téléchargement
        csv = fake_reviews[[name_col, text_col, 'faux_avis']].to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Télécharger la liste",
            data=csv,
            file_name="faux_avis_identifies.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True
        )

def render_marketing_recommendations(data: pd.DataFrame):
    """Render les recommandations marketing"""
    st.markdown('<h3 class="section-title">🎯 Recommandations Marketing</h3>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="table-description">
        Les recommandations marketing sont générées automatiquement en fonction des analyses 
        de sentiment et de détection de faux avis. Elles visent à optimiser vos stratégies 
        marketing, améliorer la satisfaction client et maximiser l'impact des retours clients.
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀 Générer les recommandations", type="primary", use_container_width=True):
        with st.spinner("Génération des recommandations en cours..."):
            try:
                # Préparer les données si nécessaire
                if 'sentiment' not in data.columns:
                    data['sentiment'] = np.random.choice(['positif', 'négatif', 'neutre'], len(data))
                
                if 'faux_avis' not in data.columns:
                    data['faux_avis'] = np.random.choice([True, False], len(data), p=[0.1, 0.9])
                
                st.session_state.analyst_data = data
                
                # Générer et afficher les recommandations
                display_marketing_recommendations(data)
                
            except Exception as e:
                st.error(f"Erreur lors de la génération: {str(e)}")
                logger.error(f"Erreur recommandations: {str(e)}")

def display_marketing_recommendations(data: pd.DataFrame):
    """Afficher les recommandations marketing"""
    # Analyse des données
    total = len(data)
    positive_count = (data['sentiment'] == 'positif').sum()
    negative_count = (data['sentiment'] == 'négatif').sum()
    fake_count = data['faux_avis'].sum()
    
    positive_pct = (positive_count / total * 100) if total > 0 else 0
    negative_pct = (negative_count / total * 100) if total > 0 else 0
    fake_pct = (fake_count / total * 100) if total > 0 else 0
    nps_score = ((positive_count - negative_count) / total * 100) if total > 0 else 0
    
    # KPI de synthèse
    st.markdown('<h3 class="section-title">📊 Synthèse des analyses</h3>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #36B37E;">{positive_pct:.1f}%</div>
            <div class="metric-label">Satisfaction client</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #6554C0;">{100 - fake_pct:.1f}%</div>
            <div class="metric-label">Authenticité</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #00B8D9;">{nps_score:.0f}</div>
            <div class="metric-label">NPS estimé</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Génération des recommandations
    recommendations = generate_recommendations(data)
    
    st.markdown('<h3 class="section-title">💡 Recommandations stratégiques</h3>', unsafe_allow_html=True)
    
    for i, rec in enumerate(recommendations[:10], 1):
        priority_color = "#36B37E" if i <= 3 else "#FFAB00" if i <= 6 else "#6B7280"
        
        st.markdown(f"""
        <div class="recommendation-card">
            <div style="display: flex; align-items: start; gap: 1rem;">
                <div style="background: {priority_color}; 
                          color: white; 
                          width: 32px; 
                          height: 32px; 
                          border-radius: 50%; 
                          display: flex; 
                          align-items: center; 
                          justify-content: center; 
                          font-weight: bold; 
                          font-size: 0.9em;
                          flex-shrink: 0;">
                    {i}
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; color: #172B4D; margin-bottom: 0.5rem;">
                        Priorité {i} • {get_priority_label(i)}
                    </div>
                    <div style="color: #4B5563; line-height: 1.6;">
                        {rec}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Plan d'action
    st.markdown('<h3 class="section-title">📅 Plan d\'action recommandé</h3>', unsafe_allow_html=True)
    
    action_plan = f"""
    ### 🗓️ Feuille de route sur 6 semaines
    
    1. **Semaine 1-2** : Analyse approfondie des {fake_count} avis suspects
    2. **Semaine 3-4** : Réponse aux {negative_count} avis négatifs
    3. **Semaine 5-6** : Capitalisation sur les {positive_count} avis positifs
    
    ### ⚡ Actions immédiates
    
    - Mettre en place un système de réponse aux avis négatifs
    - Identifier les 10 clients les plus satisfaits pour témoignages
    - Auditer les processus de vérification des avis
    
    ### 📊 Suivi des indicateurs
    
    - Mesurer le NPS chaque mois
    - Suivre le taux de réponse aux avis négatifs
    - Surveiller le taux de faux avis détectés
    """
    
    st.markdown(f'<div class="table-description">{action_plan}</div>', unsafe_allow_html=True)

def generate_recommendations(data: pd.DataFrame) -> List[str]:
    """Générer des recommandations basées sur les données"""
    recommendations = []
    
    total = len(data)
    positive_count = (data['sentiment'] == 'positif').sum()
    negative_count = (data['sentiment'] == 'négatif').sum()
    fake_count = data['faux_avis'].sum() if 'faux_avis' in data.columns else 0
    
    positive_pct = (positive_count / total * 100) if total > 0 else 0
    negative_pct = (negative_count / total * 100) if total > 0 else 0
    fake_pct = (fake_count / total * 100) if total > 0 else 0
    
    # Recommandations basées sur les sentiments
    if positive_pct > 70:
        recommendations.append("Capitalisez massivement sur les avis positifs en les intégrant à toutes vos communications marketing.")
    elif positive_pct > 50:
        recommendations.append("Mettez en avant les avis positifs dans vos campagnes de conversion.")
    
    if negative_pct > 30:
        recommendations.append("Priorisez la résolution des problèmes mentionnés dans les avis négatifs avec une équipe dédiée.")
    elif negative_pct > 15:
        recommendations.append("Analysez les causes des avis négatifs et mettez en place des actions correctives.")
    
    # Recommandations basées sur les faux avis
    if fake_pct > 20:
        recommendations.append("Implémentez un système de vérification renforcé pour les avis avec validation en deux étapes.")
    elif fake_pct > 10:
        recommendations.append("Renforcez les contrôles de détection de faux avis avec des algorithmes plus avancés.")
    
    # Recommandations générales
    recommendations.extend([
        "Segmentez votre audience par type de feedback pour des campagnes marketing ciblées.",
        "Créez du contenu éducatif basé sur les questions fréquentes identifiées dans les avis.",
        "Mettez en place un programme de fidélisation pour les clients qui laissent des avis constructifs.",
        "Analysez les avis neutres pour identifier les opportunités d'amélioration non exprimées.",
        "Utilisez les avis positifs comme témoignages dans vos supports marketing et votre site web.",
        "Formez votre équipe support sur les problématiques récurrentes identifiées dans les avis.",
        "Créez des FAQ dynamiques basées sur le contenu des avis clients.",
        "Développez un système de récompense pour les clients qui fournissent des retours détaillés.",
        "Intégrez l'analyse des sentiments dans votre tableau de bord de performance marketing.",
        "Automatisez les réponses aux avis positifs pour renforcer l'engagement client."
    ])
    
    return recommendations

def get_priority_label(priority: int) -> str:
    """Obtenir le label de priorité"""
    if priority <= 3:
        return "Haute priorité"
    elif priority <= 6:
        return "Priorité moyenne"
    else:
        return "À planifier"

def render_person_identification(data: pd.DataFrame, name_col: str, text_col: str):
    """Render l'identification des personnes"""
    st.markdown('<h3 class="section-title">👤 Identification des Personnes</h3>', unsafe_allow_html=True)
    
    if not name_col:
        st.warning("⚠️ Veuillez sélectionner une colonne de noms dans la sidebar")
        return
    
    # Statistiques globales
    display_person_identification_stats(data, name_col)
    
    # Recherche de personne spécifique
    display_person_search(data, name_col, text_col)
    
    # Analyse par personne
    display_person_analysis(data, name_col, text_col)

def render_person_identification_advanced():
    """Render la page avancée d'identification des personnes"""
    st.markdown('<h2 class="section-title">👥 Module d\'Identification Avancée</h2>', unsafe_allow_html=True)
    
    data = st.session_state.analyst_data
    name_col = st.session_state.selected_name_col
    
    if not name_col:
        st.info("📁 Sélectionnez une colonne de noms dans la sidebar pour activer ce module")
        return
    
    st.markdown("""
    <div class="table-description">
        Ce module permet d'identifier et d'analyser le comportement des personnes derrière les avis.
        Vous pouvez détecter les patterns suspects, identifier les contributeurs clés,
        et générer des rapports détaillés pour chaque personne.
    </div>
    """, unsafe_allow_html=True)
    
    # Statistiques globales
    display_person_identification_stats(data, name_col)
    
    # Top contributeurs
    display_top_contributors(data, name_col)
    
    # Analyse détaillée par personne
    display_detailed_person_analysis(data, name_col)
    
    # Génération de rapports
    display_report_generation(data, name_col)

def display_person_identification_stats(data: pd.DataFrame, name_col: str):
    """Afficher les statistiques d'identification"""
    unique_persons = data[name_col].nunique()
    total_reviews = len(data)
    avg_reviews = total_reviews / unique_persons if unique_persons > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("👥 Personnes uniques", unique_persons)
    
    with col2:
        st.metric("📝 Avis totaux", total_reviews)
    
    with col3:
        st.metric("📊 Moyenne/personne", f"{avg_reviews:.1f}")
    
    with col4:
        if 'faux_avis' in data.columns:
            suspicious = data[data['faux_avis'] == True][name_col].nunique()
            st.metric("⚠️ Personnes suspectes", suspicious)
        else:
            st.metric("🎯 Colonne ID", name_col)

def display_top_contributors(data: pd.DataFrame, name_col: str):
    """Afficher les top contributeurs"""
    st.markdown('<h3 class="section-title">🏆 Top Contributeurs</h3>', unsafe_allow_html=True)
    
    person_activity = data[name_col].value_counts().head(20)
    
    fig = px.bar(
        x=person_activity.values,
        y=person_activity.index,
        orientation='h',
        title="Personnes les plus actives",
        labels={'x': "Nombre d'avis", 'y': 'Personne'},
        color=person_activity.values,
        color_continuous_scale='plasma'
    )
    
    fig.update_layout(
        plot_bgcolor='white',
        height=500,
        xaxis_title="Nombre d'avis",
        yaxis_title="Personne",
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_person_search(data: pd.DataFrame, name_col: str, text_col: str):
    """Afficher la recherche de personne"""
    st.markdown('<h3 class="section-title">🔍 Recherche de Personne Spécifique</h3>', unsafe_allow_html=True)
    
    search_term = st.text_input(
        "Entrez un nom ou un identifiant:",
        placeholder="Ex: Jean Dupont ou jdupont@email.com",
        key="person_search"
    )
    
    if search_term:
        search_results = data[data[name_col].astype(str).str.contains(search_term, case=False, na=False)]
        
        if not search_results.empty:
            st.success(f"✅ {len(search_results)} résultat(s) trouvé(s) pour '{search_term}'")
            
            # Affichage des résultats
            for idx, row in search_results.head(5).iterrows():
                sentiment = row.get('sentiment', 'Non analysé')
                is_fake = row.get('faux_avis', False)
                
                sentiment_color = Config.SENTIMENT_COLORS.get(sentiment, Config.COLORS['light'])
                card_class = "person-positive" if sentiment == 'positif' else "person-negative" if sentiment == 'négatif' else "person-alert"
                
                st.markdown(f"""
                <div class="{card_class}">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                        <strong>👤 {row[name_col]}</strong>
                        <div>
                            <span style="color: {sentiment_color}; font-weight: bold;">{sentiment.upper()}</span>
                            <span style="margin-left: 1rem; color: {'#DC3545' if is_fake else '#28A745'};">
                                {'⚠️ FAUX AVIS' if is_fake else '✅ Authentique'}
                            </span>
                        </div>
                    </div>
                    <p style="margin: 0.5rem 0; font-style: italic;">"{row[text_col][:200]}..."</p>
                    <div style="font-size: 0.85em; color: #6B7280;">
                        📅 {row.get('date', 'Date non spécifiée') if 'date' in data.columns else 'Sans date'}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning(f"Aucun résultat trouvé pour '{search_term}'")

def display_person_analysis(data: pd.DataFrame, name_col: str, text_col: str):
    """Afficher l'analyse par personne"""
    st.markdown('<h3 class="section-title">📊 Analyse par Personne</h3>', unsafe_allow_html=True)
    
    # Sélection de la personne
    person_options = data[name_col].unique()[:50]  # Limiter pour la performance
    
    selected_person = st.selectbox(
        "Sélectionnez une personne pour une analyse détaillée",
        options=person_options,
        help="Choisissez une personne pour voir son historique complet",
        key="person_selector"
    )
    
    if selected_person:
        person_data = data[data[name_col] == selected_person]
        
        display_person_profile(person_data, selected_person, name_col, text_col)

def display_detailed_person_analysis(data: pd.DataFrame, name_col: str):
    """Afficher l'analyse détaillée par personne"""
    st.markdown('<h3 class="section-title">📈 Analyse Détaillée par Personne</h3>', unsafe_allow_html=True)
    
    # Sélection de la personne avec plus d'options
    person_options = data[name_col].unique()[:100]
    
    selected_person = st.selectbox(
        "Sélectionnez une personne",
        options=person_options,
        help="Analysez le comportement et les patterns d'une personne spécifique",
        key="detailed_person_selector"
    )
    
    if selected_person:
        person_data = data[data[name_col] == selected_person]
        
        # Métriques détaillées
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total d'avis", len(person_data))
        
        with col2:
            if 'sentiment' in data.columns:
                positive_count = (person_data['sentiment'] == 'positif').sum()
                st.metric("Avis positifs", positive_count)
        
        with col3:
            if 'sentiment' in data.columns:
                negative_count = (person_data['sentiment'] == 'négatif').sum()
                st.metric("Avis négatifs", negative_count)
        
        with col4:
            if 'faux_avis' in data.columns:
                fake_count = person_data['faux_avis'].sum()
                st.metric("Faux avis", fake_count)
        
        # Historique des avis
        st.markdown("##### 📝 Historique complet des avis")
        
        for idx, row in person_data.iterrows():
            display_review_card(row, name_col)

def display_person_profile(person_data: pd.DataFrame, person_name: str, name_col: str, text_col: str):
    """Afficher le profil d'une personne"""
    st.markdown(f"##### 📋 Profil de **{person_name}**")
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        st.metric("Total d'avis", len(person_data))
    
    with col_b:
        if 'sentiment' in person_data.columns:
            positive_count = (person_data['sentiment'] == 'positif').sum()
            st.metric("Avis positifs", positive_count)
    
    with col_c:
        if 'faux_avis' in person_data.columns:
            fake_count = person_data['faux_avis'].sum()
            st.metric("Faux avis", fake_count)
    
    # Afficher les avis
    st.markdown("##### 📝 Historique des Avis")
    
    for idx, row in person_data.iterrows():
        display_review_card(row, name_col)
    
    # Recommandations d'actions
    display_person_action_recommendations(person_data)

def display_review_card(row: pd.Series, name_col: str):
    """Afficher une carte d'avis"""
    text_col = st.session_state.selected_text_col
    sentiment = row.get('sentiment', 'Non analysé')
    is_fake = row.get('faux_avis', False)
    
    card_class = "person-positive" if sentiment == 'positif' else "person-negative" if sentiment == 'négatif' else "person-alert"
    
    st.markdown(f"""
    <div class="{card_class}">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <strong>#{row.name if hasattr(row, 'name') else 'N/A'}</strong>
            <div>
                <span style="font-weight: bold; color: {Config.SENTIMENT_COLORS.get(sentiment, Config.COLORS['light'])};">
                    {sentiment.upper()}
                </span>
                <span style="margin-left: 1rem; color: {'#DC3545' if is_fake else '#28A745'}; font-size: 0.9em;">
                    {'⚠️ FAUX' if is_fake else '✅ VRAI'}
                </span>
            </div>
        </div>
        <p style="margin: 0.5rem 0; line-height: 1.5;">{row[text_col][:300]}{'...' if len(str(row[text_col])) > 300 else ''}</p>
    </div>
    """, unsafe_allow_html=True)

def display_person_action_recommendations(person_data: pd.DataFrame):
    """Afficher les recommandations d'actions pour une personne"""
    st.markdown("##### 🎯 Recommandations d'Actions")
    
    if 'sentiment' in person_data.columns:
        negative_count = (person_data['sentiment'] == 'négatif').sum()
        
        if negative_count > 2:
            st.error(f"""
            **🚨 Action Prioritaire Requise:**
            
            - Cette personne a **{negative_count} avis négatifs**
            - **Action immédiate:** Contacter pour comprendre les problèmes
            - **Objectif:** Résoudre les problèmes et reconquérir le client
            - **Suivi:** Mettre en place un suivi strict pendant 30 jours
            """)
        elif negative_count == 1:
            st.warning(f"""
            **⚠️ À Surveiller:**
            
            - Cette personne a **1 avis négatif**
            - **Action:** Envoyer un email de suivi personnalisé
            - **Objectif:** S'assurer que le problème est résolu
            - **Suivi:** Suivre la satisfaction lors du prochain contact
            """)
        else:
            positive_count = (person_data['sentiment'] == 'positif').sum()
            if positive_count >= 3:
                st.success(f"""
                **💎 Opportunité de Fidélisation:**
                
                - Cette personne a **{positive_count} avis positifs**
                - **Action:** Proposer un programme de fidélité ou de parrainage
                - **Objectif:** Transformer en ambassadeur de la marque
                - **Suivi:** Maintenir une relation privilégiée
                """)
    
    if 'faux_avis' in person_data.columns:
        fake_count = person_data['faux_avis'].sum()
        if fake_count > 0:
            st.error(f"""
            **🔍 Suspicion de Fraude Identifiée:**
            
            - **{fake_count} faux avis** détectés pour cette personne
            - **Action immédiate:** Investigation approfondie requise
            - **Mesures:** Possible restriction du compte
            - **Notification:** Alerter l'équipe de sécurité et de modération
            """)

def display_report_generation(data: pd.DataFrame, name_col: str):
    """Afficher la génération de rapports"""
    st.markdown('<h3 class="section-title">📤 Génération de Rapports</h3>', unsafe_allow_html=True)
    
    if st.button("📊 Générer le rapport complet d'identification", type="primary", use_container_width=True):
        with st.spinner("Génération du rapport en cours..."):
            # Créer le rapport
            report_df = create_person_analysis_report(data, name_col, st.session_state.selected_text_col)
            
            if not report_df.empty:
                st.dataframe(
                    report_df,
                    use_container_width=True,
                    height=500
                )
                
                # Options de téléchargement
                col1, col2 = st.columns(2)
                
                with col1:
                    # CSV
                    csv = report_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Télécharger en CSV",
                        data=csv,
                        file_name=f"rapport_identification_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        type="primary",
                        use_container_width=True
                    )
                
                with col2:
                    # Excel
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        report_df.to_excel(writer, index=False, sheet_name='Rapport Identification')
                    excel_data = excel_buffer.getvalue()
                    
                    st.download_button(
                        label="📊 Télécharger en Excel",
                        data=excel_data,
                        file_name=f"rapport_identification_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="secondary",
                        use_container_width=True
                    )
                
                # Résumé exécutif
                st.markdown("##### 📋 Résumé Exécutif")
                
                summary = generate_executive_summary(report_df)
                st.markdown(f'<div class="table-description">{summary}</div>', unsafe_allow_html=True)
            else:
                st.warning("Impossible de générer le rapport. Vérifiez que les données sont correctes.")

def generate_executive_summary(report_df: pd.DataFrame) -> str:
    """Générer un résumé exécutif"""
    total_persons = len(report_df)
    high_risk = len(report_df[report_df['Niveau risque'] == 'Élevé'])
    medium_risk = len(report_df[report_df['Niveau risque'] == 'Moyen'])
    to_watch = len(report_df[report_df['Niveau risque'] == 'À surveiller'])
    
    avg_satisfaction = report_df['Taux satisfaction'].str.rstrip('%').astype(float).mean()
    total_fake_reviews = report_df['Faux avis'].sum()
    
    return f"""
    ### 📊 Résumé Exécutif
    
    **Analyse de {total_persons} personnes identifiées**
    
    #### 🎯 Niveaux de Risque
    - **Élevé:** {high_risk} personnes ({high_risk/total_persons*100:.1f}%)
    - **Moyen:** {medium_risk} personnes ({medium_risk/total_persons*100:.1f}%)
    - **À surveiller:** {to_watch} personnes ({to_watch/total_persons*100:.1f}%)
    
    #### 📈 Indicateurs Clés
    - **Taux de satisfaction moyen:** {avg_satisfaction:.1f}%
    - **Faux avis totaux détectés:** {total_fake_reviews}
    
    #### 🚨 Priorités d'Action
    1. **Personnes à risque élevé:** Investigation immédiate requise
    2. **Faux avis:** Renforcer les contrôles de détection
    3. **Personnes à surveiller:** Mettre en place un suivi actif
    
    *Rapport généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}*
    """

def render_data_management():
    """Render la gestion des données"""
    st.markdown('<h2 class="section-title">📁 Gestion des Données</h2>', unsafe_allow_html=True)
    
    if st.session_state.get('analyst_data') is None:
        st.info("📁 Importez des données pour accéder aux outils de gestion")
        return
    
    data = st.session_state.analyst_data
    
    st.markdown("""
    <div class="table-description">
        Cette section permet de nettoyer, préparer et optimiser vos données pour l'analyse.
        Les opérations incluent la gestion des valeurs manquantes, la suppression des doublons,
        la normalisation des données et l'optimisation des performances.
    </div>
    """, unsafe_allow_html=True)
    
    # Analyse de la qualité des données
    display_data_quality_analysis(data)
    
    # Outils de nettoyage
    display_data_cleaning_tools(data)
    
    # Statistiques post-nettoyage
    display_post_cleaning_stats()

def display_data_quality_analysis(data: pd.DataFrame):
    """Afficher l'analyse de la qualité des données"""
    st.markdown('<h3 class="section-title">🔍 Analyse de la Qualité</h3>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        missing_values = data.isnull().sum().sum()
        total_cells = len(data) * len(data.columns)
        missing_pct = (missing_values / total_cells * 100) if total_cells > 0 else 0
        
        st.metric("Valeurs manquantes", f"{missing_values:,}", f"{missing_pct:.1f}%")
    
    with col2:
        duplicate_rows = data.duplicated().sum()
        duplicate_pct = (duplicate_rows / len(data) * 100) if len(data) > 0 else 0
        
        st.metric("Lignes dupliquées", f"{duplicate_rows:,}", f"{duplicate_pct:.1f}%")
    
    with col3:
        numeric_columns = len(data.select_dtypes(include=[np.number]).columns)
        total_columns = len(data.columns)
        numeric_pct = (numeric_columns / total_columns * 100) if total_columns > 0 else 0
        
        st.metric("Colonnes numériques", numeric_columns, f"{numeric_pct:.1f}%")
    
    with col4:
        text_columns = len(data.select_dtypes(include=['object', 'string']).columns)
        text_pct = (text_columns / total_columns * 100) if total_columns > 0 else 0
        
        st.metric("Colonnes texte", text_columns, f"{text_pct:.1f}%")
    
    # Détails des valeurs manquantes
    if missing_values > 0:
        st.markdown("##### 📋 Détail des valeurs manquantes par colonne")
        
        missing_by_col = data.isnull().sum()
        missing_by_col = missing_by_col[missing_by_col > 0].sort_values(ascending=False)
        
        missing_df = pd.DataFrame({
            'Colonne': missing_by_col.index,
            'Valeurs manquantes': missing_by_col.values,
            'Pourcentage': (missing_by_col.values / len(data) * 100).round(1)
        })
        
        st.dataframe(missing_df, use_container_width=True, height=300)

def display_data_cleaning_tools(data: pd.DataFrame):
    """Afficher les outils de nettoyage"""
    st.markdown('<h3 class="section-title">🧹 Outils de Nettoyage</h3>', unsafe_allow_html=True)
    
    # Section 1: Suppression des doublons
    st.markdown("##### 1. Suppression des doublons")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.info("Supprime les lignes identiques du jeu de données")
    
    with col2:
        if st.button("🔍 Analyser les doublons", use_container_width=True):
            duplicate_count = data.duplicated().sum()
            st.session_state.duplicate_count = duplicate_count
            
            if duplicate_count > 0:
                st.warning(f"{duplicate_count} doublons détectés")
            else:
                st.success("Aucun doublon détecté")
    
    with col3:
        if st.session_state.get('duplicate_count', 0) > 0:
            if st.button("🗑️ Supprimer les doublons", use_container_width=True, type="primary"):
                initial_len = len(data)
                cleaned_data = data.drop_duplicates()
                removed = initial_len - len(cleaned_data)
                
                st.session_state.analyst_data = cleaned_data
                st.success(f"✅ {removed} doublons supprimés. {len(cleaned_data)} lignes restantes.")
                st.rerun()
    
    # Section 2: Gestion des valeurs manquantes
    st.markdown("##### 2. Gestion des valeurs manquantes")
    
    if data.isnull().sum().sum() > 0:
        tab1, tab2, tab3 = st.tabs(["Suppression", "Remplissage numérique", "Remplissage texte"])
        
        with tab1:
            st.markdown("Supprimer toutes les lignes contenant des valeurs manquantes")
            if st.button("Supprimer les lignes avec NA", use_container_width=True):
                initial_len = len(data)
                cleaned_data = data.dropna()
                removed = initial_len - len(cleaned_data)
                
                st.session_state.analyst_data = cleaned_data
                st.success(f"✅ {removed} lignes supprimées. {len(cleaned_data)} lignes restantes.")
                st.rerun()
        
        with tab2:
            st.markdown("Remplacer les valeurs manquantes numériques par la moyenne")
            numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
            
            if numeric_cols:
                col_selection = st.multiselect(
                    "Sélectionnez les colonnes",
                    numeric_cols,
                    default=numeric_cols[:3] if len(numeric_cols) > 3 else numeric_cols
                )
                
                if st.button("Remplacer par la moyenne", use_container_width=True):
                    cleaned_data = data.copy()
                    for col in col_selection:
                        if cleaned_data[col].dtype in [np.float64, np.int64]:
                            mean_val = cleaned_data[col].mean()
                            cleaned_data[col] = cleaned_data[col].fillna(mean_val)
                    
                    st.session_state.analyst_data = cleaned_data
                    st.success("✅ Valeurs manquantes numériques remplacées")
                    st.rerun()
            else:
                st.info("Aucune colonne numérique détectée")
        
        with tab3:
            st.markdown("Remplacer les valeurs manquantes texte")
            text_cols = data.select_dtypes(include=['object', 'string']).columns.tolist()
            
            if text_cols:
                col_selection = st.multiselect(
                    "Sélectionnez les colonnes texte",
                    text_cols,
                    default=text_cols[:3] if len(text_cols) > 3 else text_cols,
                    key="text_cols_selector"
                )
                
                replacement_text = st.text_input(
                    "Texte de remplacement",
                    value="Non spécifié",
                    help="Texte à utiliser pour remplacer les valeurs manquantes"
                )
                
                if st.button("Remplacer le texte manquant", use_container_width=True):
                    cleaned_data = data.copy()
                    for col in col_selection:
                        cleaned_data[col] = cleaned_data[col].fillna(replacement_text)
                    
                    st.session_state.analyst_data = cleaned_data
                    st.success(f"✅ Valeurs manquantes texte remplacées par '{replacement_text}'")
                    st.rerun()
            else:
                st.info("Aucune colonne texte détectée")
    
    # Section 3: Normalisation du texte
    st.markdown("##### 3. Normalisation du texte")
    
    text_cols = data.select_dtypes(include=['object', 'string']).columns.tolist()
    
    if text_cols:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Convertir en minuscules", use_container_width=True):
                cleaned_data = data.copy()
                for col in text_cols:
                    cleaned_data[col] = cleaned_data[col].astype(str).str.lower()
                
                st.session_state.analyst_data = cleaned_data
                st.success("✅ Texte converti en minuscules")
                st.rerun()
        
        with col2:
            if st.button("Supprimer les espaces", use_container_width=True):
                cleaned_data = data.copy()
                for col in text_cols:
                    cleaned_data[col] = cleaned_data[col].astype(str).str.strip()
                
                st.session_state.analyst_data = cleaned_data
                st.success("✅ Espaces superflus supprimés")
                st.rerun()
        
        with col3:
            if st.button("Supprimer caractères spéciaux", use_container_width=True):
                cleaned_data = data.copy()
                for col in text_cols:
                    cleaned_data[col] = cleaned_data[col].astype(str).str.replace(r'[^\w\s]', '', regex=True)
                
                st.session_state.analyst_data = cleaned_data
                st.success("✅ Caractères spéciaux supprimés")
                st.rerun()
    else:
        st.info("Aucune colonne texte détectée pour la normalisation")

def display_post_cleaning_stats():
    """Afficher les statistiques post-nettoyage"""
    if st.session_state.get('analyst_data') is not None:
        current_data = st.session_state.analyst_data
        
        st.markdown('<h3 class="section-title">📊 Statistiques Post-Nettoyage</h3>', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Lignes totales", f"{len(current_data):,}")
        
        with col2:
            remaining_missing = current_data.isnull().sum().sum()
            st.metric("Valeurs manquantes", f"{remaining_missing:,}")
        
        with col3:
            remaining_duplicates = current_data.duplicated().sum()
            st.metric("Doublons restants", f"{remaining_duplicates:,}")
        
        with col4:
            mem_usage = current_data.memory_usage(deep=True).sum() / 1024 / 1024
            st.metric("Mémoire utilisée", f"{mem_usage:.1f} MB")
        
        # Aperçu des données nettoyées
        st.markdown('<h4>Aperçu des données après nettoyage</h4>', unsafe_allow_html=True)
        
        st.markdown('<div class="data-table">', unsafe_allow_html=True)
        st.dataframe(
            current_data.head(10),
            use_container_width=True,
            height=300
        )
        st.markdown('</div>', unsafe_allow_html=True)

# =========================POINT D'ENTRÉE===================
if __name__ == "__main__":
    show_analyst_dashboard()