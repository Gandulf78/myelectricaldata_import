import __main__ as app
from datetime import datetime

import markdown
from jinja2 import Template
from mergedeep import Strategy, merge
from models.config import get_version
from templates.models.configuration import Configuration
from templates.models.datatable import Datatable
from templates.models.menu import Menu
from templates.models.sidemenu import SideMenu
from templates.models.usage_point_select import UsagePointSelect


class UsagePointId:

    def __init__(self, usage_point_id):
        self.db = app.DB
        self.application_path = app.APPLICATION_PATH
        self.usage_point_id = usage_point_id
        self.current_years = int(datetime.now().strftime("%Y"))
        self.max_history = 4
        self.max_history_chart = 6
        if self.usage_point_id is not None:
            self.config = self.db.get_usage_point(self.usage_point_id)
            self.headers = {
                'Content-Type': 'application/json',
                'Authorization': self.config.token,
                'call-service': "myelectricaldata",
                'version': get_version()
            }
        self.usage_point_select = UsagePointSelect(usage_point_id)
        self.side_menu = SideMenu()
        menu = {}
        menu = merge(
            {
                "import_data": {
                    "title": "Importer les données depuis Enedis",
                    "icon": "file_download",
                    "css": "background-color: var(--sde-bg-color);",
                    "ajax": {
                        "method": "GET",
                        "url": f'/import/{self.usage_point_id}'
                    },
                }
            },
            menu,
            strategy=Strategy.ADDITIVE)
        if hasattr(self.config, "consumption") and self.config.consumption:
            menu = merge(
                {
                    "import_daily": {
                        "title": "Importer la consommation journaliére",
                        "icon": "electric_bolt",
                        "css": "background-color: var(--text-color);",
                        "ajax": {
                            "method": "GET",
                            "url": f'/import/{self.usage_point_id}/consumption'
                        }
                    }
                },
                menu,
                strategy=Strategy.ADDITIVE)
        if hasattr(self.config, "production") and self.config.production:
            menu = merge(
                {
                    "import_production_daily": {
                        "title": "Importer la production journaliére",
                        "icon": "solar_power",
                        "css": "background-color: #F1C40F;",
                        "ajax": {
                            "method": "GET",
                            "url": f'/import/{self.usage_point_id}/production'
                        }
                    }
                },
                menu,
                strategy=Strategy.ADDITIVE)
        if hasattr(self.config, "consumption_detail") and self.config.consumption_detail:
            menu = merge(
                {
                    "import_detail": {
                        "title": "Importer la consommation détaillé",
                        "icon": "electric_bolt",
                        "css": "background-color: var(--text-color);",
                        "ajax": {
                            "method": "GET",
                            "url": f'/import/{self.usage_point_id}/consumption_detail'
                        }
                    }
                },
                menu,
                strategy=Strategy.ADDITIVE)
        if hasattr(self.config, "production_detail") and self.config.production_detail:
            menu = merge(
                {
                    "import_production_detail": {
                        "title": "Importer la production détaillé",
                        "icon": "solar_power",
                        "css": "background-color: #F1C40F;",
                        "ajax": {
                            "method": "GET",
                            "url": f'/import/{self.usage_point_id}/production_detail'
                        }
                    }
                },
                menu,
                strategy=Strategy.ADDITIVE)
        menu = merge(
            {
                "delete_data": {
                    "title": "Supprimer le cache",
                    "icon": "delete",
                    "css": "background-color: var(--text-warning);",
                    "ajax": {
                        "method": "GET",
                        "url": f'/reset/{self.usage_point_id}'
                    },
                },
                "config_data": {
                    "title": "Configuration",
                    "css": "background-color: var(--success-bg);",
                    "icon": "settings_applications"
                }
            },
            menu,
            strategy=Strategy.ADDITIVE)
        self.menu = Menu(menu)
        self.configuration_div = Configuration(f"Modification du point de livraison {self.usage_point_id}",
                                               self.usage_point_id)
        self.contract = self.db.get_contract(self.usage_point_id)
        self.address = self.db.get_addresse(self.usage_point_id)
        self.javascript = ""
        self.recap_consumption_data = {}
        self.recap_production_data = {}
        self.recap_hc_hp = "Pas de donnée."
        self.comsumption_datatable = "Pas de donnée."
        self.production_datatable = "Pas de donnée."

    def display(self):

        address = self.get_address()
        if address is None:
            address = "Inconnue"
        if hasattr(self.config, "name"):
            title = f"{self.usage_point_id} - {self.config.name}"
        else:
            title = address

        with open(f'{self.application_path}/templates/md/usage_point_id.md') as file_:
            homepage_template = Template(file_.read())
        body = homepage_template.render(
            title=title,
            address=address,
            contract_data=self.contract_data(),
            address_data=address,
        )
        body = markdown.markdown(body, extensions=['fenced_code', 'codehilite'])
        body += self.offpeak_hours_table()

        self.consumption()
        self.production()

        body += "<h1>Récapitulatif</h1>"
        # RECAP CONSUMPTION
        if hasattr(self.config, "consumption") and self.config.consumption:
            recap_consumption = self.recap(data=self.recap_consumption_data)
            body += f"<h2>Consommation</h2>"
            body += str(recap_consumption)
            body += '<div id="chart_daily_consumption"></div>'

        # RATIO HP/HC
        if hasattr(self.config, "consumption_detail") and self.config.consumption_detail:
            self.generate_chart_hc_hp(data=self.db.get_detail_all(self.usage_point_id))
            body += "<h2>Ratio HC/HP</h2>"
            body += "<table class='table_hchp'><tr>"
            body += str(self.recap_hc_hp)
            body += "</tr></table>"

        # RECAP PRODUCTION
        if hasattr(self.config, "production") and self.config.production:
            recap_production = self.recap(data=self.recap_production_data)
            body += f"<h2>Production</h2>"
            body += str(recap_production)
            body += '<div id="chart_daily_production"></div>'

        # RECAP CONSUMPTION VS PRODUCTION
        if (
                hasattr(self.config, "consumption") and self.config.consumption and
                hasattr(self.config, "production") and self.config.production
        ):
            body += "<h2>Consommation VS Production</h2>"
            body += f'<div>{self.consumption_vs_production()}</div>'
            body += '<div id="chart_daily_production_compare"></div>'

        body += "<h1>Mes données journalières</h1>"
        # CONSUMPTION DATATABLE
        if hasattr(self.config, "consumption") and self.config.consumption and self.comsumption_datatable:
            body += f"<h2>Consommation</h2>"
            body += str(self.comsumption_datatable)

        # PRODUCTION DATATABLE
        if hasattr(self.config, "production") and self.config.production and self.production_datatable:
            body += f"<h2>Production</h2>"
            body += str(self.production_datatable)

        with open(f'{self.application_path}/templates/html/usage_point_id.html') as file_:
            index_template = Template(file_.read())
        html = index_template.render(
            select_usage_points=self.usage_point_select.html(),
            javascript_loader=open(f'{self.application_path}/templates/html/head.html').read(),
            body=body,
            side_menu=self.side_menu.html(),
            javascript=(
                    self.configuration_div.javascript()
                    + self.side_menu.javascript()
                    + self.usage_point_select.javascript()
                    + self.menu.javascript()
                    + open(f'{self.application_path}/templates/js/notif.js').read()
                    + open(f'{self.application_path}/templates/js/gateway_status.js').read()
                    + open(f'{self.application_path}/templates/js/datatable.js').read()
                    + self.javascript
            ),
            configuration=self.configuration_div.html().strip(),
            menu=self.menu.html(),
            css=self.menu.css()
        )
        return html

    def contract_data(self):
        contract_data = {}
        if self.contract is not None:
            contract_data = {
                "usage_point_status": self.contract.usage_point_status,
                "meter_type": self.contract.meter_type,
                "segment": self.contract.segment,
                "subscribed_power": self.contract.subscribed_power,
                "last_activation_date": self.contract.last_activation_date,
                "distribution_tariff": self.contract.distribution_tariff,
                "contract_status": self.contract.contract_status,
                "last_distribution_tariff_change_date": self.contract.last_distribution_tariff_change_date,
            }
        return contract_data

    def offpeak_hours_table(self):

        def split(data):
            result = ""
            if data is not None:
                for idx, coh in enumerate(data.split(";")):
                    result += f"{coh}"
                    if idx + 1 < len(data.split(";")):
                        result += "<br>"
            return result

        offpeak_hours = """
        <table class='table_offpeak_hours'>
            <tr>
                <th>Lundi</th>
                <th>Mardi</th>
                <th>Mercredi</th>
                <th>Jeudi</th>
                <th>Vendredi</th>
                <th>Samedi</th>
                <th>Dimanche</th>
            </tr>
            <tr>"""
        day = 0
        while day <= 6:
            week_day = f"offpeak_hours_{day}"
            if (
                    hasattr(self.contract, week_day) and getattr(self.contract, week_day) != ""
                    and hasattr(self.config, week_day) and getattr(self.config, week_day) != ""
            ):
                contract_offpeak_hours = split(getattr(self.contract, week_day))
                config_offpeak_hours = split(getattr(self.config, week_day))
                if getattr(self.config, week_day) != getattr(self.contract, week_day):
                    offpeak_hours += f"<td><i style='text-decoration:line-through;'>{contract_offpeak_hours}</i><br>{config_offpeak_hours}</td>"
                else:
                    offpeak_hours += f"<td>{contract_offpeak_hours}</td>"
            else:
                offpeak_hours += f"<td>Pas de donnée.</td>"
            day = day + 1
        offpeak_hours += "</tr></table>"
        return offpeak_hours

    def get_address(self):
        if self.address is not None:
            return (f"{self.address.street}, "
                    f"{self.address.postal_code} "
                    f"{self.address.city}")
        else:
            return None

    def consumption(self):
        if hasattr(self.config, "consumption") and self.config.consumption:
            daily_result = Datatable(self.usage_point_id).html(
                title="Consommation",
                tag="consumption",
                daily_data=self.db.get_daily_all(self.usage_point_id, "consumption"),
                cache_last_date=self.db.get_daily_last_date(self.usage_point_id, "consumption")
            )
            if daily_result['recap']:
                self.recap_consumption_data = daily_result["recap"]
                self.comsumption_datatable = daily_result["html"]
                self.javascript += """            
                google.charts.load("current", {packages:["corechart"]});
                google.charts.setOnLoadCallback(drawChartConsumption);
                function drawChartConsumption() {
                    var data = google.visualization.arrayToDataTable([
                """
                format_table = {}
                years_array = ""
                max_history = self.current_years - self.max_history_chart
                for years, data in self.recap_consumption_data.items():
                    if years > str(max_history):
                        years_array += f"'{years}', "
                        for month, value in data['month'].items():
                            if month not in format_table:
                                format_table[month] = []
                            format_table[month].append(value)
                self.javascript += f"['Month', {years_array}],"
                for month, val in format_table.items():
                    table_value = ""
                    for idx, c in enumerate(val):
                        table_value += str(c / 1000)
                        if idx + 1 < len(val):
                            table_value += ", "
                    self.javascript += f"['{month}', {table_value}],"
                self.javascript += """]);
                            var options = {
                              title : '',
                              vAxis: {title: 'Consommation (kWh)'},
                              hAxis: {title: 'Mois'},
                              seriesType: 'bars',
                              series: {5: {type: 'line'}}
                            };
    
                            var chart = new google.visualization.ComboChart(document.getElementById('chart_daily_consumption'));
                            chart.draw(data, options);
                        }
                            """

    def production(self):
        if hasattr(self.config, "production") and self.config.production:
            daily_result = Datatable(self.usage_point_id).html(
                title="Production",
                tag="production",
                daily_data=self.db.get_daily_all(self.usage_point_id, "production"),
                cache_last_date=self.db.get_daily_last_date(self.usage_point_id, "production")
            )
            if daily_result['recap']:
                self.recap_production_data = daily_result["recap"]
                self.production_datatable = daily_result["html"]
                self.javascript += """            
                google.charts.load("current", {packages:["corechart"]});
                google.charts.setOnLoadCallback(drawChartProduction);
                function drawChartProduction() {
                    var data = google.visualization.arrayToDataTable([
                """
                format_table = {}
                years_array = ""
                max_history = self.current_years - self.max_history_chart
                for years, data in self.recap_production_data.items():
                    if years > str(max_history):
                        years_array += f"'{years}', "
                        for month, value in data['month'].items():
                            if month not in format_table:
                                format_table[month] = []
                            format_table[month].append(value)
                self.javascript += f"['Month', {years_array}],"
                for month, val in format_table.items():
                    table_value = ""
                    for idx, c in enumerate(val):
                        table_value += str(c / 1000)
                        if idx + 1 < len(val):
                            table_value += ", "
                    self.javascript += f"['{month}', {table_value}],"
                self.javascript += """]);
                                var options = {
                                  title : 'Production journalière',
                                  vAxis: {title: 'Consommation (kWh)'},
                                  hAxis: {title: 'Mois'},
                                  seriesType: 'bars',
                                  series: {5: {type: 'line'}}
                                };

                                var chart = new google.visualization.ComboChart(document.getElementById('chart_daily_production'));
                                chart.draw(data, options);
                            }
                            """

    def consumption_vs_production(self):
        if (
                self.recap_production_data != {}
                and self.config.production != {}
        ):
            compare_compsuption_production = {}
            max_year = 1
            max_history = self.current_years - max_year
            for years, data in self.recap_consumption_data.items():
                if int(years) > max_history:
                    for month, value in data['month'].items():
                        if month not in compare_compsuption_production:
                            compare_compsuption_production[month] = []
                        compare_compsuption_production[month].append(float(value) / 1000)

            for years, data in self.recap_production_data.items():
                if int(years) >= max_history:
                    for month, value in data['month'].items():
                        if month not in compare_compsuption_production:
                            compare_compsuption_production[month] = []
                        compare_compsuption_production[month].append(float(value) / 1000)

            self.javascript += """            
            google.charts.load("current", {packages:["corechart"]});
            google.charts.setOnLoadCallback(drawChartProductionVsConsumption);
            function drawChartProductionVsConsumption() {
                var data = google.visualization.arrayToDataTable([
                ['Année', 'Consommation', 'Production'],
            """
            for month, data in compare_compsuption_production.items():
                table_value = ""
                for idx, value in enumerate(data):
                    if value == "":
                        value = 0
                    table_value += f"{value}"
                    if idx + 1 < len(data):
                        table_value += ", "
                self.javascript += f"['{month}', {table_value}],"
            self.javascript += """
                ]);
                var options = {
                  title : 'Consommation VS Production',
                  vAxis: {title: 'Consommation (kWh)'},
                  hAxis: {title: 'Mois'},
                  seriesType: 'bars',
                  series: {5: {type: 'line'}}
                };
    
                var chart = new google.visualization.ComboChart(document.getElementById('chart_daily_production_compare'));
                chart.draw(data, options);
            }
            """
        else:
            return "Pas de donnée."

    def generate_chart_hc_hp(self, data):
        recap = {}
        for detail in data:
            year = detail.date.strftime("%Y")
            value = detail.value
            mesure_type = detail.measure_type
            if not year in recap:
                recap[year] = {
                    "HC": 0,
                    "HP": 0,
                }
            recap[year][mesure_type] = recap[year][mesure_type] + value
        for year, data in recap.items():
            if self.recap_hc_hp == "Pas de donnée.":
                self.recap_hc_hp = ""
            self.recap_hc_hp += f'<td class="table_hp_hc_recap" style="width: {100 / len(recap)}%" id="piChart{year}"></td>'
            self.javascript += "google.charts.load('current', {'packages':['corechart']});"
            self.javascript += f"google.charts.setOnLoadCallback(piChart{year});"
            self.javascript += f"function piChart{year}() " + "{"
            self.javascript += "   var data = google.visualization.arrayToDataTable([['Type', 'Valeur'],"
            self.javascript += f"['HC',     {data['HC']}],"
            self.javascript += f"['HP',     {data['HP']}],"
            self.javascript += """
                ]);

                var options = {
                    title: '""" + year + """',
                };"""
            self.javascript += f"var chart = new google.visualization.PieChart(document.getElementById('piChart{year}'));"
            self.javascript += """chart.draw(data, options);
            }"""

    def recap(self, data):
        if data:
            self.current_years = int(datetime.now().strftime("%Y"))
            current_month = int(datetime.now().strftime("%m"))
            max_history = self.current_years - self.max_history
            linear_years = {}
            mount_count = 0
            first_occurance = False
            for linear_year, linear_data in reversed(sorted(data.items())):
                for linear_month, linear_value in reversed(sorted(linear_data["month"].items())):
                    key = f"{current_month}/{self.current_years} => {current_month}/{self.current_years - 1}"
                    if not first_occurance and linear_value != 0:
                        first_occurance = True
                    if first_occurance:
                        if key not in linear_years:
                            linear_years[key] = 0
                        linear_years[key] = linear_years[key] + linear_value
                        mount_count = mount_count + 1
                        if mount_count >= 12:
                            self.current_years = self.current_years - 1
                            mount_count = 0

            body = '<table class="table_recap"><tr>'
            body += '<th class="table_recap_header">Annuel</th>'
            self.current_years = int(datetime.now().strftime("%Y"))
            for year, data in reversed(sorted(data.items())):
                if int(year) > max_history:
                    body += f"""
                <td class="table_recap_data">                    
                    <div class='recap_years_title'>{year}</div>
                    <div class='recap_years_value'>{round(data['value'] / 1000)} kWh</div>
                </td>    
                """
                    self.current_years = self.current_years - 1
            body += "</tr>"
            body += "<tr>"
            body += '<th class="table_recap_header">Annuel linéaire</th>'
            self.current_years = int(datetime.now().strftime("%Y"))
            for year, data in linear_years.items():
                if self.current_years > max_history:
                    data_last_years_class = ""
                    data_last_years = "---"
                    key = f"{current_month}/{self.current_years - 1} => {current_month}/{self.current_years - 2}"
                    if str(key) in linear_years:
                        data_last_years = linear_years[str(key)]
                        data_last_years = 100 - (round((data_last_years / data) * 100))
                        self.current_years = self.current_years - 1
                        if data_last_years >= 0:
                            if data_last_years == 0:
                                data_last_years_class = "blue"
                            else:
                                data_last_years_class = "red"
                                data_last_years = f"+{data_last_years}"
                        else:
                            data_last_years_class = "green"
                    body += f"""
                <td class="table_recap_data">                    
                    <div class='recap_years_title'>{year}</div>
                    <div class='recap_years_value'>{round(data / 1000)} kWh</div>
                    <div class='recap_years_value {data_last_years_class}'><b>{data_last_years}%</b></div>
                </td>                
                """
            body += "</tr>"
            body += "</table>"
        else:
            body = "Pas de donnée."
        return body
