# ============= dashboard_manager_marketing.py ====================

from dataclasses import dataclass
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
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
class MarketingConfig:
    """Configuration spécifique au dashboard Marketing"""
    COLORS = {
        'primary': '#36B37E',
        'secondary': '#6554C0',
        'warning': '#FFAB00',
        'danger': '#FF5630',
        'info': '#00B8D9',
        'success': '#36B37E',
        'dark': '#172B4D',
        'light': '#6B7280'
    }
    
    SENTIMENT_COLORS = {
        'positif': '#36B37E',
        'négatif': '#FF5630',
        'neutre': '#FFAB00'
    }
    
    CHART_THEME = {
        'background': 'white',
        'grid_color': '#f0f0f0',
        'font_family': 'Arial, sans-serif'
    }
    
    # Seuils pour les recommandations
    HIGH_SATISFACTION_THRESHOLD = 70  # %
    HIGH_RISK_THRESHOLD = 30  # %
    FAKE_REVIEW_THRESHOLD = 20  # %

# =========================CLASSES UTILITAIRES===================
@dataclass
class MarketingInsight:
    """Insight marketing généré"""
    category: str
    title: str
    description: str
    priority: int
    metrics: Dict[str, Any]
    recommendations: List[str]
    
    @property
    def priority_color(self) -> str:
        if self.priority == 1:
            return MarketingConfig.COLORS['danger']
        elif self.priority == 2:
            return MarketingConfig.COLORS['warning']
        else:
            return MarketingConfig.COLORS['info']

@dataclass
class ClientProfile:
    """Profil d'un client"""
    name: str
    total_reviews: int
    positive_count: int
    negative_count: int
    neutral_count: int
    fake_reviews: int
    first_interaction: Optional[str] = None
    last_interaction: Optional[str] = None
    segment: str = "Standard"
    
    @property
    def satisfaction_score(self) -> float:
        if self.total_reviews == 0:
            return 0.0
        return (self.positive_count / self.total_reviews) * 100
    
    @property
    def client_value(self) -> str:
        if self.satisfaction_score > 80 and self.total_reviews >= 3:
            return "Ambassadeur"
        elif self.satisfaction_score > 60:
            return "Fidèle"
        elif self.negative_count >= 2:
            return "À risque"
        else:
            return "Standard"

# =========================UTILITAIRES===================
def setup_marketing_logging():
    """Configuration du logging pour le marketing"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - MARKETING - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('marketing_dashboard.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_marketing_logging()

def validate_marketing_data(data: pd.DataFrame) -> Tuple[bool, str]:
    """Valider les données marketing"""
    if data is None or data.empty:
        return False, "Données vides ou non chargées"
    
    required_columns = []
    if len(required_columns) > 0:
        missing = [col for col in required_columns if col not in data.columns]
        if missing:
            return False, f"Colonnes manquantes: {', '.join(missing)}"
    
    return True, "Données valides"

def detect_marketing_columns(data: pd.DataFrame) -> Dict[str, List[str]]:
    """Détecter les colonnes importantes pour le marketing"""
    result = {
        'text_columns': data.select_dtypes(include=['object', 'string']).columns.tolist(),
        'date_columns': [],
        'client_columns': [],
        'performance_columns': data.select_dtypes(include=[np.number]).columns.tolist(),
        'campaign_columns': []
    }
    
    # Détection des colonnes de date
    date_keywords = ['date', 'time', 'jour', 'timestamp', 'datetime', 'periode']
    for col in data.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in date_keywords):
            result['date_columns'].append(col)
    
    # Détection des colonnes clients
    client_keywords = ['client', 'customer', 'nom', 'name', 'utilisateur', 'user', 
                      'email', 'contact', 'acheteur', 'buyer', 'prospect']
    for col in data.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in client_keywords):
            result['client_columns'].append(col)
    
    # Détection des colonnes campagne
    campaign_keywords = ['campaign', 'campagne', 'channel', 'canal', 'source', 
                        'medium', 'referral', 'acquisition']
    for col in data.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in campaign_keywords):
            result['campaign_columns'].append(col)
    
    return result

# =========================FONCTIONS D'ANALYSE MARKETING===================
def calculate_marketing_kpis(data: pd.DataFrame) -> Dict[str, Any]:
    """Calculer les KPI marketing"""
    kpis = {}
    
    # KPI de base
    kpis['total_reviews'] = len(data)
    
    if 'sentiment' in data.columns:
        kpis['positive_reviews'] = (data['sentiment'] == 'positif').sum()
        kpis['negative_reviews'] = (data['sentiment'] == 'négatif').sum()
        kpis['neutral_reviews'] = (data['sentiment'] == 'neutre').sum()
        
        kpis['satisfaction_rate'] = (kpis['positive_reviews'] / kpis['total_reviews'] * 100) if kpis['total_reviews'] > 0 else 0
        kpis['nps_score'] = ((kpis['positive_reviews'] - kpis['negative_reviews']) / kpis['total_reviews'] * 100) if kpis['total_reviews'] > 0 else 0
    
    if 'faux_avis' in data.columns:
        kpis['fake_reviews'] = data['faux_avis'].sum()
        kpis['fake_rate'] = (kpis['fake_reviews'] / kpis['total_reviews'] * 100) if kpis['total_reviews'] > 0 else 0
    
    return kpis

def create_performance_trend_chart(data: pd.DataFrame, date_col: str, metric_col: str) -> Tuple[Optional[go.Figure], str]:
    """Créer un graphique de tendance des performances"""
    if date_col not in data.columns or metric_col not in data.columns:
        return None, "Colonnes manquantes"
    
    try:
        # Préparation des données
        chart_data = data.copy()
        
        # Convertir la date
        chart_data[date_col] = pd.to_datetime(chart_data[date_col], errors='coerce')
        chart_data = chart_data.dropna(subset=[date_col, metric_col])
        
        # Trier par date
        chart_data = chart_data.sort_values(date_col)
        
        # Créer le graphique
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=chart_data[date_col],
            y=chart_data[metric_col],
            mode='lines+markers',
            name=metric_col,
            line=dict(color=MarketingConfig.COLORS['primary'], width=3),
            marker=dict(size=8),
            hovertemplate='<b>%{x}</b><br>%{y:,.0f}<extra></extra>'
        ))
        
        # Ajouter une ligne de tendance
        if len(chart_data) > 1:
            z = np.polyfit(range(len(chart_data)), chart_data[metric_col], 1)
            p = np.poly1d(z)
            fig.add_trace(go.Scatter(
                x=chart_data[date_col],
                y=p(range(len(chart_data))),
                mode='lines',
                name='Tendance',
                line=dict(color=MarketingConfig.COLORS['warning'], width=2, dash='dash'),
                hoverinfo='skip'
            ))
        
        fig.update_layout(
            title=f"Évolution de {metric_col}",
            xaxis_title="Date",
            yaxis_title=metric_col,
            plot_bgcolor=MarketingConfig.CHART_THEME['background'],
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
            height=500
        )
        
        fig.update_xaxes(gridcolor=MarketingConfig.CHART_THEME['grid_color'])
        fig.update_yaxes(gridcolor=MarketingConfig.CHART_THEME['grid_color'])
        
        # Calculer les statistiques
        if len(chart_data) > 0:
            first_value = chart_data[metric_col].iloc[0]
            last_value = chart_data[metric_col].iloc[-1]
            change = ((last_value - first_value) / first_value * 100) if first_value != 0 else 0
            
            interpretation = f"Évolution: {change:+.1f}% sur la période"
        else:
            interpretation = "Données insuffisantes pour l'analyse"
        
        return fig, interpretation
        
    except Exception as e:
        logger.error(f"Erreur dans le graphique de tendance: {str(e)}")
        return None, f"Erreur: {str(e)}"

def create_sentiment_distribution_chart(data: pd.DataFrame) -> Tuple[Optional[go.Figure], str]:
    """Créer un graphique de distribution des sentiments"""
    if 'sentiment' not in data.columns:
        return None, "Données de sentiment non disponibles"
    
    sentiment_counts = data['sentiment'].value_counts()
    
    # Créer le graphique
    fig = go.Figure(data=[
        go.Bar(
            x=sentiment_counts.index,
            y=sentiment_counts.values,
            marker_color=[MarketingConfig.SENTIMENT_COLORS.get(s, MarketingConfig.COLORS['light']) 
                         for s in sentiment_counts.index],
            text=sentiment_counts.values,
            textposition='outside',
            textfont=dict(size=14, weight='bold'),
            hovertemplate='<b>%{x}</b><br>%{y} avis<br>%{customdata}%<extra></extra>',
            customdata=[(count / len(data) * 100) for count in sentiment_counts.values]
        )
    ])
    
    fig.update_layout(
        title="Distribution des sentiments clients",
        xaxis_title="Sentiment",
        yaxis_title="Nombre d'avis",
        plot_bgcolor=MarketingConfig.CHART_THEME['background'],
        showlegend=False,
        height=500,
        margin=dict(l=50, r=50, t=80, b=50)
    )
    
    fig.update_xaxes(gridcolor=MarketingConfig.CHART_THEME['grid_color'])
    fig.update_yaxes(gridcolor=MarketingConfig.CHART_THEME['grid_color'])
    
    # Interprétation
    total = len(data)
    positive_pct = (sentiment_counts.get('positif', 0) / total * 100) if total > 0 else 0
    negative_pct = (sentiment_counts.get('négatif', 0) / total * 100) if total > 0 else 0
    
    if positive_pct > MarketingConfig.HIGH_SATISFACTION_THRESHOLD:
        interpretation = "Excellente satisfaction client - Opportunité de capitalisation"
    elif negative_pct > MarketingConfig.HIGH_RISK_THRESHOLD:
        interpretation = "Attention requise - Taux d'insatisfaction élevé"
    elif positive_pct > negative_pct:
        interpretation = "Satisfaction globalement positive avec marge d'amélioration"
    else:
        interpretation = "Performance mitigée - Nécessite une analyse approfondie"
    
    return fig, interpretation

def create_client_activity_chart(data: pd.DataFrame, client_col: str) -> Optional[go.Figure]:
    """Créer un graphique d'activité des clients"""
    if client_col not in data.columns:
        return None
    
    # Compter l'activité par client
    client_activity = data[client_col].value_counts().head(15)
    
    # Créer le graphique
    fig = go.Figure(data=[
        go.Bar(
            x=client_activity.values,
            y=client_activity.index,
            orientation='h',
            marker_color=MarketingConfig.COLORS['primary'],
            hovertemplate='<b>%{y}</b><br>%{x} avis<extra></extra>',
            text=client_activity.values,
            textposition='outside'
        )
    ])
    
    fig.update_layout(
        title="Top 15 des clients les plus actifs",
        xaxis_title="Nombre d'avis",
        yaxis_title="Client",
        plot_bgcolor=MarketingConfig.CHART_THEME['background'],
        height=600,
        margin=dict(l=150, r=50, t=80, b=50)
    )
    
    fig.update_xaxes(gridcolor=MarketingConfig.CHART_THEME['grid_color'])
    
    return fig

