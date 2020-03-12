from flask import Flask, request, Response, send_from_directory
from flask import g # global variables
from rcj import Rcj
from flask_httpauth import HTTPBasicAuth
from flask import jsonify
import json
from flask_cors import CORS

from configparser import ConfigParser

# read config file
parser = ConfigParser()
parser.read("rcj_config.ini")

# setup flask
app = Flask(__name__, static_url_path='')
CORS(app,
    supports_credentials=True,
    resources={
        r'/api/*': {
            'origins': ['https://rcjberlin.github.io', 'https://nikolockenvitz.de']
        }
    })

import os

# init the login manager
auth = HTTPBasicAuth()

# send digital scoring sheet
@app.route('/dss/<path:path>')
def send_dss(path):
    return send_from_directory('../rcj-dss', path)

@auth.verify_password
def verify_password(username, password):
    return g.rcj.check_referee_password(username, password)

# https://flask-doc.readthedocs.io/en/latest/patterns/sqlite3.html
@app.before_request
def before_request():
    g.rcj = Rcj(parser.get('db', 'filename'))

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'rcj'):
        del g.rcj

@app.route('/')
@auth.login_required
def root():
    return 'Hello from Flask!'

@app.route('/api/v1/cors_test')
def test():
    return 'ok'

@app.route('/api/v1/login_required')
@auth.login_required
def login_required():
    return 'ok'

@app.route('/api/v1/submit_run', methods=['PUT', 'POST'])
@auth.login_required
def submit_run():
    # check for valid json
    if not request.is_json:
        return 'not json', 400
    try:
        run = request.json
    except ValueError as e:
        return str(e), 400

    # add username and self computed scoring to dictionary
    run['referee'] = auth.username()
    try:
        g.rcj.store_run(run)
    except ValueError as e:
        return "{}: {}".format('ValueError', str(e)), 400
    return 'ok', 200

@app.route('/api/v1/dump_runs', methods=['GET'])
@auth.login_required
def dump_runs():
    return jsonify({'runs': g.rcj.dump_runs()})

@app.route('/api/v1/get_runs', methods=['GET'])
@auth.login_required
def get_runs():
    return jsonify({'runs': g.rcj.get_runs()})

@app.route('/api/v1/get_runs/competition/<string:competition>', methods=['GET'])
@auth.login_required
def get_runs_competition(competition):
    return jsonify({'runs': g.rcj.get_runs_competition(competition)})

def api_v2_check_auth(request):
    username = request['referee']['name']
    password = request['referee']['auth']
    return g.rcj.check_referee_password(username, password)

@app.route('/crud', methods=['GET'])
def crud():
    return send_from_directory('../public', 'crud.html')
@app.route('/crud/main.js', methods=['GET'])
def crud_main_js():
    return send_from_directory('../public', 'main.js')

@app.route('/api/v2/sql', methods=['POST'])
def sql():
    if not request.is_json:
        return jsonify({'error': 'not json'}), 400
    try:
        req = request.json
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    if(not api_v2_check_auth(req)):
        return jsonify({'error': 'Unauthorized'}), 401
    if(req['referee']['name'] not in ["niko", "manuel"]):
        return jsonify({'error': 'Forbidden'}), 403

    sql_statement = req['sqlStatement']
    result = g.rcj.execute_sql_statement(sql_statement)

    # logging?
    # provide schema?
    return jsonify(result)