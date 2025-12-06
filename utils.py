# utils.py
import pandas as pd
import numpy as np
import hashlib
import json
import os
import uuid
import re
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from textblob import TextBlob
from collections import Counter
import warnings
import nltk
warnings.filterwarnings('ignore')

# ==================== CONFIGURATION ====================
AIM_CONFIG_FILE = "aim_config.json"
USERS_FILE = "users.json"

# Télécharger les ressources NLTK
try:
    nltk.download('vader_lexicon', quiet=True)
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    sia = SentimentIntensityAnalyzer()
except:
    sia = None

# ==================== CONFIGURATION AIM ====================
def load_aim_config():
    """Charge la configuration AIM depuis un fichier JSON"""
    default_config = {
        "modules": {
            "fake_review_detection": {
                "active": True,
                "threshold": 0.7,
                "min_review_length": 10
            },
            "sentiment_analysis": {
                "active": True,
                "model": "vader",
                "auto_detect": True
            },
            "recommendations": {
                "active": True,
                "frequency": "weekly",
                "auto_generate": True
            }
        },
        "kpis": {
            "data_analyst": ["fake_review_rate", "sentiment_distribution", "review_volume"],
            "marketing": ["nps_score", "conversion_rate", "roi_impact"],
            "admin": ["system_uptime", "user_activity", "model_accuracy"]
        }
    }
    
    if os.path.exists(AIM_CONFIG_FILE):
        try:
            with open(AIM_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default_config
    return default_config

def save_aim_config(config):
    """Sauvegarde la configuration AIM"""
    with open(AIM_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# ==================== FONCTIONS AIM ====================
def detecter_faux_avis(texte, seuil=0.7):
    """Détecte les faux avis basés sur des motifs communs"""
    if not isinstance(texte, str):
        return False
    
    motifs_faux_avis = [
        r'trop.*bon', r'incroyable.*produit', r'meilleur.*achat',
        r'parfait.*.*parfait', r'excellent.*.*excellent',
        r'sans.*faute', r'absolument.*parfait'
    ]
    
    score = 0
    texte_lower = texte.lower()
    
    for motif in motifs_faux_avis:
        if re.search(motif, texte_lower):
            score += 0.2
    
    if len(texte.split()) < 10:
        score += 0.3
    
    try:
        blob = TextBlob(texte)
        if abs(blob.sentiment.polarity) > 0.8:
            score += 0.2
    except:
        pass
    
    return score > seuil

def analyser_sentiment(texte):
    """Analyse le sentiment d'un texte"""
    if not isinstance(texte, str) or not texte.strip():
        return "neutre"
    
    if sia:
        scores = sia.polarity_scores(texte)
        if scores['compound'] >= 0.05:
            return "positif"
        elif scores['compound'] <= -0.05:
            return "négatif"
        else:
            return "neutre"
    else:
        positive_words = ['bon', 'excellent', 'super', 'génial', 'parfait']
        negative_words = ['mauvais', 'nul', 'horrible', 'déçu', 'décevant']
        
        texte_lower = texte.lower()
        pos_count = sum(1 for word in positive_words if word in texte_lower)
        neg_count = sum(1 for word in negative_words if word in texte_lower)
        
        if pos_count > neg_count:
            return "positif"
        elif neg_count > pos_count:
            return "négatif"
        else:
            return "neutre"

def generer_recommandations(df, colonne_texte='avis'):
    """Génère des recommandations marketing basées sur les données"""
    if df is None or colonne_texte not in df.columns:
        return ["Aucune donnée disponible pour générer des recommandations"]
    
    recommandations = []
    
    if 'sentiment' not in df.columns:
        df['sentiment'] = df[colonne_texte].apply(analyser_sentiment)
    
    total_avis = len(df)
    avis_positifs = (df['sentiment'] == 'positif').sum()
    avis_negatifs = (df['sentiment'] == 'négatif').sum()
    
    ratio_positifs = avis_positifs / total_avis if total_avis > 0 else 0
    if ratio_positifs < 0.6:
        recommandations.append(
            f"**Amélioration de l'expérience client**\n"
            f"Avec seulement {ratio_positifs:.1%} d'avis positifs, concentrez-vous sur les points négatifs récurrents."
        )
    else:
        recommandations.append(
            f"**Excellente satisfaction client**\n"
            f"{ratio_positifs:.1%} d'avis positifs. Mettez en avant ces retours dans votre communication."
        )
    
    if 'faux_avis' not in df.columns:
        df['faux_avis'] = df[colonne_texte].apply(lambda x: detecter_faux_avis(str(x)))
    
    faux_avis_count = df['faux_avis'].sum()
    if faux_avis_count > 0:
        recommandations.append(
            f"**Vigilance sur les faux avis**\n"
            f"{faux_avis_count} faux avis détectés. Considérez leur suppression pour maintenir la crédibilité."
        )
    
    return recommandations

# ==================== FONCTIONS VISUALISATION ====================
def create_kpi_card(title, value, color="#667eea", interpretation=""):
    """Crée une carte KPI stylisée avec interprétation"""
    card_html = f"""
    <div class="kpi-card" style="border-left-color: {color};">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h3 style="color: {color}; margin: 0; font-size: 2em;">{value}</h3>
                <p style="color: #666; margin: 5px 0 0 0; font-weight: 500;">{title}</p>
            </div>
        </div>
    </div>
    """
    
    if interpretation:
        card_html += f"""
        <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; margin-top: 5px; font-size: 0.85em; color: #666;">
             {interpretation}
        </div>
        """
    
    return card_html

def create_sentiment_chart(data, sentiment_col='sentiment'):
    """Crée un graphique de répartition des sentiments"""
    if data is None or sentiment_col not in data.columns:
        return None, ""
    
    sentiment_counts = data[sentiment_col].value_counts()
    colors = {'positif': '#36B37E', 'négatif': '#FF5630', 'neutre': '#FFAB00'}
    
    fig = go.Figure(data=[go.Pie(
        labels=sentiment_counts.index,
        values=sentiment_counts.values,
        hole=.4,
        marker_colors=[colors.get(str(s).lower(), '#6554C0') for s in sentiment_counts.index],
        textinfo='percent+label',
        textposition='inside'
    )])
    
    fig.update_layout(
        title="Répartition des Sentiments",
        height=400,
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#172B4D')
    )
    
    interpretation = ""
    if len(sentiment_counts) > 0:
        dominant = sentiment_counts.idxmax()
        ratio = sentiment_counts.max() / sentiment_counts.sum()
        
        if dominant == 'positif' and ratio > 0.6:
            interpretation = f"Excellent! {ratio:.1%} des avis sont positifs."
        elif dominant == 'négatif' and ratio > 0.4:
            interpretation = f"Attention: {ratio:.1%} des avis sont négatifs. Action requise."
        elif dominant == 'neutre':
            interpretation = f"Principalement neutre ({ratio:.1%}). Améliorez l'engagement."
    
    return fig, interpretation

def create_fake_review_analysis(data, text_col='avis'):
    """Crée des visualisations pour l'analyse des faux avis"""
    if data is None or text_col not in data.columns:
        return [], ""
    
    visualizations = []
    interpretations = []
    
    data['faux_avis'] = data[text_col].apply(lambda x: detecter_faux_avis(str(x)))
    fake_count = data['faux_avis'].sum()
    total = len(data)
    
    fig1 = go.Figure(data=[go.Pie(
        labels=['Vrais Avis', 'Faux Avis'],
        values=[total - fake_count, fake_count],
        hole=.3,
        marker_colors=['#36B37E', '#FF5630'],
        textinfo='percent+label'
    )])
    
    fig1.update_layout(
        title="Répartition Vrais/Faux Avis",
        height=300,
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    interp1 = f"{fake_count} faux avis détectés ({fake_count/total*100:.1f}% du total)"
    visualizations.append(fig1)
    interpretations.append(interp1)
    
    return visualizations, interpretations

def create_bar_chart(data, column, title, top_n=10):
    """Crée un diagramme en barres"""
    if data is None or column not in data.columns:
        return None, ""
    
    value_counts = data[column].value_counts().head(top_n)
    
    fig = px.bar(
        x=value_counts.index,
        y=value_counts.values,
        title=title,
        labels={'x': column, 'y': 'Nombre'},
        color=value_counts.values,
        color_continuous_scale=['#6554C0', '#36B37E', '#FFAB00']
    )
    
    fig.update_layout(
        height=400,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#172B4D')
    )
    
    interpretation = ""
    if len(value_counts) > 0:
        top_value = value_counts.iloc[0]
        total = value_counts.sum()
        interpretation = f"La catégorie '{value_counts.index[0]}' représente {top_value/total*100:.1f}% du total"
    else:
        interpretation = "Pas assez de données pour l'interprétation"
    
    return fig, interpretation

def create_trend_chart(data, date_col='date', value_col=None):
    """Crée un graphique de tendance temporelle"""
    if data is None or date_col not in data.columns:
        return None, ""
    
    try:
        data[date_col] = pd.to_datetime(data[date_col])
        
        if value_col:
            daily_data = data.groupby(data[date_col].dt.date)[value_col].mean().reset_index()
            title = f"Évolution de {value_col}"
            y_label = value_col
        else:
            daily_data = data.groupby(data[date_col].dt.date).size().reset_index()
            daily_data.columns = ['date', 'count']
            title = "Évolution du Volume"
            y_label = "Nombre"
        
        fig = px.line(daily_data, x='date', y=daily_data.columns[1], 
                     title=title,
                     markers=True,
                     color_discrete_sequence=['#6554C0'])
        
        fig.update_layout(
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis_title="Date",
            yaxis_title=y_label,
            font=dict(color='#172B4D')
        )
        
        interpretation = ""
        if len(daily_data) > 1:
            first_val = daily_data.iloc[0][daily_data.columns[1]]
            last_val = daily_data.iloc[-1][daily_data.columns[1]]
            change = ((last_val - first_val) / first_val * 100) if first_val != 0 else 0
            
            if change > 10:
                interpretation = f"Forte augmentation de {change:.1f}% sur la période"
            elif change < -10:
                interpretation = f"Diminution significative de {abs(change):.1f}% sur la période"
            else:
                interpretation = f"Évolution stable ({change:.1f}% de variation)"
        else:
            interpretation = "Données insuffisantes pour l'analyse de tendance"
        
        return fig, interpretation
    except Exception as e:
        return None, f"Erreur: {str(e)}"

# ==================== CSS STYLES ====================
page_bg_css = """
<style>
.stApp {
    background: #F4F5F7 !important;
    min-height: 100vh;
}

.main-header {
    text-align: center;
    padding: 25px;
    background: linear-gradient(135deg, #FFFFFF 0%, #F9FAFB 100%);
    border-radius: 12px;
    margin-bottom: 30px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    border: 1px solid #E5E7EB;
}

.kpi-card {
    background: white;
    border-radius: 12px;
    padding: 20px;
    margin: 10px 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    transition: all 0.3s ease;
    border-left: 4px solid;
    border-top: 1px solid #F3F4F6;
}

.kpi-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 12px rgba(0,0,0,0.08);
}

.login-container {
    background: white;
    border-radius: 16px;
    padding: 40px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.08);
    max-width: 500px;
    margin: 50px auto;
    border: 1px solid #E5E7EB;
}

.role-badge {
    display: inline-block;
    padding: 6px 16px;
    border-radius: 20px;
    font-weight: 600;
    margin: 5px;
    font-size: 0.8em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.admin-badge { 
    background: linear-gradient(135deg, #FF5630 0%, #DE350B 100%); 
    color: white;
    border: none;
}

.analyst-badge { 
    background: linear-gradient(135deg, #6554C0 0%, #403294 100%); 
    color: white;
    border: none;
}

.marketing-badge { 
    background: linear-gradient(135deg, #36B37E 0%, #00875A 100%); 
    color: white;
    border: none;
}

.chart-container {
    background: white;
    border-radius: 12px;
    padding: 20px;
    margin: 15px 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    border: 1px solid #E5E7EB;
}

.stButton > button {
    border-radius: 8px !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
    border: none !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1) !important;
}

.recommendation-card {
    background: white;
    border-left: 4px solid #36B37E;
    padding: 18px;
    margin: 12px 0;
    border-radius: 8px;
    transition: all 0.3s ease;
    border: 1px solid #E5E7EB;
    box-shadow: 0 2px 4px rgba(0,0,0,0.03);
}

.recommendation-card:hover {
    transform: translateX(4px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.06);
}

.interpretation-box {
    background: #F8F9FA;
    border-left: 4px solid #6554C0;
    padding: 12px 16px;
    margin-top: 10px;
    border-radius: 6px;
    font-size: 0.9em;
    color: #4B5563;
}

.user-table {
    background: white;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    border: 1px solid #E5E7EB;
}

.user-table-header {
    background: linear-gradient(135deg, #F3F4F6 0%, #E5E7EB 100%);
    padding: 16px;
    font-weight: 600;
    color: #374151;
}

.user-table-row {
    padding: 16px;
    border-bottom: 1px solid #F3F4F6;
    transition: background 0.3s ease;
}

.user-table-row:hover {
    background: #F9FAFB;
}

[data-testid="stSidebar"] {
    background: white;
}

h1, h2, h3, h4 {
    color: #172B4D !important;
}

p {
    color: #4B5563 !important;
}
</style>
"""