def generate_marketing_insights(data: pd.DataFrame, text_col: str, client_col: Optional[str] = None) -> List[MarketingInsight]:
    """Générer des insights marketing"""
    insights = []
    
    # Calculer les KPI
    kpis = calculate_marketing_kpis(data)
    
    # Insight 1: Satisfaction client
    if 'satisfaction_rate' in kpis:
        satisfaction_insight = MarketingInsight(
            category="Satisfaction Client",
            title="Analyse de la satisfaction client",
            description=f"Taux de satisfaction global: {kpis['satisfaction_rate']:.1f}%",
            priority=1 if kpis['satisfaction_rate'] < 60 else 2,
            metrics=kpis,
            recommendations=[
                "Capitaliser sur les avis positifs comme témoignages",
                "Mettre en place un programme de fidélisation",
                "Analyser les causes des avis négatifs"
            ]
        )
        insights.append(satisfaction_insight)
    
    # Insight 2: Authenticité des avis
    if 'fake_rate' in kpis:
        fake_insight = MarketingInsight(
            category="Authenticité",
            title="Analyse de l'authenticité des avis",
            description=f"Taux de faux avis détectés: {kpis['fake_rate']:.1f}%",
            priority=1 if kpis['fake_rate'] > MarketingConfig.FAKE_REVIEW_THRESHOLD else 3,
            metrics={'fake_rate': kpis['fake_rate']},
            recommendations=[
                "Renforcer les contrôles de validation des avis",
                "Implémenter un système de vérification",
                "Auditer les processus de modération"
            ]
        )
        insights.append(fake_insight)
    
    # Insight 3: Segmentation clients
    if client_col and client_col in data.columns:
        unique_clients = data[client_col].nunique()
        avg_reviews = kpis['total_reviews'] / unique_clients if unique_clients > 0 else 0
        
        segmentation_insight = MarketingInsight(
            category="Segmentation",
            title="Opportunités de segmentation",
            description=f"{unique_clients} clients uniques - Moyenne: {avg_reviews:.1f} avis/client",
            priority=2,
            metrics={'unique_clients': unique_clients, 'avg_reviews': avg_reviews},
            recommendations=[
                "Segmenter les clients par niveau d'activité",
                "Créer des campagnes personnalisées par segment",
                "Développer des programmes spécifiques pour les clients actifs"
            ]
        )
        insights.append(segmentation_insight)
    
    # Insight 4: Net Promoter Score
    if 'nps_score' in kpis:
        nps_category = "Promoteur" if kpis['nps_score'] > 50 else "Passif" if kpis['nps_score'] > 0 else "Détracteur"
        
        nps_insight = MarketingInsight(
            category="Loyalité",
            title=f"Score NPS: {kpis['nps_score']:.0f} ({nps_category})",
            description="Net Promoter Score mesurant la volonté de recommandation",
            priority=1 if kpis['nps_score'] < 0 else 2,
            metrics={'nps_score': kpis['nps_score'], 'nps_category': nps_category},
            recommendations=[
                "Améliorer l'expérience client pour convertir les détracteurs",
                "Renforcer l'engagement des promoteurs",
                "Mettre en place un programme de parrainage"
            ]
        )
        insights.append(nps_insight)
    
    return insights

