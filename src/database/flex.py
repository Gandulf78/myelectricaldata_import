import json
from datetime import datetime
from sqlalchemy import Column, String, Date, select
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import IntegrityError
import requests
import logging
from . import DB  # Assurez-vous que DB est correctement importé

# Définir la base pour les modèles SQLAlchemy
Base = declarative_base()

class FlexDay(Base):
    __tablename__ = 'flex_days'
    date = Column(Date, primary_key=True)
    status = Column(String)

class FlexConfig(Base):
    __tablename__ = 'flex_config'
    key = Column(String, primary_key=True)
    value = Column(String)

class DatabaseFlex:
    """Classe pour gérer les jours Flex dans la base de données."""

    def __init__(self):
        """Initialisation de la gestion de la base de données."""
        self.session = DB.session()
        Base.metadata.create_all(bind=self.session.get_bind())  # Crée les tables si elles n'existent pas

    def get_flex_day(self, date):
        """Récupère le statut d'un jour Flex."""
        query = select(FlexDay).where(FlexDay.date == date)
        result = self.session.scalars(query).one_or_none()
        return result.status if result else None

    def set_flex_day(self, date, status):
        """Ajoute ou met à jour le statut Flex pour une date donnée."""
        existing_entry = self.session.query(FlexDay).filter_by(date=date).first()
        if existing_entry:
            # Mettre à jour si l'entrée existe déjà
            existing_entry.status = status
        else:
            # Ajouter une nouvelle entrée si elle n'existe pas
            new_entry = FlexDay(date=date, status=status)
            self.session.add(new_entry)
        try:
            self.session.flush()  # Valider temporairement les changements
        except IntegrityError as e:
            logging.error(f"Erreur d'intégrité lors de l'ajout/mise à jour : {e}")
            self.session.rollback()  # Annuler les modifications si erreur

    def get_flex_config(self, key):
        """Récupère la valeur d'une clé de configuration Flex."""
        query = select(FlexConfig).where(FlexConfig.key == key)
        config = self.session.scalars(query).one_or_none()
        return json.loads(config.value) if config else None

    def set_flex_config(self, key, value):
        """Définit la valeur d'une clé de configuration Flex."""
        query = select(FlexConfig).where(FlexConfig.key == key)
        config = self.session.scalars(query).one_or_none()
        if config:
            config.value = json.dumps(value)
        else:
            self.session.add(FlexConfig(key=key, value=json.dumps(value)))
        self.session.flush()

class FlexDayManager:
    """Classe pour gérer les jours Flex via l'API EDF et une base de données locale."""

    API_URL = "https://particulier.edf.fr/services/rest/opm/getOPMStatut"

    def __init__(self, db: DatabaseFlex):
        self.db = db

    def is_sobriety_period(self, date):
        """Vérifie si une date donnée est dans la période de Sobriété."""
        dt = datetime.strptime(date.strftime("%Y-%m-%d"), "%Y-%m-%d")
        year = dt.year
        sobriety_start_1 = datetime(year, 1, 1)
        sobriety_end_1 = datetime(year, 4, 15)
        sobriety_start_2 = datetime(year, 10, 15)
        sobriety_end_2 = datetime(year, 12, 31)
        return (sobriety_start_1 <= dt <= sobriety_end_1) or (sobriety_start_2 <= dt <= sobriety_end_2)

    def is_weekend(self, date):
        """Vérifie si une date donnée est un week-end."""
        dt = datetime.strptime(date.strftime("%Y-%m-%d"), "%Y-%m-%d")
        return dt.weekday() in [5, 6]  # Samedi = 5, Dimanche = 6

    def get_flex_status(self, date):
          """Récupère le statut Flex pour une date donnée."""
          if self.is_weekend(date):
                  return "Normal"
          if not self.is_sobriety_period(date):
                  return "Normal"
  
          cached_status = self.db.get_flex_day(date)
          if cached_status is not None and cached_status != "":
                  return cached_status
  
          try:
                  response = requests.get(f"{self.API_URL}?dateRelevant={date.strftime('%Y-%m-%d')}")
                  response.raise_for_status()  # Vérifie si la réponse est OK (code 200)
                  status_code = response.json().get("couleurJourJ")
                  if status_code is None:
                          logging.warning(f"L'API n'a pas retourné de 'etat' pour la date {date}")
                          return "Inconnu"
          except requests.exceptions.RequestException as e:
                  logging.error(f"Erreur lors de l'appel à l'API EDF pour Flex : {e}")
                  return None
  
          status_map = {
                  "RAS": "Normal",
                  "ZENF_PM": "Sobriete",
                  "ZENF_BONIF": "Bonus",
          }
          status = status_map.get(status_code, None)
          if status is None:
                  logging.warning(f"Statut API inconnu pour la date {date}: {status_code}")
                  status = "Inconnu"
  
          # Enregistrer le statut dans le cache
          self.db.set_flex_day(date, status)
          logging.info(f"Statut Flex enregistré pour la date {date}: {status}")
          return status
