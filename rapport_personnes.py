# rapport_personnes.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

def generer_rapport_personnes(data, name_col, text_col, sentiment_col=None, faux_avis_col=None, date_col=None):
    """Génère un rapport détaillé par personne"""
    
    rapport = {
        "statistiques": {},
        "personnes_a_suivre": [],
        "recommandations": [],
        "alertes": [],
        "visualisations": []
    }
    
    # Vérifier que la colonne des noms existe
    if name_col not in data.columns:
        rapport["erreur"] = f"Colonne '{name_col}' non trouvée dans les données"
        return rapport
    
    # Statistiques générales
    total_personnes = data[name_col].nunique()
    total_avis = len(data)
    
    rapport["statistiques"]["total_personnes"] = total_personnes
    rapport["statistiques"]["total_avis"] = total_avis
    rapport["statistiques"]["moyenne_avis_par_personne"] = total_avis / total_personnes if total_personnes > 0 else 0
    
    # Analyse par personne
    personnes_stats = []
    alertes_urgentes = []
    
    for personne in data[name_col].unique()[:100]:  # Limiter pour la performance
        personne_data = data[data[name_col] == personne]
        
        personne_stats = {
            "personne": personne,
            "nombre_avis": len(personne_data),
            "premier_avis": personne_data.iloc[0][text_col][:100] + "..." if len(personne_data) > 0 else "",
            "dernier_avis": personne_data.iloc[-1][text_col][:100] + "..." if len(personne_data) > 0 else ""
        }
        
        # Ajouter les dates si disponibles
        if date_col and date_col in data.columns:
            try:
                dates = pd.to_datetime(personne_data[date_col])
                personne_stats["date_premier"] = dates.min().strftime('%Y-%m-%d')
                personne_stats["date_dernier"] = dates.max().strftime('%Y-%m-%d')
                personne_stats["frequence_jours"] = (dates.max() - dates.min()).days if len(dates) > 1 else 0
            except:
                personne_stats["date_premier"] = "N/A"
                personne_stats["date_dernier"] = "N/A"
        
        # Ajouter les sentiments si disponibles
        if sentiment_col and sentiment_col in data.columns:
            sentiments = personne_data[sentiment_col].value_counts()
            personne_stats["positifs"] = sentiments.get('positif', 0)
            personne_stats["negatifs"] = sentiments.get('négatif', 0)
            personne_stats["neutres"] = sentiments.get('neutre', 0)
            
            # Calculer le ratio de satisfaction
            total_sentiments = personne_stats["positifs"] + personne_stats["negatifs"] + personne_stats["neutres"]
            if total_sentiments > 0:
                personne_stats["ratio_satisfaction"] = personne_stats["positifs"] / total_sentiments * 100
            else:
                personne_stats["ratio_satisfaction"] = 0
        
        # Ajouter les faux avis si disponibles
        if faux_avis_col and faux_avis_col in data.columns:
            faux_count = personne_data[faux_avis_col].sum()
            personne_stats["faux_avis"] = faux_count
            
            if faux_count > 0:
                alerte = {
                    "personne": personne,
                    "raison": f"{faux_count} faux avis détectés",
                    "priorite": "Haute" if faux_count > 2 else "Moyenne",
                    "action": "Investigation immédiate" if faux_count > 2 else "Surveillance"
                }
                rapport["personnes_a_suivre"].append(alerte)
                alertes_urgentes.append(alerte)
        
        # Détecter les patterns suspects
        if personne_stats["nombre_avis"] > 10:
            alerte_activite = {
                "personne": personne,
                "raison": f"{personne_stats['nombre_avis']} avis (activité élevée)",
                "priorite": "Moyenne",
                "action": "Vérifier l'authenticité"
            }
            rapport["personnes_a_suivre"].append(alerte_activite)
        
        personnes_stats.append(personne_stats)
    
    rapport["details_personnes"] = pd.DataFrame(personnes_stats)
    
    # Générer des recommandations
    if len(alertes_urgentes) > 0:
        rapport["recommandations"].append(
            f"Contacter {len(alertes_urgentes)} personne(s) pour faux avis (investigation requise)"
        )
    
    if sentiment_col and sentiment_col in data.columns:
        personnes_negatives = rapport["details_personnes"][rapport["details_personnes"]["negatifs"] > 2]
        if len(personnes_negatives) > 0:
            rapport["recommandations"].append(
                f"Suivre {len(personnes_negatives)} personne(s) avec avis négatifs répétés"
            )
    
    # Générer des visualisations
    try:
        # 1. Distribution du nombre d'avis par personne
        fig1 = px.histogram(
            rapport["details_personnes"],
            x='nombre_avis',
            nbins=20,
            title="Distribution du nombre d'avis par personne",
            labels={'nombre_avis': "Nombre d'avis", 'count': 'Nombre de personnes'}
        )
        rapport["visualisations"].append({"titre": "Distribution des avis", "figure": fig1})
        
        # 2. Top 10 des personnes les plus actives
        top_10 = rapport["details_personnes"].nlargest(10, 'nombre_avis')
        fig2 = px.bar(
            top_10,
            x='personne',
            y='nombre_avis',
            title="Top 10 des personnes les plus actives",
            color='nombre_avis',
            color_continuous_scale='viridis'
        )
        fig2.update_layout(xaxis_tickangle=-45)
        rapport["visualisations"].append({"titre": "Top 10 actifs", "figure": fig2})
        
    except Exception as e:
        rapport["erreurs_visualisation"] = str(e)
    
    return rapport