# =========================COMPOSANTS UI===================
def page_bg_css() -> str:
    """CSS pour l'interface Marketing"""
    return """
    <style>
    .stApp {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        min-height: 100vh;
    }
    
    .main-header {
        background: linear-gradient(135deg, #36B37E 0%, #00875A 100%);
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
        border-left: 5px solid #36B37E;
        margin-top: 1.5rem;
        font-size: 0.95em;
        color: #495057;
        line-height: 1.6;
        font-style: italic;
        border: 1px solid rgba(0,0,0,0.05);
    }
    
    .insight-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 3px 15px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border: 1px solid #e5e7eb;
        transition: all 0.3s ease;
    }
    
    .insight-card:hover {
        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    .strategy-card {
        background: linear-gradient(135deg, white 0%, #f8f9fa 100%);
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 3px 15px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border: 1px solid rgba(0,0,0,0.05);
    }
    
    .client-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border-left: 5px solid;
        transition: all 0.3s ease;
    }
    
    .client-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    
    .client-card-positive {
        border-left-color: #36B37E;
    }
    
    .client-card-negative {
        border-left-color: #FF5630;
    }
    
    .client-card-neutral {
        border-left-color: #FFAB00;
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
        border-bottom: 3px solid #36B37E;
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
        background: linear-gradient(90deg, #36B37E, #6554C0);
    }
    
    .info-description {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        border-left: 5px solid #6554C0;
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
    
    .marketing-badge {
        background: linear-gradient(135deg, #36B37E 0%, #00875A 100%);
        color: white;
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
        background: linear-gradient(135deg, #36B37E 0%, #00875A 100%);
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
    
    .priority-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-size: 0.75em;
        font-weight: 600;
        margin-left: 0.5rem;
    }
    
    .priority-1 {
        background: rgba(255, 86, 48, 0.1);
        color: #FF5630;
        border: 1px solid rgba(255, 86, 48, 0.3);
    }
    
    .priority-2 {
        background: rgba(255, 171, 0, 0.1);
        color: #FFAB00;
        border: 1px solid rgba(255, 171, 0, 0.3);
    }
    
    .priority-3 {
        background: rgba(0, 184, 217, 0.1);
        color: #00B8D9;
        border: 1px solid rgba(0, 184, 217, 0.3);
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

def render_marketing_sidebar() -> str:
    """Render la sidebar marketing"""
    if 'user_info' not in st.session_state:
        st.session_state.user_info = {
            'full_name': 'Manager Marketing',
            'email': 'marketing@entreprise.com',
            'role': 'marketing'
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
                          background: linear-gradient(135deg, #36B37E 0%, #00875A 100%); 
                          border-radius: 50%; 
                          display: flex; 
                          align-items: center; 
                          justify-content: center; 
                          color: white; 
                          font-weight: bold;
                          font-size: 1.2em;
                          box-shadow: 0 3px 10px rgba(54, 179, 126, 0.3);">
                    {user_info['full_name'][0].upper() if user_info.get('full_name') else 'M'}
                </div>
                <div>
                    <h4 style="margin: 0; color: #172B4D; font-weight: 600;">
                        {user_info.get('full_name', 'Manager Marketing')}
                    </h4>
                    <div class="role-badge marketing-badge">Marketing Manager</div>
                </div>
            </div>
            <p style="margin: 0; font-size: 0.9em; color: #6B7280; line-height: 1.4;">
                {user_info.get('email', 'marketing@entreprise.com')}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation
        st.markdown("### 📈 Navigation")
        menu_options = {
            "📊 Performance": "performance",
            "🔍 Insights AIM": "insights",
            "🎯 Stratégies": "strategies",
            "👥 Clients": "clients"
        }
        
        selected_menu = st.radio(
            "Sélectionnez une section",
            list(menu_options.keys()),
            label_visibility="collapsed",
            key="marketing_nav_menu"
        )
        
        st.markdown("---")
        
        # Import de données marketing
        st.markdown("### 📤 Données marketing")
        
        uploaded_file = st.file_uploader(
            "Téléverser des données",
            type=['csv', 'xlsx', 'json'],
            key="marketing_data_uploader",
            help="Formats supportés: CSV, Excel, JSON (données clients, campagnes, avis)"
        )
        
        if uploaded_file:
            try:
                with st.spinner("Chargement des données marketing..."):
                    if uploaded_file.name.endswith('.csv'):
                        data = pd.read_csv(uploaded_file)
                    elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                        data = pd.read_excel(uploaded_file)
                    elif uploaded_file.name.endswith('.json'):
                        data = pd.read_json(uploaded_file)
                    
                    st.session_state.marketing_data = data
                    
                    # Détection automatique des colonnes
                    column_types = detect_marketing_columns(data)
                    
                    if 'selected_text_col' not in st.session_state:
                        st.session_state.selected_text_col = (
                            column_types['text_columns'][0] 
                            if column_types['text_columns'] else None
                        )
                    
                    if 'selected_client_col' not in st.session_state:
                        st.session_state.selected_client_col = (
                            column_types['client_columns'][0] 
                            if column_types['client_columns'] else None
                        )
                    
                    st.markdown(f"""
                    <div class="upload-success">
                        <strong>✅ Données marketing importées !</strong><br>
                        <small>{len(data)} enregistrements, {len(data.columns)} colonnes</small>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    logger.info(f"Données marketing importées: {uploaded_file.name}")
                    
            except Exception as e:
                st.markdown(f"""
                <div class="upload-error">
                    <strong>❌ Erreur lors de l'import</strong><br>
                    <small>{str(e)}</small>
                </div>
                """, unsafe_allow_html=True)
                logger.error(f"Erreur import marketing: {str(e)}")
        
        # Options de colonnes
        if st.session_state.get('marketing_data') is not None:
            st.markdown("---")
            st.markdown("### ⚙️ Configuration")
            
            data = st.session_state.marketing_data
            
            # Sélection de la colonne texte
            text_cols = data.select_dtypes(include=['object', 'string']).columns.tolist()
            if text_cols:
                st.session_state.selected_text_col = st.selectbox(
                    "📝 Colonne des avis",
                    text_cols,
                    index=text_cols.index(st.session_state.selected_text_col) 
                    if st.session_state.selected_text_col in text_cols else 0,
                    help="Colonne contenant les avis ou commentaires clients"
                )
            
            # Sélection de la colonne client
            client_cols = detect_marketing_columns(data)['client_columns']
            if client_cols:
                st.session_state.selected_client_col = st.selectbox(
                    "👤 Colonne des clients",
                    client_cols,
                    index=client_cols.index(st.session_state.selected_client_col) 
                    if st.session_state.selected_client_col in client_cols else 0,
                    help="Colonne identifiant les clients"
                )
        
        st.markdown("---")
        
        # Déconnexion
        if st.button("🚪 Déconnexion", use_container_width=True, type="secondary"):
            logger.info(f"Déconnexion marketing: {user_info.get('full_name')}")
            
            # Nettoyer la session
            for key in list(st.session_state.keys()):
                if key not in ['logged_in']:
                    del st.session_state[key]
            
            st.session_state.logged_in = False
            st.rerun()
    
    return menu_options[selected_menu]

