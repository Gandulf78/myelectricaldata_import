import __main__ as app

from datetime import datetime
from dateutil.relativedelta import relativedelta

class ExportMqtt:

    def __init__(self, usage_point_id, mesure_type="consumption"):
        self.usage_point_id = usage_point_id
        self.mesure_type = mesure_type
        self.date_format = "%Y-%m-%d"

    def load_daily_data(self, begin, end, price, sub_prefix):
        app.LOG.log(f" {begin.strftime(self.date_format)} => {end.strftime(self.date_format)}")
        prefix = f"{sub_prefix}"
        app.MQTT.publish_multiple({
            f"dateBegin": begin.strftime(self.date_format),
            f"dateEnded": end.strftime(self.date_format)
        }, prefix)
        # DATA FORMATTING
        this_year_watt = 0
        this_year_euro = 0
        this_year_begin = ""
        this_year_end = ""
        this_month_watt = 0
        this_month_euro = 0
        this_month_begin = ""
        this_month_end = ""
        month_watt = {}
        month_euro = {}
        month_begin = {}
        month_end = {}
        week_watt = {}
        week_euro = {}
        week_begin = ""
        week_end = ""
        week_idx = 0
        current_month_year = ""
        current_this_month_year = ""

        for data in app.DB.get_daily_range(self.usage_point_id, begin, end, self.mesure_type):
            date = data.date
            watt = data.value
            kwatt = data.value / 1000
            euro = kwatt * price
            this_year_begin = date
            if this_year_end == "":
                this_year_end = date
            this_year_watt = this_year_watt + watt
            this_year_euro = this_year_euro + euro

            if current_month_year == "":
                current_month_year = date.strftime("%Y")
            if date.strftime("%Y") == current_month_year:
                if date.strftime('%m') not in month_watt:
                    month_watt[date.strftime('%m')] = watt
                    month_euro[date.strftime('%m')] = euro
                    month_end[date.strftime('%m')] = date
                else:
                    month_watt[date.strftime('%m')] = month_watt[date.strftime('%m')] + watt
                    month_euro[date.strftime('%m')] = month_euro[date.strftime('%m')] + euro
                    month_begin[date.strftime('%m')] = date

            if week_idx < 7:
                week_begin = date
                if week_end == "":
                    week_end = date
                if date not in week_watt:
                    week_watt[date] = watt
                    week_euro[date] = euro
                else:
                    week_watt[date] = week_watt[date] + watt
                    week_euro[date] = week_euro[date] + euro

            if current_this_month_year == "":
                current_this_month_year = date.strftime("%Y")
            if (
                    date.strftime("%m") == datetime.now().strftime("%m")
                    and date.strftime("%Y") == current_this_month_year
            ):
                this_month_begin = date
                if this_month_end == "":
                    this_month_end = date
                this_month_watt = this_month_watt + watt
                this_month_euro = this_month_euro + euro
            week_idx = week_idx + 1
        # MQTT FORMATTING
        mqtt_data = {
            f"thisYear/dateBegin": this_year_begin.strftime(self.date_format),
            f"thisYear/dateEnd": this_year_end.strftime(self.date_format),
            f"thisYear/base/Wh": this_year_watt,
            f"thisYear/base/kWh": round(this_year_watt / 1000, 2),
            f"thisYear/base/euro": round(this_year_euro, 2),
            f"thisMonth/dateBegin": this_month_begin.strftime(self.date_format),
            f"thisMonth/dateEnd": this_month_end.strftime(self.date_format),
            f"thisMonth/base/Wh": this_month_watt,
            f"thisMonth/base/kWh": round(this_month_watt / 1000, 2),
            f"thisMonth/base/euro": round(this_month_euro, 2),
            f"thisWeek/dateBegin": week_begin.strftime(self.date_format),
            f"thisWeek/dateEnd": week_end.strftime(self.date_format),
        }
        for date, watt in month_watt.items():
            mqtt_data[f"months/{date}/base/Wh"] = watt
            mqtt_data[f"months/{date}/base/kWh"] = round(watt / 1000, 2)
        for date, euro in month_euro.items():
            mqtt_data[f"months/{date}/base/euro"] = round(euro, 2)
        for date, value in month_begin.items():
            mqtt_data[f"months/{date}/dateBegin"] = value.strftime(self.date_format)
        for date, value in month_end.items():
            mqtt_data[f"months/{date}/dateEnd"] = value.strftime(self.date_format)

        for date, watt in week_watt.items():
            mqtt_data[f"thisWeek/{date.strftime('%A')}/date"] = date.strftime(self.date_format)
            mqtt_data[f"thisWeek/{date.strftime('%A')}/base/Wh"] = watt
            mqtt_data[f"thisWeek/{date.strftime('%A')}/base/kWh"] = round(watt / 1000, 2)
        for date, euro in week_euro.items():
            mqtt_data[f"thisWeek/{date.strftime('%A')}/base/euro"] = round(euro, 2)

        # SEND TO MQTT
        app.MQTT.publish_multiple(mqtt_data, prefix)

    def daily_annual(self, price):
        app.LOG.log("Génération des données annuelles")
        date_range = app.DB.get_daily_date_range(self.usage_point_id)
        date_begin = datetime.combine(date_range["begin"], datetime.min.time())
        date_end = datetime.combine(date_range["end"], datetime.max.time())
        date_begin_current = datetime.combine(date_end.replace(month=1).replace(day=1),
                                                       datetime.min.time())
        finish = False
        while not finish:
            sub_prefix = f"/{self.usage_point_id}/{self.mesure_type}/annual/{date_begin_current.strftime('%Y')}"
            self.load_daily_data(date_begin_current, date_end, price, sub_prefix)
            # CALCUL NEW DATE
            if date_begin_current == date_begin:
                finish = True
            date_end = datetime.combine(
                (date_end - relativedelta(years=1)).replace(month=12, day=31), datetime.max.time()
            )
            date_begin_current = date_begin_current - relativedelta(years=1)
            if date_begin_current < date_begin:
                date_begin_current = date_begin
        app.LOG.log(" => Finish")

    def daily_linear(self, price):
        app.LOG.log("Génération des données linéaires")
        date_range = app.DB.get_daily_date_range(self.usage_point_id)
        date_begin = datetime.combine(date_range["begin"], datetime.min.time())
        date_end = datetime.combine(date_range["end"], datetime.max.time())
        date_begin_current = date_end - relativedelta(years=1)
        idx = 0
        finish = False
        while not finish:
            if idx == 0:
                key = "year"
            else:
                key = f"year-{idx}"
            sub_prefix = f"/{self.usage_point_id}/{self.mesure_type}/linear/{key}"
            self.load_daily_data(date_begin_current, date_end, price, sub_prefix)
            # CALCUL NEW DATE
            if date_begin_current == date_begin:
                finish = True
            date_end = datetime.combine(
                (date_end - relativedelta(years=1)), datetime.max.time()
            )
            date_begin_current = date_begin_current - relativedelta(years=1)
            if date_begin_current < date_begin:
                date_begin_current = datetime.combine(date_begin, datetime.min.time())
            idx = idx + 1
        app.LOG.log(" => Finish")

    def load_detail_data(self, begin, end, price_hp, price_hc, sub_prefix):
        app.LOG.log(f" {begin.strftime(self.date_format)} => {end.strftime(self.date_format)}")
        prefix = f"{sub_prefix}"
        # DATA FORMATTING
        week_idx = 0
        current_month_year = ""
        current_this_month_year = ""
        output = {
            "hp": {
                "this_year_watt": 0,
                "this_year_euro": 0,
                "month_watt": {},
                "month_euro": {},
                "week_watt": {},
                "week_euro": {},
                "this_month_watt": 0,
                "this_month_euro": 0
            },
            "hc": {
                "this_year_watt": 0,
                "this_year_euro": 0,
                "month_watt": {},
                "month_euro": {},
                "week_watt": {},
                "week_euro": {},
                "this_month_watt": 0,
                "this_month_euro": 0
            }
        }

        for data in app.DB.get_detail_range(self.usage_point_id, begin, end, self.mesure_type):
            date = data.date
            watt = data.value / (60 / data.interval)
            kwatt = watt / 1000

            measure_type = data.measure_type.lower()
            output[measure_type]["this_year_watt"] = output[measure_type]["this_year_watt"] + watt
            if measure_type == "hp":
                euro = kwatt * price_hp
            else:
                euro = kwatt * price_hc
            output[measure_type]["this_year_euro"] = output[measure_type]["this_year_euro"] + euro

            if current_month_year == "":
                current_month_year = date.strftime("%Y")
            if date.strftime("%Y") == current_month_year:
                if date.strftime('%m') not in output[measure_type]["month_watt"]:
                    output[measure_type]["month_watt"][date.strftime('%m')] = watt
                    output[measure_type]["month_euro"][date.strftime('%m')] = euro
                else:
                    output[measure_type]["month_watt"][date.strftime('%m')] = \
                        output[measure_type]["month_watt"][date.strftime('%m')] + watt
                    output[measure_type]["month_euro"][date.strftime('%m')] = \
                        output[measure_type]["month_euro"][date.strftime('%m')] + euro

            if week_idx < 7:
                if date not in output[measure_type]["week_watt"]:
                    output[measure_type]["week_watt"][date] = watt
                    output[measure_type]["week_euro"][date] = euro
                else:
                    output[measure_type]["week_watt"][date] = output[measure_type]["week_watt"][date] + watt
                    output[measure_type]["week_euro"][date] = output[measure_type]["week_euro"][date] + euro

            if current_this_month_year == "":
                current_this_month_year = date.strftime("%Y")
            if date.strftime("%m") == datetime.now().strftime("%m") and date.strftime("%Y") == current_this_month_year:
                output[measure_type]["this_month_watt"] = output[measure_type]["this_month_watt"] + watt
                output[measure_type]["this_month_euro"] = output[measure_type]["this_month_euro"] + euro
            week_idx = week_idx + 1
        # MQTT FORMATTING
        for measure_type, data in output.items():
            mqtt_data = {
                f"thisYear/{measure_type}/Wh": output[measure_type]["this_year_watt"],
                f"thisYear/{measure_type}/kWh": round(output[measure_type]["this_year_watt"] / 1000, 2),
                f"thisYear/{measure_type}/euro": round(output[measure_type]["this_year_euro"], 2),
                f"thisMonth/{measure_type}/Wh": output[measure_type]["this_month_watt"],
                f"thisMonth/{measure_type}/kWh": round(output[measure_type]["this_month_watt"] / 1000, 2),
                f"thisMonth/{measure_type}/euro": round(output[measure_type]["this_month_euro"], 2),
            }
            for date, watt in output[measure_type]["month_watt"].items():
                mqtt_data[f"months/{date}/{measure_type}/Wh"] = watt
                mqtt_data[f"months/{date}/{measure_type}/kWh"] = round(watt / 1000, 2)
            for date, euro in output[measure_type]["month_euro"].items():
                mqtt_data[f"months/{date}/{measure_type}/euro"] = round(euro, 2)

            for date, watt in output[measure_type]["week_watt"].items():
                mqtt_data[f"thisWeek/{date.strftime('%A')}/{measure_type}/Wh"] = watt
                mqtt_data[f"thisWeek/{date.strftime('%A')}/{measure_type}/kWh"] = round(watt / 1000, 2)
            for date, euro in output[measure_type]["week_euro"].items():
                mqtt_data[f"thisWeek/{date.strftime('%A')}/{measure_type}/euro"] = round(euro, 2)

            # SEND TO MQTT
            app.MQTT.publish_multiple(mqtt_data, prefix)

    def detail_annual(self, price_hp, price_hc):
        app.LOG.log("Génération des données annuelles détaillées")
        date_range = app.DB.get_detail_date_range(self.usage_point_id)
        date_begin = datetime.combine(date_range["begin"], datetime.min.time())
        date_end = datetime.combine(date_range["end"], datetime.max.time())
        date_begin_current = datetime.combine(date_end.replace(month=1).replace(day=1),
                                                       datetime.min.time())
        finish = False
        while not finish:
            sub_prefix = f"/{self.usage_point_id}/{self.mesure_type}/annual/{date_begin_current.strftime('%Y')}"
            self.load_detail_data(date_begin_current, date_end, price_hp, price_hc, sub_prefix)
            # CALCUL NEW DATE
            if date_begin_current == date_begin:
                finish = True
            date_end = datetime.combine(
                (date_end - relativedelta(years=1)).replace(month=12, day=31), datetime.max.time()
            )
            date_begin_current = date_begin_current - relativedelta(years=1)
            if date_begin_current < date_begin:
                date_begin_current = date_begin
        app.LOG.log(" => Finish")

    def detail_linear(self, price_hp, price_hc):
        app.LOG.log("Génération des données linéaires détaillées")
        date_range = app.DB.get_detail_date_range(self.usage_point_id)
        date_begin = datetime.combine(date_range["begin"], datetime.min.time())
        date_end = datetime.combine(date_range["end"], datetime.max.time())
        date_begin_current = date_end - relativedelta(years=1)
        idx = 0
        finish = False
        while not finish:
            if idx == 0:
                key = "year"
            else:
                key = f"year-{idx}"
            sub_prefix = f"/{self.usage_point_id}/{self.mesure_type}/linear/{key}"
            self.load_detail_data(date_begin_current, date_end, price_hp, price_hc, sub_prefix)
            # CALCUL NEW DATE
            if date_begin_current == date_begin:
                finish = True
            date_end = datetime.combine(
                (date_end - relativedelta(years=1)), datetime.max.time()
            )
            date_begin_current = date_begin_current - relativedelta(years=1)
            if date_begin_current < date_begin:
                date_begin_current = datetime.combine(date_begin, datetime.min.time())
            idx = idx + 1
        app.LOG.log(" => Finish")