"""Import data in statistique recorder of Home Assistant."""
import inspect
import json
import logging
import ssl
import time
import traceback
import websocket
import calendar

from datetime import datetime, timedelta

from config.main import APP_CONFIG
from config.myelectricaldata import UsagePointId
from const import TEMPO_BEGIN, TIMEZONE, URL_CONFIG_FILE
from database.config import DatabaseConfig
from database.detail import DatabaseDetail
from database.tempo import DatabaseTempo
from database.flex import DatabaseFlex, FlexDayManager
from database.usage_points import DatabaseUsagePoints
from models.stat import Stat
from utils import chunks_list

class HomeAssistantWs:
    """Class to interact with Home Assistant WebSocket API."""

    def __init__(self, usage_point_id):
        """Initialize the class with the usage point id.

        Args:
            usage_point_id (str): The usage point id
        """
        self.websocket = None
        self.usage_point_id = usage_point_id
        self.usage_point_id_config: UsagePointId = APP_CONFIG.myelectricaldata.usage_point_config[self.usage_point_id]
        self.id = 1
        self.purge_force = False
        self.current_stats = []
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
        if self.connect():
            self.import_data()
        else:
            logging.critical("La configuration Home Assistant WebSocket est erronée")
        if self.websocket and self.websocket.connected:
            self.websocket.close()

    def connect(self):
        """Connect to the Home Assistant WebSocket server.

        Returns:
            bool: True if the connection is successful, False otherwise
        """
        with APP_CONFIG.tracer.start_as_current_span(f"{__name__}.{inspect.currentframe().f_code.co_name}"):
            try:
                prefix = "ws"
                sslopt = None
                if APP_CONFIG.home_assistant_ws.ssl:
                    sslopt = {"cert_reqs": ssl.CERT_NONE}
                    prefix = "wss"
                self.uri = f"{prefix}://{APP_CONFIG.home_assistant_ws.url}/api/websocket"
                
                # Enable ping/pong to keep connection alive
                self.websocket = websocket.WebSocket(sslopt=sslopt)
                self.websocket.ping_interval = 30
                self.websocket.ping_timeout = 10
                
                logging.info("Connexion au WebSocket Home Assistant %s", self.uri)
                self.websocket.connect(self.uri, timeout=5)
                output = json.loads(self.websocket.recv())
                if "type" in output and output["type"] == "auth_required":
                    logging.info("Authentification requise")
                    return self.authentificate()
                return True
            except Exception as e:
                if self.websocket:
                    self.websocket.close()
                logging.error(
                    f"""
    Impossible de se connecter au WebSocket Home Assistant: {str(e)}

    Vous pouvez récupérer un exemple ici :
{URL_CONFIG_FILE}
"""
                )
                return False

    def ensure_connection(self):
        """Ensure the WebSocket connection is active, attempt to reconnect if not.
        
        Returns:
            bool: True if connection is active or successfully reconnected
        """
        if not self.websocket or not self.websocket.connected:
            for attempt in range(self.max_retries):
                logging.warning(f"Tentative de reconnexion ({attempt + 1}/{self.max_retries})...")
                if self.connect() and self.authentificate():
                    return True
                time.sleep(self.retry_delay)
            return False
        return True

    def authentificate(self):
        """Authenticate with the Home Assistant WebSocket server.

        Returns:
            bool: True if the authentication is successful, False otherwise
        """
        with APP_CONFIG.tracer.start_as_current_span(f"{__name__}.{inspect.currentframe().f_code.co_name}"):
            data = {"type": "auth", "access_token": APP_CONFIG.home_assistant_ws.token}
            auth_output = self.send(data)
            if auth_output["type"] == "auth_ok":
                logging.info(" => OK")
                return True
            logging.error(" => Authentification impossible, merci de vérifier votre url & token.")
            return False

    def send(self, data):
        """Send data to the Home Assistant WebSocket server.

        Args:
            data (dict): The data to send
        Returns:
            dict: The output from the server
        """
        with APP_CONFIG.tracer.start_as_current_span(f"{__name__}.{inspect.currentframe().f_code.co_name}"):
            if not self.ensure_connection():
                raise ConnectionError("Impossible de maintenir la connexion WebSocket")
            
            try:
                self.websocket.send(json.dumps(data))
                self.id = self.id + 1
                output = json.loads(self.websocket.recv())
                if "type" in output and output["type"] == "result":
                    if not output["success"]:
                        logging.error(f"Erreur d'envoi : {data}")
                        logging.error(output)
                return output
            except (websocket.WebSocketConnectionClosedException, ConnectionError) as e:
                logging.error(f"Erreur de connexion lors de l'envoi: {str(e)}")
                if self.ensure_connection():
                    return self.send(data)  # Retry once if reconnection successful
                raise

    def list_data(self):
        """List the data already cached in Home Assistant.

        Returns:
            dict: The list of data
        """
        with APP_CONFIG.tracer.start_as_current_span(f"{__name__}.{inspect.currentframe().f_code.co_name}"):
            logging.info("Liste les données déjà en cache.")
            import_statistics = {
                "id": self.id,
                "type": "recorder/list_statistic_ids",
                "statistic_type": "sum",
            }
            current_stats = self.send(import_statistics)
            for stats in current_stats["result"]:
                if stats["statistic_id"].startswith("myelectricaldata:"):
                    self.current_stats.append(stats["statistic_id"])
            return current_stats

    def clear_data(self, statistic_ids):
        """Clear the data imported into Energy.

        Args:
            statistic_ids (list): The list of statistic ids
        Returns:
            dict: The output from clearing the data
        """
        with APP_CONFIG.tracer.start_as_current_span(f"{__name__}.{inspect.currentframe().f_code.co_name}"):
            logging.info("Effacement des données importées dans Energy.")
            for key in statistic_ids:
                logging.info(f" - {key}")
            clear_statistics = {
                "id": self.id,
                "type": "recorder/clear_statistics",
                "statistic_ids": statistic_ids,
            }
            for data in self.current_stats:
                logging.info(f" - {data}")
            clear_stat = self.send(clear_statistics)
            return clear_stat

    def get_data(self, statistic_ids, begin: datetime, end: datetime):
        """Get the data for a given period.

        Args:
            statistic_ids (list): The list of statistic ids
            begin (datetime): The start of the period
            end (datetime): The end of the period
        Returns:
            dict: The data for the period
        """
        with APP_CONFIG.tracer.start_as_current_span(f"{__name__}.{inspect.currentframe().f_code.co_name}"):
            statistics_during_period = {
                "id": self.id,
                "type": "recorder/statistics_during_period",
                "start_time": begin.isoformat(),
                "end_time": end.isoformat(),
                "statistic_ids": [statistic_ids],
                "period": "hour",
            }
            stat_period = self.send(statistics_during_period)
            return stat_period

    def import_data(self):  # noqa: C901, PLR0915
        """Import the data for the usage point into Home Assistant."""
        # Check and parse tariff_change_date
        if hasattr(self.usage_point_id_config, "tariff_change_date") and self.usage_point_id_config.tariff_change_date:
            try:
                tariff_change_date = datetime.strptime(self.usage_point_id_config.tariff_change_date, "%Y-%m-%d")
            except ValueError as e:
                logging.error(f"Invalid date format for tariff_change_date: {self.usage_point_id_config.tariff_change_date}. Error: {e}")
                tariff_change_date = None
        else:
            tariff_change_date = None

        with APP_CONFIG.tracer.start_as_current_span(f"{__name__}.{inspect.currentframe().f_code.co_name}"):
            logging.info(f"Point de livraison : {self.usage_point_id}")
            try:
                plan = DatabaseUsagePoints(self.usage_point_id).get_plan()
                if self.usage_point_id_config.consumption_detail:
                    logging.info(" => Préparation des données de consommation...")
                    measurement_direction = "consumption"
                    max_date = APP_CONFIG.home_assistant_ws.max_date
                    if max_date is not None:
                        logging.warning("Max date détectée %s", max_date)
                        begin = datetime.strptime(max_date, "%Y-%m-%d").replace(tzinfo=TIMEZONE)
                        detail = DatabaseDetail(self.usage_point_id).get_all(begin=begin, order_dir="desc")
                    else:
                        detail = DatabaseDetail(self.usage_point_id).get_all(order_dir="desc")

                    cost = 0
                    last_year = None
                    last_month = None

                    stats_kwh = {}
                    stats_euro = {}

                    db_tempo_price = DatabaseTempo().get_config("price")
                    tempo_color_ref = {}
                    for tempo_data in DatabaseTempo().get():
                        tempo_color_ref[tempo_data.date] = tempo_data.color

                    stats = Stat(usage_point_id=self.usage_point_id, measurement_direction="consumption")
                    strdate = ""
                    day_flex = "Inconnu"

                    first_time_slot = None
                    daily_charge = 0

                    for data in detail:
                        year = int(f'{data.date.strftime("%Y")}')
                        if last_year is None or year != last_year:
                            logging.info(f"  - {year} :")
                        month = int(f'{data.date.strftime("%m")}')
                        if last_month is None or month != last_month:
                            logging.info(f"    * {month}")
                        day = int(f'{data.date.strftime("%d")}')    
                        last_year = year
                        last_month = month
                        hour_minute = int(f'{data.date.strftime("%H")}{data.date.strftime("%M")}')

                        # Check if it's the first time slot of the day
                        if first_time_slot is None or (year, month, day) != (last_year, last_month, last_day):
                            first_time_slot = data
                            last_day =  day
                        # Calculate daily charge based on the first time slot
                        if data == first_time_slot:
                            num_days_in_month = calendar.monthrange(year, month)[1]
                            daily_charge = self.usage_point_id_config.monthly_charge / num_days_in_month
                        else:
                            daily_charge = 0

                        name = f"MyElectricalData - {self.usage_point_id}"
                        statistic_id = f"myelectricaldata:{self.usage_point_id}"
                        day_interval = data.interval if hasattr(data, "interval") and data.interval != 0 else 1
                        value = data.value / (60 / day_interval)                     
                        
                        tag = None
                        if plan == "BASE":
                            name = f"{name} {plan} {measurement_direction}"
                            statistic_id = f"{statistic_id}_{plan.lower()}_{measurement_direction}"
                            cost = value * self.usage_point_id_config.consumption_price_base / 1000
                            tag = "base"
                        elif plan == "HC/HP":
                            measure_type = stats.get_mesure_type(data.date)
                            if measure_type == "HC":
                                name = f"{name} HC {measurement_direction}"
                                statistic_id = f"{statistic_id}_hc_{measurement_direction}"
                                cost = value * self.usage_point_id_config.consumption_price_hc / 1000
                                tag = "hc"
                            else:
                                name = f"{name} HP {measurement_direction}"
                                statistic_id = f"{statistic_id}_hp_{measurement_direction}"
                                cost = value * self.usage_point_id_config.consumption_price_hp / 1000
                                tag = "hp"
                        elif plan.upper() == "TEMPO" :
                            hour_type = stats.get_mesure_type(data.date)
                            max_time = 2359
                            if TEMPO_BEGIN <= hour_minute <= max_time:
                                date = datetime.combine(data.date, datetime.min.time())
                            else:
                                date = datetime.combine(data.date - timedelta(days=1), datetime.min.time())

                            if date not in tempo_color_ref:
                                logging.error(f"Import impossible, pas de donnée tempo sur la date du {data.date}")
                            else:                   
                                day_color = tempo_color_ref[date]
                                tempo_color = f"{day_color}{hour_type}"
                                tempo_color_price_key = f"{day_color.lower()}_{hour_type.lower()}"
                                tempo_price = float(db_tempo_price[tempo_color_price_key])
                                cost = value / 1000 * tempo_price
                                name = f"{name} {tempo_color} {measurement_direction}"
                                statistic_id = f"{statistic_id}_{tempo_color.lower()}_{measurement_direction}"
                                tag = tempo_color.lower()                        
                        elif plan.upper() == "FLEX" :
                            # Check if we should use BASE tariff based on date
                            tariff_change_date = datetime.strptime(self.usage_point_id_config.tariff_change_date, "%Y-%m-%d") if hasattr(self.usage_point_id_config, "tariff_change_date") else None

                            if tariff_change_date and data.date < tariff_change_date:
                                # Use BASE tariff pricing with normal_HP for all consumption
                                flex_hour = "normal_HP"
                                cost = value * self.usage_point_id_config.consumption_price_base / 1000
                                name = f"{name} {flex_hour} {measurement_direction}"
                                statistic_id = f"{statistic_id}_{flex_hour.lower()}_{measurement_direction}"
                                tag = flex_hour.lower()
                            else:
                                # Use FLEX tariff logic
                                # Récupérer le statut Flex
                                db_flex = DatabaseFlex()  # Utilise la session de DB par défaut
                                flex_manager = FlexDayManager(db_flex)
                                hour_type = stats.get_mesure_type(data.date)
                                newstrdate = data.date.strftime("%Y-%m-%d")

                                if newstrdate != strdate:
                                    strdate = newstrdate
                                    day_flex = flex_manager.get_flex_status(strdate)

                                if day_flex == "Inconnu":
                                  if hour_type == "HC":
                                    flex_hour = "normal_HC"
                                    cost = value * self.usage_point_id_config.consumption_price_hc / 1000
                                  elif hour_type == "HP":
                                    flex_hour = "normal_HP"
                                    cost = value * self.usage_point_id_config.consumption_price_hp / 1000

                                  name = f"{name} {flex_hour} {measurement_direction}"
                                  statistic_id = f"{statistic_id}_{flex_hour.lower()}_{measurement_direction}"
                                  tag = flex_hour.lower()

                                else:
                                  flex_hour = f"{day_flex.lower()}_{hour_type}"
                                  name = f"{name} {flex_hour} {measurement_direction}"
                                  statistic_id = f"{statistic_id}_{flex_hour.lower()}_{measurement_direction}"
                                  tag = flex_hour.lower()
                                                      
                                  if flex_hour == "normal_HC":
                                    cost = value * self.usage_point_id_config.consumption_price_flex_normal_hc / 1000
                                  elif flex_hour == "normal_HP":
                                    cost = value * self.usage_point_id_config.consumption_price_flex_normal_hp / 1000    
                                  elif flex_hour == "sobriete_HC":
                                    cost = value * self.usage_point_id_config.consumption_price_flex_sobriete_hc / 1000
                                  elif flex_hour == "sobriete_HP":
                                    cost = value * self.usage_point_id_config.consumption_price_flex_sobriete_hp / 1000                           
                                  elif flex_hour == "bonus_HC":
                                    cost = value * self.usage_point_id_config.consumption_price_flex_bonus_hc / 1000                           
                                  elif flex_hour == "bonus_HP":
                                    cost = value * self.usage_point_id_config.consumption_price_flex_bonus_hp / 1000     
                                  else:
                                    cost = 0.0                                                                                
                        else:
                            logging.error(f"Plan {plan} inconnu.")

                        date = TIMEZONE.localize(data.date, "%Y-%m-%d %H:%M:%S")
                        date = date.replace(minute=0, second=0, microsecond=0)
                        key = date.strftime("%Y-%m-%d %H:%M:%S")

                        # KWH
                        if statistic_id not in stats_kwh:
                            stats_kwh[statistic_id] = {"name": name, "sum": 0, "data": {}}
                        if key not in stats_kwh[statistic_id]["data"]:
                            stats_kwh[statistic_id]["data"][key] = {
                                "start": date.isoformat(),
                                "state": 0,
                                "sum": 0,
                            }
                        value = value / 1000
                        stats_kwh[statistic_id]["data"][key]["state"] = (
                            stats_kwh[statistic_id]["data"][key]["state"] + value
                        )
                        stats_kwh[statistic_id]["tag"] = tag
                        stats_kwh[statistic_id]["sum"] += value
                        stats_kwh[statistic_id]["data"][key]["sum"] = stats_kwh[statistic_id]["sum"]

                        # EURO
                        statistic_id = f"{statistic_id}_cost"
                        if statistic_id not in stats_euro:
                            stats_euro[statistic_id] = {
                                "name": f"{name} Cost",
                                "sum": 0,
                                "data": {},
                            }
                        if key not in stats_euro[statistic_id]["data"]:
                            stats_euro[statistic_id]["data"][key] = {
                                "start": date.isoformat(),
                                "state": 0,
                                "sum": 0,
                            }
                        # Add charge to cost
                        cost += daily_charge
                        stats_euro[statistic_id]["tag"] = tag
                        stats_euro[statistic_id]["data"][key]["state"] += cost
                        stats_euro[statistic_id]["sum"] += cost
                        stats_euro[statistic_id]["data"][key]["sum"] = stats_euro[statistic_id]["sum"]

                    # CLEAN OLD DATA
                    if APP_CONFIG.home_assistant_ws.purge or self.purge_force:
                        logging.info(f"Clean old data import In Home Assistant Recorder {self.usage_point_id}")
                        list_statistic_ids = []
                        for statistic_id, _ in stats_kwh.items():
                            list_statistic_ids.append(statistic_id)
                        self.clear_data(list_statistic_ids)
                        APP_CONFIG.home_assistant_ws.purge = False
                        DatabaseConfig().set("purge", False)

                    logging.info(" => Envoie des données...")
                    logging.info(" - Consommation :")
                    for statistic_id, data in stats_kwh.items():
                        metadata = {
                            "has_mean": False,
                            "has_sum": True,
                            "name": data["name"],
                            "source": "myelectricaldata",
                            "statistic_id": statistic_id,
                            "unit_of_measurement": "kWh",
                        }
                        chunks = list(
                            chunks_list(list(data["data"].values()), APP_CONFIG.home_assistant_ws.batch_size)
                        )
                        chunks_len = len(chunks)
                        for i, chunk in enumerate(chunks):
                            current_plan = data["tag"].upper()
                            logging.info(
                                "   * %s : %s => %s (%s/%s) ",
                                current_plan,
                                chunk[-1]["start"],
                                chunk[0]["start"],
                                i + 1,
                                chunks_len,
                            )
                            self.send(
                                {
                                    "id": self.id,
                                    "type": "recorder/import_statistics",
                                    "metadata": metadata,
                                    "stats": chunk,
                                }
                            )

                    logging.info(" - Coût :")
                    for statistic_id, data in stats_euro.items():
                        metadata = {
                            "has_mean": False,
                            "has_sum": True,
                            "name": data["name"],
                            "source": "myelectricaldata",
                            "statistic_id": statistic_id,
                            "unit_of_measurement": "EURO",
                        }
                        chunks = list(
                            chunks_list(list(data["data"].values()), APP_CONFIG.home_assistant_ws.batch_size)
                        )
                        chunks_len = len(chunks)
                        for i, chunk in enumerate(chunks):
                            current_plan = data["tag"].upper()
                            logging.info(
                                "   * %s : %s => %s (%s/%s) ",
                                current_plan,
                                chunk[-1]["start"],
                                chunk[0]["start"],
                                i + 1,
                                chunks_len,
                            )
                            self.send(
                                {
                                    "id": self.id,
                                    "type": "recorder/import_statistics",
                                    "metadata": metadata,
                                    "stats": list(chunk),
                                }
                            )

                if self.usage_point_id_config.production_detail:
                    logging.info(" => Préparation des données de production...")
                    measurement_direction = "production"
                    max_date = APP_CONFIG.home_assistant_ws.max_date
                    if max_date is not None:
                        logging.warning("Max date détectée %s", max_date)
                        begin = datetime.strptime(max_date, "%Y-%m-%d").replace(tzinfo=TIMEZONE)
                        detail = DatabaseDetail(self.usage_point_id, "production")
                        detail = detail.get_all(begin=begin, order_dir="desc")
                    else:
                        detail = DatabaseDetail(self.usage_point_id, "production").get_all(order_dir="desc")

                    cost = 0
                    last_year = None
                    last_month = None

                    stats_kwh = {}
                    stats_euro = {}
                    for data in detail:
                        year = int(f'{data.date.strftime("%Y")}')
                        if last_year is None or year != last_year:
                            logging.info(f"{year} :")
                        month = int(f'{data.date.strftime("%m")}')
                        if last_month is None or month != last_month:
                            logging.info(f"- {month}")
                        last_year = year
                        last_month = month
                        hour_minute = int(f'{data.date.strftime("%H")}{data.date.strftime("%M")}')
                        name = f"MyElectricalData - {self.usage_point_id} {measurement_direction}"
                        statistic_id = f"myelectricaldata:{self.usage_point_id}_{measurement_direction}"
                        day_interval = data.interval if hasattr(data, "interval") and data.interval != 0 else 1
                        value = data.value / (60 / day_interval)
                        cost = value * self.usage_point_id_config.production_price / 1000
                        date = TIMEZONE.localize(data.date, "%Y-%m-%d %H:%M:%S")
                        date = date.replace(minute=0, second=0, microsecond=0)
                        key = date.strftime("%Y-%m-%d %H:%M:%S")

                        # KWH
                        if statistic_id not in stats_kwh:
                            stats_kwh[statistic_id] = {"name": name, "sum": 0, "data": {}}
                        if key not in stats_kwh[statistic_id]["data"]:
                            stats_kwh[statistic_id]["data"][key] = {
                                "start": date.isoformat(),
                                "state": 0,
                                "sum": 0,
                            }
                        value = value / 1000
                        stats_kwh[statistic_id]["data"][key]["state"] = (
                            stats_kwh[statistic_id]["data"][key]["state"] + value
                        )
                        stats_kwh[statistic_id]["sum"] += value
                        stats_kwh[statistic_id]["data"][key]["sum"] = stats_kwh[statistic_id]["sum"]

                        # EURO
                        statistic_id = f"{statistic_id}_revenue"
                        if statistic_id not in stats_euro:
                            stats_euro[statistic_id] = {
                                "name": f"{name} Revenue",
                                "sum": 0,
                                "data": {},
                            }
                        if key not in stats_euro[statistic_id]["data"]:
                            stats_euro[statistic_id]["data"][key] = {
                                "start": date.isoformat(),
                                "state": 0,
                                "sum": 0,
                            }
                        stats_euro[statistic_id]["data"][key]["state"] += cost
                        stats_euro[statistic_id]["sum"] += cost
                        stats_euro[statistic_id]["data"][key]["sum"] = stats_euro[statistic_id]["sum"]

                    if APP_CONFIG.home_assistant_ws.purge or self.purge_force:
                        list_statistic_ids = []
                        for statistic_id, _ in stats_kwh.items():
                            list_statistic_ids.append(statistic_id)
                        self.clear_data(list_statistic_ids)
                        APP_CONFIG.home_assistant_ws.purge = False
                        DatabaseConfig().set("purge", False)

                    logging.info(" => Envoie des données de production...")

                    for statistic_id, data in stats_kwh.items():
                        metadata = {
                            "has_mean": False,
                            "has_sum": True,
                            "name": data["name"],
                            "source": "myelectricaldata",
                            "statistic_id": statistic_id,
                            "unit_of_measurement": "kWh",
                        }
                        import_statistics = {
                            "id": self.id,
                            "type": "recorder/import_statistics",
                            "metadata": metadata,
                            "stats": list(data["data"].values()),
                        }
                        self.send(import_statistics)

                    for statistic_id, data in stats_euro.items():
                        metadata = {
                            "has_mean": False,
                            "has_sum": True,
                            "name": data["name"],
                            "source": "myelectricaldata",
                            "statistic_id": statistic_id,
                            "unit_of_measurement": "EURO",
                        }
                        import_statistics = {
                            "id": self.id,
                            "type": "recorder/import_statistics",
                            "metadata": metadata,
                            "stats": list(data["data"].values()),
                        }
                        self.send(import_statistics)

            except Exception as _e:
                self.websocket.close()
                traceback.print_exc()
                logging.error(_e)
                logging.critical("Erreur lors de l'export des données vers Home Assistant")