# =========================PAGES PRINCIPALES===================
def render_performance_page():
    """Page Performance"""
    st.markdown('<h2 class="section-title">📊 Tableau de bord Performance</h2>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-description">
        Cette section présente les indicateurs clés de performance marketing. 
        Surveillez l'évolution de vos métriques, analysez les tendances et prenez des décisions basées sur les données.
    </div>
    """, unsafe_allow_html=True)
    
    # KPI marketing
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">+24.5%</div>
            <div class="metric-label">ROI Marketing</div>
            <div style="font-size: 0.8em; color: #36B37E; margin-top: 0.5rem;">
                ↑ Excellent retour sur investissement
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">3.8%</div>
            <div class="metric-label">Taux de Conversion</div>
            <div style="font-size: 0.8em; color: #36B37E; margin-top: 0.5rem;">
                ↑ Au-dessus de la moyenne du secteur
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">45€</div>
            <div class="metric-label">Coût d'Acquisition</div>
            <div style="font-size: 0.8em; color: #36B37E; margin-top: 0.5rem;">
                ↓ Coût optimisé par rapport au marché
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">4.5/5</div>
            <div class="metric-label">Satisfaction Client</div>
            <div style="font-size: 0.8em; color: #36B37E; margin-top: 0.5rem;">
                → Très bonne satisfaction client
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Analyse des données
    if st.session_state.get('marketing_data') is not None:
        data = st.session_state.marketing_data
        
        st.markdown('<h3 class="section-title">📈 Analyse des performances</h3>', unsafe_allow_html=True)
        
        # Sélection des métriques
        numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
        date_cols = detect_marketing_columns(data)['date_columns']
        
        if numeric_cols and date_cols:
            col1, col2 = st.columns(2)
            
            with col1:
                selected_kpi = st.selectbox(
                    "Sélectionner un KPI à analyser",
                    numeric_cols,
                    help="Sélectionnez une métrique numérique à suivre"
                )
            
            with col2:
                selected_date_col = st.selectbox(
                    "Colonne de date",
                    date_cols,
                    help="Sélectionnez la colonne contenant les dates"
                )
            
            if selected_kpi and selected_date_col:
                fig, interpretation = create_performance_trend_chart(data, selected_date_col, selected_kpi)
                
                if fig:
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown(f'<div class="interpretation-box">{interpretation}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("ℹ️ Importez des données avec des colonnes numériques et de date pour voir les analyses de tendance.")
    
    # Recommandations de performance
    st.markdown('<h3 class="section-title">🎯 Recommandations de performance</h3>', unsafe_allow_html=True)
    
    recommendations = [
        {
            'title': 'Optimiser le budget acquisition',
            'description': 'Allouer plus de budget aux canaux avec ROI > 200%',
            'impact': 'Élevé',
            'timeline': 'Court terme'
        },
        {
            'title': 'Améliorer le taux de conversion',
            'description': 'Mettre en place un tunnel de vente optimisé',
            'impact': 'Moyen',
            'timeline': 'Moyen terme'
        },
        {
            'title': 'Renforcer la fidélisation',
            'description': 'Développer un programme de fidélité client',
            'impact': 'Élevé',
            'timeline': 'Long terme'
        }
    ]
    
    for rec in recommendations:
        st.markdown(f"""
        <div class="strategy-card">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
                <strong style="color: #172B4D;">{rec['title']}</strong>
                <div>
                    <span style="font-size: 0.8em; background: #36B37E20; color: #36B37E; padding: 0.25rem 0.5rem; border-radius: 10px; margin-right: 0.5rem;">
                        {rec['impact']}
                    </span>
                    <span style="font-size: 0.8em; background: #6554C020; color: #6554C0; padding: 0.25rem 0.5rem; border-radius: 10px;">
                        {rec['timeline']}
                    </span>
                </div>
            </div>
            <p style="color: #6B7280; margin: 0; font-size: 0.9em;">{rec['description']}</p>
        </div>
        """, unsafe_allow_html=True)

def render_insights_page():
    """Page Insights AIM"""
    st.markdown('<h2 class="section-title">🔍 Insights Marketing Intelligents</h2>', unsafe_allow_html=True)
    
    if st.session_state.get('marketing_data') is None:
        st.info("📁 Importez des données marketing pour générer des insights")
        return
    
    data = st.session_state.marketing_data
    text_col = st.session_state.get('selected_text_col')
    client_col = st.session_state.get('selected_client_col')
    
    if not text_col:
        st.warning("⚠️ Veuillez sélectionner une colonne de texte dans la sidebar")
        return
    
    st.markdown("""
    <div class="info-description">
        Les insights AIM utilisent l'intelligence artificielle pour analyser les données clients et générer 
        des recommandations actionnables. Cette analyse combine l'analyse de sentiment, la détection de faux avis 
        et l'identification des patterns clients.
    </div>
    """, unsafe_allow_html=True)
    
    # Bouton d'analyse
    if st.button("🚀 Générer les insights AIM", type="primary", use_container_width=True):
        with st.spinner("Analyse en cours... Cela peut prendre quelques secondes"):
            try:
                # Appliquer les analyses
                if 'analyser_sentiment' in globals():
                    data['sentiment'] = data[text_col].apply(analyser_sentiment)
                else:
                    # Fallback pour les tests
                    data['sentiment'] = np.random.choice(['positif', 'négatif', 'neutre'], len(data))
                
                if 'detecter_faux_avis' in globals():
                    data['faux_avis'] = data[text_col].apply(lambda x: detecter_faux_avis(str(x)))
                else:
                    data['faux_avis'] = np.random.choice([True, False], len(data), p=[0.05, 0.95])
                
                st.session_state.marketing_data = data
                
                # Afficher les résultats
                display_aim_insights(data, text_col, client_col)
                
            except Exception as e:
                st.error(f"Erreur lors de l'analyse: {str(e)}")
                logger.error(f"Erreur insights AIM: {str(e)}")
    
    # Si l'analyse a déjà été faite
    if 'sentiment' in data.columns and 'faux_avis' in data.columns:
        display_aim_insights(data, text_col, client_col)

def display_aim_insights(data: pd.DataFrame, text_col: str, client_col: Optional[str]):
    """Afficher les insights AIM"""
    # Calculer les KPI
    kpis = calculate_marketing_kpis(data)
    
    # KPI de synthèse
    st.markdown('<h3 class="section-title">📊 Synthèse des analyses</h3>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        satisfaction = kpis.get('satisfaction_rate', 0)
        color = "#36B37E" if satisfaction > 60 else "#FFAB00" if satisfaction > 40 else "#FF5630"
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: {color};">{satisfaction:.1f}%</div>
            <div class="metric-label">Satisfaction client</div>
            <div style="font-size: 0.8em; color: #6B7280; margin-top: 0.5rem;">
                {kpis.get('positive_reviews', 0)} avis positifs
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        fake_rate = kpis.get('fake_rate', 0)
        color = "#FF5630" if fake_rate > 10 else "#FFAB00" if fake_rate > 5 else "#36B37E"
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: {color};">{fake_rate:.1f}%</div>
            <div class="metric-label">Faux avis détectés</div>
            <div style="font-size: 0.8em; color: #6B7280; margin-top: 0.5rem;">
                {kpis.get('fake_reviews', 0)} avis suspects
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        nps_score = kpis.get('nps_score', 0)
        nps_category = "Promoteur" if nps_score > 50 else "Passif" if nps_score > 0 else "Détracteur"
        color = "#36B37E" if nps_score > 50 else "#FFAB00" if nps_score > 0 else "#FF5630"
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: {color};">{nps_score:.0f}</div>
            <div class="metric-label">Score NPS</div>
            <div style="font-size: 0.8em; color: #6B7280; margin-top: 0.5rem;">
                {nps_category}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Distribution des sentiments
    st.markdown('<h3 class="section-title">📈 Distribution des sentiments</h3>', unsafe_allow_html=True)
    
    fig, interpretation = create_sentiment_distribution_chart(data)
    
    if fig:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(f'<div class="interpretation-box">{interpretation}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Insights marketing générés
    st.markdown('<h3 class="section-title">💡 Insights marketing générés</h3>', unsafe_allow_html=True)
    
    insights = generate_marketing_insights(data, text_col, client_col)
    
    for insight in insights:
        st.markdown(f"""
        <div class="insight-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <div>
                    <strong style="color: {insight.priority_color}; font-size: 1.1em;">{insight.category}</strong>
                    <span class="priority-badge priority-{insight.priority}">
                        Priorité {insight.priority}
                    </span>
                </div>
            </div>
            <h4 style="margin: 0 0 0.5rem 0; color: #172B4D;">{insight.title}</h4>
            <p style="color: #6B7280; margin-bottom: 1rem;">{insight.description}</p>
            
            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                <strong style="color: #172B4D; display: block; margin-bottom: 0.5rem;">🎯 Recommandations:</strong>
                <ul style="margin: 0; padding-left: 1.2rem; color: #6B7280;">
                    {''.join([f'<li>{rec}</li>' for rec in insight.recommendations])}
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Identification des clients (si colonne client disponible)
    if client_col and client_col in data.columns:
        display_client_identification_insights(data, client_col, text_col)

def display_client_identification_insights(data: pd.DataFrame, client_col: str, text_col: str):
    """Afficher les insights d'identification clients"""
    st.markdown('<h3 class="section-title">👤 Identification et analyse clients</h3>', unsafe_allow_html=True)
    
    # Faux avis par client
    if 'faux_avis' in data.columns:
        fake_reviews = data[data['faux_avis'] == True]
        
        if not fake_reviews.empty:
            st.markdown("##### 🚨 Clients à l'origine de faux avis")
            
            fake_by_client = fake_reviews[client_col].value_counts()
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.dataframe(
                    fake_reviews[[client_col, text_col, 'sentiment']].rename(
                        columns={client_col: 'Client', text_col: 'Avis', 'sentiment': 'Sentiment'}
                    ),
                    use_container_width=True,
                    height=300
                )
            
            with col2:
                st.markdown("**📊 Statistiques:**")
                st.metric("Clients suspects", len(fake_by_client))
                st.metric("Faux avis total", len(fake_reviews))
                
                # Téléchargement
                csv = fake_reviews[[client_col, text_col, 'sentiment', 'faux_avis']].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exporter la liste",
                    data=csv,
                    file_name="clients_suspects.csv",
                    mime="text/csv",
                    use_container_width=True
                )
    
    # Analyse par sentiment
    if 'sentiment' in data.columns:
        st.markdown("##### 📊 Analyse des clients par sentiment")
        
        tab1, tab2, tab3 = st.tabs(["😊 Clients positifs", "😠 Clients négatifs", "😐 Clients neutres"])
        
        with tab1:
            positive_clients = data[data['sentiment'] == 'positif']
            if not positive_clients.empty:
                top_positive = positive_clients[client_col].value_counts().head(10)
                
                st.write(f"**Top 10 clients positifs ({len(positive_clients)} avis):**")
                
                for client, count in top_positive.items():
                    with st.expander(f"👤 {client} - {count} avis positifs"):
                        client_reviews = positive_clients[positive_clients[client_col] == client]
                        for idx, row in client_reviews.head(3).iterrows():
                            st.write(f"• {row[text_col][:150]}...")
                
                # Graphique
                fig_pos = create_client_activity_chart(positive_clients, client_col)
                if fig_pos:
                    fig_pos.update_layout(title="Top clients positifs")
                    st.plotly_chart(fig_pos, use_container_width=True)
        
        with tab2:
            negative_clients = data[data['sentiment'] == 'négatif']
            if not negative_clients.empty:
                top_negative = negative_clients[client_col].value_counts().head(10)
                
                st.write(f"**Clients avec avis négatifs ({len(negative_clients)} avis):**")
                
                for client, count in top_negative.items():
                    st.warning(f"**{client}**: {count} avis négatifs")
                    sample = negative_clients[negative_clients[client_col] == client].iloc[0][text_col]
                    st.caption(f"Exemple: {sample[:100]}...")
                
                # Graphique
                fig_neg = create_client_activity_chart(negative_clients, client_col)
                if fig_neg:
                    fig_neg.update_layout(title="Clients avec avis négatifs")
                    st.plotly_chart(fig_neg, use_container_width=True)
        
        with tab3:
            neutral_clients = data[data['sentiment'] == 'neutre']
            if not neutral_clients.empty:
                st.write(f"**Avis neutres par client ({len(neutral_clients)} avis):**")
                st.dataframe(
                    neutral_clients[[client_col, text_col]].rename(
                        columns={client_col: 'Client', text_col: 'Avis'}
                    ),
                    use_container_width=True,
                    height=300
                )
    
    # Recommandations finales
    st.markdown('<h3 class="section-title">🎯 Recommandations actionnables</h3>', unsafe_allow_html=True)
    
    if 'generer_recommandations' in globals():
        recommendations = generer_recommandations(data, text_col)
    else:
        recommendations = [
            "Capitaliser sur les avis positifs dans vos campagnes marketing",
            "Répondre rapidement aux avis négatifs avec des solutions concrètes",
            "Mettre en place un système de vérification des avis pour améliorer la crédibilité",
            "Segmenter votre audience par sentiment pour des campagnes personnalisées",
            "Créer du contenu basé sur les retours clients les plus fréquents",
            "Développer un programme de fidélisation pour les clients satisfaits"
        ]
    
    for i, rec in enumerate(recommendations, 1):
        st.info(f"**{i}.** {rec}")

