import os
import random
import string
import json
import traceback
import psycopg2.extras
from psycopg2.extras import execute_values
from flask import Flask, render_template, url_for, request, jsonify, Blueprint, current_app, redirect, make_response
from flask_login import login_user, logout_user, login_required, current_user
from app.db.db import get_db_connection, release_db_connection
from werkzeug.utils import secure_filename
from PIL import Image
from datetime import datetime, timedelta
from weasyprint import HTML

shared = Blueprint('shared', __name__, url_prefix='/')

# Rote to our home page
@shared.route('/')
def home():
    return render_template('/shared/home.html', user = current_user)

