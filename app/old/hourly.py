import json
import locale

from datetime import datetime, timedelta
from importlib import import_module
from pprint import pprint

import pytz

main = import_module("main")
f = import_module("function")

locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')
timezone = pytz.timezone('Europe/Paris')


def Hourly(cur, con, client, pdl, pdl_config, last_activation_date=datetime.now(pytz.timezone('Europe/Paris')),
           offpeak_hours=None):
    def forceRound(x, n):
        import decimal
        d = decimal.Decimal(repr(x))
        targetdigit = decimal.Decimal("1e%d" % -n)
        chopped = d.quantize(targetdigit, decimal.ROUND_DOWN)
        return float(chopped)

    ha_autodiscovery_prefix = main.config['home_assistant']['discovery_prefix']

    ha_discovery = {
        pdl: {}
    }

    path = f"enedisgateway/{pdl}_hourly"
    config = {
        "name": f"enedisgateway_{pdl}_hourly",
        "uniq_id": f"enedisgateway.{pdl}.hourly",
        "stat_t": f"{ha_autodiscovery_prefix}/sensor/{path}/state",
        "json_attr_t": f"{ha_autodiscovery_prefix}/sensor/{path}/attributes",
        "unit_of_measurement": "W",
        "device": {
            "identifiers": [f"linky_{pdl}"],
            "name": f"Linky {pdl}",
            "model": "Linky",
            "manufacturer": "Enedis"
        },
    }

    f.publish(client, f"sensor/{path}/config", json.dumps(config), ha_autodiscovery_prefix)

    today = datetime.now(timezone)
    attributes = {
        "numPDL": pdl,
        "lastUpdate": today.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "timeLastCall": today.strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

    today = datetime.now(timezone)
    found = False
    delta = 0
    deltaMax = 7
    notFound = False
    while not found and not notFound:
        yesterday_datetime = today - timedelta(days=1 + delta)
        yesterday = yesterday_datetime.strftime('%Y-%m-%d')
        query = f"SELECT * FROM consumption_detail WHERE pdl = '{pdl}' AND date = (select max(date) from consumption_detail);"
        cur.execute(query)
        query_result = cur.fetchone()
        if query_result != None:
            found = True
        else:
            notFound = True

    if notFound == True:
        f.log(" => No detail data found (skip HA Hourly Sensor)")
    else:

        date_history_datetime = today - timedelta(days=5)
        date_history = date_history_datetime.strftime('%Y-%m-%d')

        query = f"SELECT * FROM consumption_detail WHERE pdl = '{pdl}' AND date BETWEEN '{date_history}' AND '{yesterday}' ORDER BY DATE ASC;"
        cur.execute(query)
        query_result = cur.fetchall()
        attributes[f'hourly'] = []
        attributes['hourly_value'] = []
        for val in query_result:
            date = val[1]
            value = val[2]
            state = val[2]
            attributes[f'hourly'].append(date)
            attributes[f'hourly_value'].append(value)

        f.publish(client, f"sensor/{path}/state", str(state), ha_autodiscovery_prefix)
        f.publish(client, f"sensor/{path}/attributes", json.dumps(attributes), ha_autodiscovery_prefix)

        if not "debug" in main.config:
            debug = False
        else:
            debug = main.config["debug"]
        if debug == True:
            pprint(attributes)

    return ha_discovery