def render_strategies_page():
    """Page Stratégies"""
    st.markdown('<h2 class="section-title">🎯 Stratégies Marketing</h2>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-description">
        Développez et planifiez vos stratégies marketing basées sur les données. 
        Cette section vous permet de créer des plans d'action, de prioriser les initiatives 
        et de suivre l'impact de vos décisions stratégiques.
    </div>
    """, unsafe_allow_html=True)
    
    # Stratégies recommandées
    st.markdown('<h3 class="section-title">💡 Stratégies recommandées par AIM</h3>', unsafe_allow_html=True)
    
    strategies = [
        {
            'title': 'Capitaliser sur le positif',
            'description': 'Transformer les avis positifs en témoignages impactants',
            'category': 'Content Marketing',
            'impact': 'Élevé',
            'effort': 'Faible'
        },
        {
            'title': 'Améliorer l\'expérience client',
            'description': 'Adresser les points négatifs récurrents identifiés',
            'category': 'CX Optimisation',
            'impact': 'Critique',
            'effort': 'Moyen'
        },
        {
            'title': 'Cibler avec précision',
            'description': 'Segmenter par sentiment pour des campagnes personnalisées',
            'category': 'Audience Targeting',
            'impact': 'Élevé',
            'effort': 'Moyen'
        },
        {
            'title': 'Optimiser les ressources',
            'description': 'Allouer le budget aux canaux les plus performants',
            'category': 'Budget Allocation',
            'impact': 'Élevé',
            'effort': 'Faible'
        }
    ]
    
    # Affichage des stratégies en grille
    cols = st.columns(2)
    
    for idx, strategy in enumerate(strategies):
        with cols[idx % 2]:
            st.markdown(f"""
            <div class="strategy-card">
                <div style="margin-bottom: 0.75rem;">
                    <span style="font-size: 0.8em; background: #36B37E20; color: #36B37E; padding: 0.25rem 0.75rem; border-radius: 12px;">
                        {strategy['category']}
                    </span>
                </div>
                
                <h4 style="margin: 0 0 0.5rem 0; color: #172B4D;">{strategy['title']}</h4>
                <p style="color: #6B7280; margin-bottom: 1rem; font-size: 0.9em;">{strategy['description']}</p>
                
                <div style="display: flex; gap: 0.5rem; margin-top: 1rem;">
                    <div style="flex: 1; text-align: center;">
                        <div style="font-size: 0.75em; color: #6B7280; margin-bottom: 0.25rem;">Impact</div>
                        <div style="font-weight: 600; color: {get_impact_color(strategy['impact'])};">
                            {strategy['impact']}
                        </div>
                    </div>
                    
                    <div style="width: 1px; background: #e5e7eb;"></div>
                    
                    <div style="flex: 1; text-align: center;">
                        <div style="font-size: 0.75em; color: #6B7280; margin-bottom: 0.25rem;">Effort</div>
                        <div style="font-weight: 600; color: {get_effort_color(strategy['effort'])};">
                            {strategy['effort']}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Plan d'action personnel
    st.markdown('<h3 class="section-title">📝 Plan d\'action personnel</h3>', unsafe_allow_html=True)
    
    action_plan = st.text_area(
        "Décrivez votre plan d'action marketing:",
        height=200,
        placeholder="Exemple:\n1. Répondre aux 10 avis négatifs cette semaine\n2. Créer 3 témoignages clients à partir d'avis positifs\n3. Analyser les faux avis détectés et ajuster la stratégie\n4. Segmenter l'audience pour la prochaine campagne\n5. Mesurer l'impact des changements après 30 jours",
        help="Définissez vos actions concrètes basées sur les insights"
    )
    
    col1, col2 = st.columns([1, 3])
    
    with col2:
        if st.button("💾 Sauvegarder le plan", type="primary", use_container_width=True):
            if action_plan.strip():
                st.session_state.marketing_action_plan = action_plan
                st.success("✅ Plan sauvegardé dans votre espace personnel !")
                
                # Option de téléchargement
                plan_text = f"Plan d'action marketing - {datetime.now().strftime('%d/%m/%Y')}\n\n{action_plan}"
                st.download_button(
                    label="📥 Télécharger le plan",
                    data=plan_text,
                    file_name=f"plan_action_marketing_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            else:
                st.warning("Veuillez saisir un plan d'action")
    
    # Affichage du plan sauvegardé
    if 'marketing_action_plan' in st.session_state:
        st.markdown("##### 📋 Plan sauvegardé:")
        st.text(st.session_state.marketing_action_plan)

def get_impact_color(impact: str) -> str:
    """Obtenir la couleur pour l'impact"""
    if impact == 'Critique':
        return MarketingConfig.COLORS['danger']
    elif impact == 'Élevé':
        return MarketingConfig.COLORS['warning']
    else:
        return MarketingConfig.COLORS['info']

def get_effort_color(effort: str) -> str:
    """Obtenir la couleur pour l'effort"""
    if effort == 'Élevé':
        return MarketingConfig.COLORS['danger']
    elif effort == 'Moyen':
        return MarketingConfig.COLORS['warning']
    else:
        return MarketingConfig.COLORS['success']

def render_clients_page():
    """Page Clients"""
    st.markdown('<h2 class="section-title">👥 Identification et Analyse des Clients</h2>', unsafe_allow_html=True)
    
    if st.session_state.get('marketing_data') is None:
        st.info("📁 Importez des données avec une colonne client pour activer cette fonctionnalité")
        return
    
    data = st.session_state.marketing_data
    client_col = st.session_state.get('selected_client_col')
    
    if not client_col:
        st.warning("⚠️ Veuillez sélectionner une colonne client dans la sidebar")
        return
    
    st.markdown("""
    <div class="info-description">
        Analysez le comportement de vos clients, identifiez les segments clés et personnalisez vos stratégies 
        marketing en fonction des profils clients. Cette section permet une compréhension approfondie de votre audience.
    </div>
    """, unsafe_allow_html=True)
    
    # Statistiques globales clients
    col1, col2, col3 = st.columns(3)
    
    with col1:
        unique_clients = data[client_col].nunique()
        st.metric("👥 Clients uniques", unique_clients)
    
    with col2:
        total_reviews = len(data)
        st.metric("📝 Avis totaux", total_reviews)
    
    with col3:
        avg_reviews = total_reviews / unique_clients if unique_clients > 0 else 0
        st.metric("📊 Moyenne avis/client", f"{avg_reviews:.1f}")
    
    # Recherche de client spécifique
    st.markdown('<h3 class="section-title">🔎 Rechercher un client spécifique</h3>', unsafe_allow_html=True)
    
    client_search = st.text_input(
        "Entrez le nom ou l'identifiant d'un client:",
        placeholder="Ex: Jean Dupont ou jdupont@email.com",
        key="client_search_input"
    )
    
    if client_search:
        client_data = data[data[client_col].astype(str).str.contains(client_search, case=False, na=False)]
        
        if not client_data.empty:
            st.success(f"✅ {len(client_data)} avis trouvés pour '{client_search}'")
            
            # Onglets d'analyse
            tab1, tab2, tab3 = st.tabs(["📊 Profil client", "📝 Historique des avis", "📈 Recommandations"])
            
            with tab1:
                display_client_profile(client_data, client_search, client_col)
            
            with tab2:
                display_client_reviews(client_data, client_col)
            
            with tab3:
                display_client_recommendations(client_data, client_col)
        else:
            st.warning(f"Aucun client trouvé avec '{client_search}'")
    
    # Top clients par activité
    st.markdown('<h3 class="section-title">🏆 Top clients par activité</h3>', unsafe_allow_html=True)
    
    client_activity = data[client_col].value_counts().head(15)
    
    fig = create_client_activity_chart(data, client_col)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    
    # Segmentation clients
    st.markdown('<h3 class="section-title">🎯 Segmentation clients</h3>', unsafe_allow_html=True)
    
    if 'sentiment' in data.columns:
        display_client_segmentation(data, client_col)
    
    # Export des données clients
    st.markdown('<h3 class="section-title">📤 Export des données clients</h3>', unsafe_allow_html=True)
    
    if st.button("📊 Générer le rapport complet clients", type="primary", use_container_width=True):
        with st.spinner("Génération du rapport en cours..."):
            # Créer un rapport synthétique
            client_summary = create_client_summary_report(data, client_col)
            
            st.dataframe(client_summary, use_container_width=True, height=400)
            
            # Options de téléchargement
            col1, col2 = st.columns(2)
            
            with col1:
                # CSV
                csv = client_summary.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Télécharger en CSV",
                    data=csv,
                    file_name=f"rapport_clients_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True
                )
            
            with col2:
                # Excel
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    client_summary.to_excel(writer, index=False, sheet_name='Rapport Clients')
                excel_data = excel_buffer.getvalue()
                
                st.download_button(
                    label="📊 Télécharger en Excel",
                    data=excel_data,
                    file_name=f"rapport_clients_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="secondary",
                    use_container_width=True
                )

def display_client_profile(client_data: pd.DataFrame, client_name: str, client_col: str):
    """Afficher le profil d'un client"""
    st.markdown(f"##### Profil de **{client_name}**")
    
    # Calculer les statistiques
    total_reviews = len(client_data)
    
    if 'sentiment' in client_data.columns:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            positive_count = (client_data['sentiment'] == 'positif').sum()
            st.metric("Avis positifs", positive_count)
        
        with col2:
            negative_count = (client_data['sentiment'] == 'négatif').sum()
            st.metric("Avis négatifs", negative_count)
        
        with col3:
            neutral_count = (client_data['sentiment'] == 'neutre').sum()
            st.metric("Avis neutres", neutral_count)
    
    if 'faux_avis' in client_data.columns:
        fake_count = client_data['faux_avis'].sum()
        if fake_count > 0:
            st.error(f"⚠️ **{fake_count} faux avis** détectés pour ce client")
    
    # Dates importantes
    if 'date' in client_data.columns:
        try:
            client_data['date'] = pd.to_datetime(client_data['date'], errors='coerce')
            first_review = client_data['date'].min()
            last_review = client_data['date'].max()
            
            st.info(f"""
            **📅 Historique d'activité:**
            - Premier avis: {first_review.strftime('%d/%m/%Y') if pd.notna(first_review) else 'Non disponible'}
            - Dernier avis: {last_review.strftime('%d/%m/%Y') if pd.notna(last_review) else 'Non disponible'}
            """)
        except:
            pass
    
    # Segmentation
    if 'sentiment' in client_data.columns:
        positive_count = (client_data['sentiment'] == 'positif').sum()
        satisfaction_rate = (positive_count / total_reviews * 100) if total_reviews > 0 else 0
        
        if satisfaction_rate > 80:
            segment = "Ambassadeur"
            color = "#36B37E"
        elif satisfaction_rate > 60:
            segment = "Fidèle"
            color = "#6554C0"
        elif (client_data['sentiment'] == 'négatif').sum() >= 2:
            segment = "À risque"
            color = "#FF5630"
        else:
            segment = "Standard"
            color = "#FFAB00"
        
        st.markdown(f"""
        <div style="background: {color}20; padding: 1rem; border-radius: 8px; border-left: 4px solid {color}; margin-top: 1rem;">
            <strong>Segment client: {segment}</strong><br>
            <small>Taux de satisfaction: {satisfaction_rate:.1f}%</small>
        </div>
        """, unsafe_allow_html=True)

def display_client_reviews(client_data: pd.DataFrame, client_col: str):
    """Afficher les avis d'un client"""
    st.markdown("##### Liste des avis")
    
    text_col = st.session_state.get('selected_text_col', client_data.columns[1] if len(client_data.columns) > 1 else 'text')
    
    for idx, row in client_data.iterrows():
        sentiment = row.get('sentiment', 'Non analysé')
        is_fake = row.get('faux_avis', False)
        
        # Déterminer la classe CSS
        if sentiment == 'positif':
            card_class = "client-card-positive"
        elif sentiment == 'négatif':
            card_class = "client-card-negative"
        else:
            card_class = "client-card-neutral"
        
        # Déterminer les couleurs
        sentiment_color = MarketingConfig.SENTIMENT_COLORS.get(sentiment, MarketingConfig.COLORS['light'])
        fake_color = "#DC3545" if is_fake else "#28A745"
        
        st.markdown(f"""
        <div class="client-card {card_class}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <strong style="color: #172B4D;">Avis #{idx if hasattr(row, 'name') else 'N/A'}</strong>
                <div style="display: flex; gap: 1rem;">
                    <span style="color: {sentiment_color}; font-weight: bold;">{sentiment.upper()}</span>
                    <span style="color: {fake_color}; font-size: 0.9em;">
                        {'⚠️ FAUX' if is_fake else '✅ VRAI'}
                    </span>
                </div>
            </div>
            <p style="margin: 0.5rem 0; color: #4B5563; line-height: 1.5;">{row[text_col]}</p>
            <div style="font-size: 0.85em; color: #6B7280; margin-top: 0.5rem;">
                📅 {row.get('date', 'Date non spécifiée') if 'date' in row.index else 'Sans date'}
            </div>
        </div>
        """, unsafe_allow_html=True)

def display_client_recommendations(client_data: pd.DataFrame, client_col: str):
    """Afficher les recommandations pour un client"""
    st.markdown("##### 🎯 Recommandations d'actions")
    
    if 'sentiment' in client_data.columns:
        negative_count = (client_data['sentiment'] == 'négatif').sum()
        
        if negative_count > 2:
            st.error(f"""
            **🚨 Action Prioritaire Requise**
            
            Ce client a **{negative_count} avis négatifs**.
            
            **Actions recommandées:**
            1. Contacter immédiatement pour comprendre les problèmes
            2. Offrir une solution ou une compensation appropriée
            3. Mettre en place un suivi strict pendant 30 jours
            4. Assigner un account manager dédié
            
            **Objectif:** Reconquérir le client et transformer l'expérience
            """)
        elif negative_count == 1:
            st.warning(f"""
            **⚠️ À Surveiller**
            
            Ce client a **1 avis négatif**.
            
            **Actions recommandées:**
            1. Envoyer un email de suui personnalisé
            2. S'assurer que le problème est résolu
            3. Suivre la satisfaction lors du prochain contact
            
            **Objectif:** Prévenir la perte du client
            """)
        
        positive_count = (client_data['sentiment'] == 'positif').sum()
        if positive_count >= 3:
            st.success(f"""
            **💎 Opportunité de Fidélisation**
            
            Ce client a **{positive_count} avis positifs**.
            
            **Actions recommandées:**
            1. Proposer un programme de fidélité ou de parrainage
            2. Demander un témoignage pour les campagnes marketing
            3. Offrir un avantage exclusif ou une promotion spéciale
            
            **Objectif:** Transformer en ambassadeur de la marque
            """)
    
    if 'faux_avis' in client_data.columns:
        fake_count = client_data['faux_avis'].sum()
        if fake_count > 0:
            st.error(f"""
            **🔍 Suspicion de Fraude Identifiée**
            
            **{fake_count} faux avis** détectés pour ce client.
            
            **Actions immédiates:**
            1. Investigation approfondie requise
            2. Possible restriction du compte
            3. Notification à l'équipe de sécurité
            4. Audit des autres avis de ce client
            
            **Objectif:** Protéger l'intégrité de la plateforme
            """)

def display_client_segmentation(data: pd.DataFrame, client_col: str):
    """Afficher la segmentation clients"""
    # Calculer la satisfaction par client
    client_sentiment = data.groupby(client_col)['sentiment'].apply(
        lambda x: (x == 'positif').sum() / len(x) * 100 if len(x) > 0 else 0
    ).reset_index()
    
    client_sentiment.columns = [client_col, 'satisfaction_rate']
    
    # Ajouter le nombre total d'avis
    client_activity = data[client_col].value_counts().reset_index()
    client_activity.columns = [client_col, 'total_reviews']
    
    # Fusionner les données
    client_segmentation = pd.merge(client_sentiment, client_activity, on=client_col)
    
    # Définir les segments
    def assign_segment(row):
        if row['satisfaction_rate'] > 80 and row['total_reviews'] >= 3:
            return 'Ambassadeur'
        elif row['satisfaction_rate'] > 60:
            return 'Fidèle'
        elif (data[data[client_col] == row[client_col]]['sentiment'] == 'négatif').sum() >= 2:
            return 'À risque'
        else:
            return 'Standard'
    
    client_segmentation['segment'] = client_segmentation.apply(assign_segment, axis=1)
    
    # Statistiques par segment
    segment_stats = client_segmentation['segment'].value_counts()
    
    col1, col2, col3, col4 = st.columns(4)
    
    segments = ['Ambassadeur', 'Fidèle', 'Standard', 'À risque']
    colors = ['#36B37E', '#6554C0', '#FFAB00', '#FF5630']
    
    for idx, segment in enumerate(segments):
        with [col1, col2, col3, col4][idx]:
            count = segment_stats.get(segment, 0)
            percentage = (count / len(client_segmentation) * 100) if len(client_segmentation) > 0 else 0
            
            st.markdown(f"""
            <div style="text-align: center;">
                <div style="font-size: 2em; font-weight: bold; color: {colors[idx]};">{count}</div>
                <div style="font-size: 0.9em; color: #6B7280;">{segment}</div>
                <div style="font-size: 0.8em; color: #9CA3AF;">{percentage:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Graphique de segmentation
    fig = px.pie(
        values=segment_stats.values,
        names=segment_stats.index,
        title="Répartition des segments clients",
        color=segment_stats.index,
        color_discrete_map=dict(zip(segments, colors))
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    
    st.plotly_chart(fig, use_container_width=True)

def create_client_summary_report(data: pd.DataFrame, client_col: str) -> pd.DataFrame:
    """Créer un rapport synthétique clients"""
    report_data = []
    
    for client in data[client_col].unique()[:100]:  # Limiter pour la performance
        client_data = data[data[client_col] == client]
        
        profile = ClientProfile(
            name=client,
            total_reviews=len(client_data),
            positive_count=client_data[client_data['sentiment'] == 'positif'].shape[0] 
                         if 'sentiment' in data.columns else 0,
            negative_count=client_data[client_data['sentiment'] == 'négatif'].shape[0] 
                         if 'sentiment' in data.columns else 0,
            neutral_count=client_data[client_data['sentiment'] == 'neutre'].shape[0] 
                         if 'sentiment' in data.columns else 0,
            fake_reviews=client_data['faux_avis'].sum() 
                         if 'faux_avis' in data.columns else 0
        )
        
        report_row = {
            'Client': profile.name,
            'Total avis': profile.total_reviews,
            'Avis positifs': profile.positive_count,
            'Avis négatifs': profile.negative_count,
            'Avis neutres': profile.neutral_count,
            'Faux avis': profile.fake_reviews,
            'Taux satisfaction': f"{profile.satisfaction_score:.1f}%",
            'Segment': profile.client_value,
            'Valeur client': profile.client_value
        }
        
        if 'date' in data.columns:
            try:
                dates = pd.to_datetime(client_data['date'], errors='coerce')
                report_row['Premier avis'] = dates.min().strftime('%d/%m/%Y') if pd.notna(dates.min()) else 'N/A'
                report_row['Dernier avis'] = dates.max().strftime('%d/%m/%Y') if pd.notna(dates.max()) else 'N/A'
            except:
                report_row['Premier avis'] = 'N/A'
                report_row['Dernier avis'] = 'N/A'
        
        report_data.append(report_row)
    
    report_df = pd.DataFrame(report_data)
    return report_df.sort_values('Total avis', ascending=False)

# =========================FONCTION PRINCIPALE===================
def show_marketing_dashboard():
    """Interface principale du Marketing Manager"""
    
    # Initialisation de l'état
    if 'marketing_data' not in st.session_state:
        st.session_state.marketing_data = None
    if 'selected_text_col' not in st.session_state:
        st.session_state.selected_text_col = None
    if 'selected_client_col' not in st.session_state:
        st.session_state.selected_client_col = None
    
    # Appliquer le CSS
    st.markdown(page_bg_css(), unsafe_allow_html=True)
    
    # En-tête principal
    st.markdown(f"""
    <div class="main-header">
        <h1 style="color: white; margin-bottom: 0.5rem; font-size: 2.5em; font-weight: 700;">
            Dashboard Marketing Manager
        </h1>
        <p style="color: rgba(255,255,255,0.95); font-size: 1.2em; margin-bottom: 0;">
            Optimisation marketing avec insights AIM - Data-Driven Decisions
        </p>
        <p style="color: rgba(255,255,255,0.8); font-size: 0.9em; margin-top: 0.5rem;">
            <i class="fas fa-chart-line"></i> Dernière mise à jour: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        # Navigation via sidebar
        selected_section = render_marketing_sidebar()
        
        # Affichage de la section sélectionnée
        if selected_section == "performance":
            render_performance_page()
        
        elif selected_section == "insights":
            render_insights_page()
        
        elif selected_section == "strategies":
            render_strategies_page()
        
        elif selected_section == "clients":
            render_clients_page()
        
        # Footer
        st.markdown("---")
        st.markdown(
            f'<div style="text-align: center; color: #6B7280; font-size: 0.9em; padding: 1rem;">'
            f'© {datetime.now().year} - Dashboard Marketing Manager | '
            f'Dernière mise à jour: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}'
            f'</div>',
            unsafe_allow_html=True
        )
    
    except Exception as e:
        logger.error(f"Erreur dans le dashboard marketing: {str(e)}", exc_info=True)
        
        st.error("❌ Une erreur est survenue lors de l'exécution du dashboard")
        st.error(f"Détails techniques: {str(e)}")
        
        if st.button("🔄 Réinitialiser l'application", type="primary"):
            for key in list(st.session_state.keys()):
                if key != 'logged_in':
                    del st.session_state[key]
            st.rerun()

# =========================POINT D'ENTRÉE===================
if __name__ == "__main__":
    show_marketing_dashboard()