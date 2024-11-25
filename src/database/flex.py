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

    def get_flex_day(self, dt):
        """Récupère le statut d'un jour Flex."""
        normalized_date = datetime(dt.year, dt.month, dt.day)
        query = select(FlexDay).where(FlexDay.date == normalized_date)
        result = self.session.scalars(query).one_or_none()
        return result.status if result else None

    from datetime import date

    def set_flex_day(self, dt, status):
        """Ajoute ou met à jour le statut Flex pour une date donnée."""
        try:
            with self.session.begin():  # Assurer une transaction
                # Normaliser la date pour ne conserver que la partie 'date'
                normalized_date = datetime(dt.year, dt.month, dt.day)

                logging.info(f"Vérification de l'existence de la date : {normalized_date}")
                existing_entry = self.session.query(FlexDay).filter_by(date=normalized_date).first()

                if existing_entry:
                    logging.info(f"Entrée existante trouvée pour la date {normalized_date}, mise à jour du statut.")
                    existing_entry.status = status  # Mise à jour du statut
                else:
                    logging.info(
                        f"Aucune entrée existante pour la date {normalized_date}, insertion d'une nouvelle entrée.")
                    self.session.add(FlexDay(date=normalized_date, status=status))

                self.session.commit()  # Commit des changements
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
        with self.session.begin():  # Assurer une transaction
            config = self.session.scalars(select(FlexConfig).where(FlexConfig.key == key)).one_or_none()
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

    def is_sobriety_period(self, dt):
        """Vérifie si une date donnée est dans la période de Sobriété."""
        
        year = dt.year
        sobriety_start_1 = datetime(year, 1, 1)
        sobriety_end_1 = datetime(year, 4, 15)
        sobriety_start_2 = datetime(year, 10, 15)
        sobriety_end_2 = datetime(year, 12, 31)
        return (sobriety_start_1 <= dt <= sobriety_end_1) or (sobriety_start_2 <= dt <= sobriety_end_2)

    def is_weekend(self, dt):
        """Vérifie si une date donnée est un week-end."""
        return dt.weekday() in [5, 6]  # Samedi = 5, Dimanche = 6

    def get_flex_status(self, date):
        """Récupère le statut Flex pour une date donnée."""
        dt = datetime.strptime(date, "%Y-%m-%d")
        if self.is_weekend(dt):
            return "Normal"
        if not self.is_sobriety_period(dt):
            return "Normal"

        cached_status = self.db.get_flex_day(dt)
        if cached_status is not None and cached_status != "":
            return cached_status

        try:
            response = requests.get(f"{self.API_URL}?dateRelevant={date}")
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
        self.db.set_flex_day(dt, status)
        logging.info(f"Statut Flex enregistré pour la date {date}: {status}")
        return status