def afficher_rapport_personnes(data, name_col, text_col):
    """Affiche le rapport dans Streamlit"""
    
    st.markdown("## 📊 Rapport Détaillé par Personne")
    
    if name_col not in data.columns:
        st.error(f"Colonne '{name_col}' non trouvée dans les données")
        return
    
    # Statistiques générales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Personnes uniques", data[name_col].nunique())
    
    with col2:
        st.metric("Avis au total", len(data))
    
    with col3:
        avg_reviews = len(data) / data[name_col].nunique() if data[name_col].nunique() > 0 else 0
        st.metric("Moyenne avis/personne", f"{avg_reviews:.1f}")
    
    with col4:
        if 'sentiment' in data.columns:
            positive = (data['sentiment'] == 'positif').sum()
            st.metric("Avis positifs", positive)
    
    # Top contributeurs
    st.markdown("### 🏆 Top Contributeurs")
    top_contributors = data[name_col].value_counts().head(15)
    
    fig = px.bar(
        x=top_contributors.values,
        y=top_contributors.index,
        orientation='h',
        title="Personnes avec le plus d'avis",
        labels={'x': "Nombre d'avis", 'y': 'Personne'},
        color=top_contributors.values,
        color_continuous_scale='Viridis'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Analyse détaillée par sentiment
    if 'sentiment' in data.columns:
        st.markdown("### 😊 Analyse des Sentiments par Personne")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Personnes avec le plus d'avis positifs
            positive_counts = data[data['sentiment'] == 'positif'][name_col].value_counts().head(10)
            if len(positive_counts) > 0:
                st.markdown("**Top contributeurs positifs:**")
                for person, count in positive_counts.items():
                    st.success(f"✅ **{person}**: {count} avis positifs")
        
        with col2:
            # Personnes avec le plus d'avis négatifs
            negative_counts = data[data['sentiment'] == 'négatif'][name_col].value_counts().head(10)
            if len(negative_counts) > 0:
                st.markdown("**Personnes avec avis négatifs:**")
                for person, count in negative_counts.items():
                    st.error(f"❌ **{person}**: {count} avis négatifs")
    
    # Liste détaillée
    st.markdown("### 📋 Détails par Personne")
    
    for person in top_contributors.index[:10]:
        person_data = data[data[name_col] == person]
        
        with st.expander(f"👤 {person} ({len(person_data)} avis)"):
            col_a, col_b = st.columns([2, 1])
            
            with col_a:
                st.markdown("**Derniers avis:**")
                for i, (_, row) in enumerate(person_data.head(3).iterrows()):
                    sentiment = row.get('sentiment', 'Non analysé')
                    sentiment_emoji = "😊" if sentiment == 'positif' else "😠" if sentiment == 'négatif' else "😐"
                    st.write(f"{i+1}. {sentiment_emoji} {row[text_col][:150]}...")
            
            with col_b:
                if 'sentiment' in data.columns:
                    sentiments = person_data['sentiment'].value_counts()
                    st.markdown("**Répartition:**")
                    for sentiment, count in sentiments.items():
                        emoji = "🟢" if sentiment == 'positif' else "🔴" if sentiment == 'négatif' else "🟡"
                        st.write(f"{emoji} {sentiment}: {count}")
                
                if 'faux_avis' in data.columns:
                    fake_count = person_data['faux_avis'].sum()
                    if fake_count > 0:
                        st.error(f"⚠️ {fake_count} faux avis détectés")
    
    # Export des données
    st.markdown("### 📤 Export des Données")
    
    if st.button("Générer le rapport complet", type="primary"):
        # Créer un rapport synthétique
        report_data = []
        
        for person in data[name_col].unique()[:100]:  # Limiter pour la performance
            person_reviews = data[data[name_col] == person]
            
            stats = {
                'Personne': person,
                'Nombre_avis': len(person_reviews),
            }
            
            if 'date' in data.columns:
                try:
                    dates = pd.to_datetime(person_reviews['date'])
                    stats['Date_premier'] = dates.min().strftime('%Y-%m-%d') if not pd.isna(dates.min()) else 'N/A'
                    stats['Date_dernier'] = dates.max().strftime('%Y-%m-%d') if not pd.isna(dates.max()) else 'N/A'
                except:
                    stats['Date_premier'] = 'N/A'
                    stats['Date_dernier'] = 'N/A'
            
            if 'sentiment' in data.columns:
                sentiments = person_reviews['sentiment'].value_counts()
                stats['Avis_positifs'] = sentiments.get('positif', 0)
                stats['Avis_negatifs'] = sentiments.get('négatif', 0)
                stats['Avis_neutres'] = sentiments.get('neutre', 0)
            
            if 'faux_avis' in data.columns:
                stats['Faux_avis'] = person_reviews['faux_avis'].sum()
                stats['Statut'] = 'Suspect' if stats['Faux_avis'] > 0 else 'Normal'
            
            report_data.append(stats)
        
        report_df = pd.DataFrame(report_data)
        
        # Trier par nombre d'avis
        report_df = report_df.sort_values('Nombre_avis', ascending=False)
        
        st.dataframe(report_df, use_container_width=True, height=400)
        
        # Téléchargement
        csv = report_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger le rapport complet",
            data=csv,
            file_name=f"rapport_personnes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            type="primary"
        )