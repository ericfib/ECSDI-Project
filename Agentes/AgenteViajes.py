# -*- coding: utf-8 -*-

from multiprocessing import Process, Queue
import socket

from AgentUtil.ACLMessages import get_agent_info, send_message, build_message, get_message_properties, register_agent
from rdflib import Namespace, Graph, Literal, URIRef, RDF, XSD
from flask import Flask, request, render_template

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent

__author__ = 'arnau'

# Configuration stuff
from AgentUtil.OntoNamespaces import ACL, ECSDI

hostname = socket.gethostname()
port = 9000

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgenteViaje = Agent('AgenteViaje',
                       agn.AgenteViaje,
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


def get_activities(g, peticion_plan):
    g = Graph()
    return g


def get_hotels(g, peticion_plan):
    ag_hoteles = get_agent_info(agn.PlannerAgent, DirectoryAgent, AgenteViaje, get_count())
    gresp = send_message(build_message(g, perf=ACL.request, sender=AgenteViaje.uri, receiver=ag_hoteles.uri,
                                       msgcnt=get_count(),
                                       content=peticion_plan), ag_hoteles.address)
    return gresp


def get_flights(g, peticion_plan):
    ag_flights = get_agent_info(agn.PlannerAgent, DirectoryAgent, AgenteViaje, get_count())
    gresp = send_message(build_message(g, perf=ACL.request, sender=AgenteViaje.uri, receiver=ag_flights.uri,
                                       msgcnt=get_count(),
                                       content=peticion_plan), ag_flights.address)
    return gresp


def add_to_graph(g, ontology, dato, ontology_dato):
    g.add((ontology_dato, RDF.type, ECSDI.ciudad))
    g.add((ontology_dato, ECSDI.nombre, Literal(dato, datatype=XSD.string)))
    g.add((ontology, ECSDI.tiene_como_origen, URIRef(ontology_dato)))
    return g


def create_peticion_de_plan_graph(origin, destination, dep_date, ret_date, flight_min_price, flight_max_price,
                                  cultural, ludic, festivity, aloj_min_price, aloj_max_price, peticion_plan, n):
    g = Graph()

    ciudad_origen = ECSDI['ciudad' + str(n)]
    g = add_to_graph(g, peticion_plan, origin, ciudad_origen)
    ciudad_destino = ECSDI['ciudad' + str(n)]
    g = add_to_graph(g, peticion_plan, destination, ciudad_destino)
    data_inicio = ECSDI['fecha_inicial' + str(n)]
    g = add_to_graph(g, peticion_plan, dep_date, data_inicio)
    data_fin = ECSDI['fecha_final' + str(n)]
    g = add_to_graph(g, peticion_plan, ret_date, data_fin)
    ludica = ECSDI['porcentaje_actividad_ludica' + str(n)]
    g = add_to_graph(g, peticion_plan, ludic, ludica)
    cultura = ECSDI['porcentaje_actividad_cultural' + str(n)]
    g = add_to_graph(g, peticion_plan, cultural, cultura)
    festiva = ECSDI['porcentaje_actividad_festiva' + str(n)]
    g = add_to_graph(g, peticion_plan, festivity, festiva)
    r_al_max = ECSDI['rango_precio_alojamiento_max' + str(n)]
    g = add_to_graph(g, peticion_plan, flight_max_price, r_al_max)
    r_al_min = ECSDI['rango_precio_alojamiento_min' + str(n)]
    g = add_to_graph(g, peticion_plan, flight_min_price, r_al_min)
    r_fl_max = ECSDI['rango_precio_vuelo_max' + str(n)]
    g = add_to_graph(g, peticion_plan, aloj_max_price, r_fl_max)
    r_fl_min = ECSDI['rango_precio_vuelo_min' + str(n)]
    g = add_to_graph(g, peticion_plan, aloj_min_price, r_fl_min)

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

        n = get_count()
        peticion_plan = ECSDI['peticion_de_plan' + str(n)]
        g = create_peticion_de_plan_graph(origin, destination, dep_date, ret_date, flight_min_price, flight_max_price,
                                          cultural, ludic, festivity, hotel_min_price, hotel_max_price, peticion_plan, n)
        activities = get_activities(g, peticion_plan)
        hotels = get_hotels(g, peticion_plan)
        flights = get_flights(g, peticion_plan)

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


def get_count():
    global mss_cnt
    if not mss_cnt:
        mss_cnt = 0
    mss_cnt += 1
    return mss_cnt


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
