# -*- coding: utf-8 -*-

# WSGI-файл для развёртывания, развёртывание другими способами не допускается!

# Системные импорты
import os, sys, subprocess

# Компоненты Django
from django.core.management import call_command
from django.conf import settings

using_uwsgi = False

try:
	import uwsgi
	using_uwsgi = True
except:
	print("This application is meant to be run under uWSGI, note that!")

# Django
from django.core.wsgi import get_wsgi_application
from django.db import connection

# Задаём путь к модулю настроек
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "roskombox.settings")

# Наш WSGI callable
application = get_wsgi_application()

if using_uwsgi:
	try:
		from uwsgidecorators import *
	except:
		print("Running under uWSGI, but also need uwsgidecorators module!")
		print("If you are using a virtualenv, you can install the decorators manually:")
		print("pip install uwsgidecorators")
		exit(-1)

	def perform_load(manual = False):
		os.chdir(settings.BASE_DIR)
		uwsgi.lock(0)
		if manual:
			command = ['./manage.py', 'roskom_load']
		else:
			command = ['./manage.py', 'roskom_load', 'auto']
		
		try:
			result = subprocess.check_output(command)
		except:
			pass

		uwsgi.unlock(0)

	def perform_scan(manual = False):
		os.chdir(settings.BASE_DIR)
		uwsgi.lock(0)
		if manual:
			command = ['./manage.py', 'roskom_check']
		else:
			command = ['./manage.py', 'roskom_check', 'auto']
		
		try:
			result = subprocess.check_output(command)
		except:
			pass

		uwsgi.unlock(0)

	@cron(-1, -1, -1, -1, -1, target = 'mule')
	def check_jobs(num):
		cursor = connection.cursor()
		cursor.execute("SELECT value FROM settings WHERE name = \'roskom:download_requested\'")
		rows = cursor.fetchall()
		if len(rows) != 0 and (int(rows[0][0]) == 1):
			cursor.execute("DELETE FROM settings WHERE name = \'roskom:download_requested\'")
			perform_load(True)
		
		cursor.execute("SELECT value FROM settings WHERE name = \'roskom:scan_requested\'")
		rows = cursor.fetchall()
		if len(rows) != 0 and (int(rows[0][0]) == 1):
			cursor.execute("DELETE FROM settings WHERE name = \'roskom:scan_requested\'")
			perform_scan(True)

	@cron(0, -2, -1, -1, -1, target = 'mule') # Каждые 2 часа
	def roskom_load(num):
		print("Running roskom_load")
		perform_load()
		print("roskom_load finished")

	@cron(-10, -1, -1, -1, -1, target = 'mule')
	def roskom_cleanup(num):
		print("Running roskom_cleanup")
		uwsgi.lock(0)
		call_command('roskom_cleanup')
		uwsgi.unlock(0)
		print("roskom_cleanup finished")

	@cron(0, 3, -1, -1, -1, target = 'mule')
	def roskom_check(num):
		print("Running roskom_check")
		perform_scan()
		print("roskom_check finished")

	print("Running under uWSGI, perfect!")