# -*- coding: utf-8 -*-

from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph
from flask import Flask, request, render_template

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent

__author__ = 'arnau'

# Configuration stuff
hostname = socket.gethostname()
port = 9000

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgentePersonal = Agent('AgenteViaje',
                       agn.AgenteSimple,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    global mss_cnt
    pass


def get_activities(city, cultural, ludic, festivity):
    g = Graph()
    return g


def get_hotels(city, min_price, max_price, dep_date, ret_date):
    g = Graph()
    return g


def get_flights(origin, destination, dep_date, ret_date, flight_min_price, flight_max_price):
    g = Graph()
    return g


@app.route("/iface", methods=['GET', 'POST'])
def form():
    if request.method == 'GET':
        return render_template('formulario.html')
    else:
        origin = request.form['corigin']
        destination = request.form['cdestination']
        dep_date = request.form['idate']
        ret_date = request.form['fdate']
        flight_max_price = request.form['fmaxp']
        flight_min_price = request.form['fminp']
        hotel_max_price = request.form['fmaxh']
        hotel_min_price = request.form['fminh']
        cultural = request.form['cact']
        ludic = request.form['lact']
        festivity = request.form['fact']

        activities = get_activities(destination, cultural, ludic, festivity)
        hotels = get_hotels(destination, hotel_min_price, hotel_max_price, dep_date, ret_date)
        flights = get_flights(origin, destination, dep_date, ret_date, flight_min_price, flight_max_price)

        result = activities + hotels + flights

        return render_template('formulario.html')


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def tidyup():
    """
    Acciones previas a parar el agente

    """
    pass


def agentbehavior1(cola):
    """
    Un comportamiento del agente

    :return:
    """
    pass


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
