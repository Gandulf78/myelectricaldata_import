import json
from datetime import datetime
from sqlalchemy import Column, String, Date, select, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import requests
import logging

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

# Classe qui gère la base de données Flex
class DatabaseFlex:
    """Classe pour gérer les jours Flex dans la base de données."""

    def __init__(self, engine):
        """Initialisation de la gestion de la base de données."""
        self.engine = engine
        self.session_factory = sessionmaker(bind=self.engine)
        self.session = self.session_factory()
        Base.metadata.create_all(bind=self.engine)  # Crée les tables si elles n'existent pas

    def get_flex_day(self, date):
        """Récupère le statut d'un jour Flex."""
        query = select(FlexDay).where(FlexDay.date == date)
        result = self.session.scalars(query).one_or_none()
        return result.status if result else None

    def set_flex_day(self, date, status):
        """Insère ou met à jour le statut d'un jour Flex."""
        with self.session.begin():
            flex_day = self.session.scalars(select(FlexDay).where(FlexDay.date == date)).one_or_none()
            if flex_day:
                flex_day.status = status
            else:
                flex_day = FlexDay(date=date, status=status)
                self.session.add(flex_day)
            self.session.commit()

    def get_flex_config(self, key):
        """Récupère la valeur d'une clé de configuration Flex."""
        query = select(FlexConfig).where(FlexConfig.key == key)
        config = self.session.scalars(query).one_or_none()
        return json.loads(config.value) if config else None

    def set_flex_config(self, key, value):
        """Définit la valeur d'une clé de configuration Flex."""
        with self.session.begin():
            config = self.session.scalars(select(FlexConfig).where(FlexConfig.key == key)).one_or_none()
            if config:
                config.value = json.dumps(value)
            else:
                config = FlexConfig(key=key, value=json.dumps(value))
                self.session.add(config)
            self.session.commit()

# Classe qui gère les jours Flex via l'API EDF et la base de données locale
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
        # Vérifie si la date est un week-end
        if self.is_weekend(date):
            return "Normal"

        # Vérifie si la date est dans une période de Sobriété
        if not self.is_sobriety_period(date):
            return "Normal"

        # Vérifie le cache
        cached_status = self.db.get_flex_day(date)
        if cached_status:
            return cached_status

        # Appelle l'API EDF si le statut n'est pas en cache
        try:
            response = requests.get(f"{self.API_URL}?dateRelevant={date.strftime('%Y-%m-%d')}")
            response.raise_for_status()  # Vérifie si la réponse est OK (code 200)
            status_code = response.json().get("etat")
        except requests.exceptions.RequestException as e:
            logging.error(f"Erreur lors de l'appel à l'API EDF pour Flex : {e}")
            return None

        # Traduire le statut API en un statut utilisateur
        status_map = {
            "RAS": "Normal",
            "ZENF_PM": "Sobriété",
            "ZENF_BONIF": "Bonus",
        }
        status = status_map.get(status_code, "Inconnu")

        # Stocke dans la base de données
        self.db.set_flex_day(date, status)
        return status

if __name__ == "__main__":
    # Configurez le niveau de log
    logging.basicConfig(level=logging.INFO)

    # Instanciez la gestion de la base Flex
    engine = create_engine("sqlite:///database.db", echo=True)
    db_flex = DatabaseFlex(engine=engine)

    # Instanciez le gestionnaire de jours Flex
    manager = FlexDayManager(db=db_flex)

    # Liste des dates à tester
    test_dates = [
        "2024-11-18",  # Jour en semaine pendant Sobriété
        "2024-07-01",  # Hors période Sobriété
        "2024-11-19",  # Week-end
        "2024-12-25",  # Pendant Sobriété, mais peut-être un jour spécial
        "2024-01-14",  # Sobriété (première période)
        "2024-11-16",  # Samedi
    ]

    # Testez et affichez les résultats
    for date in test_dates:
        status = manager.get_flex_status(date)
        print(f"Statut pour le {date} : {status}")
