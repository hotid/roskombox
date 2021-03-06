# -*- coding: utf-8 -*-

#------------------------------------------------------------------------------------#
# Этот файл является частью приложения Roskombox, разработанного ООО «Оргтехсервис». #
# https://github.com/orgtechservice/roskombox                                        #
# Предоставляется на условиях GNU GPL v3                                             #
#------------------------------------------------------------------------------------#

# компоненты Django
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.template import RequestContext, loader, Context
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.db import connection

# наш проект
from portal.models import *
from portal.forms import *
from portal.utils import *
import roskombox.tasks as tasks

# django-jsonview
from jsonview.decorators import json_view

@login_required
@require_POST
@json_view
def add_ssh_key(request):
	result = {'method': 'add_ssh_key', 'result': 'ok'}
	key_data = request.POST.get('key_data', '')
	if re_ssh_key.match(key_data) is None:
		result['result'] = 'error'
		result['message'] = 'Неверный формат публичного ключа RSA'
	else:
		if not append_ssh_key(key_data):
			result['result'] = 'error'
			result['message'] = 'append_ssh_key() failed'

	return result

@login_required
@require_POST
@json_view
def del_ssh_key(request):
	result = {'method': 'del_ssh_key', 'result': 'ok'}
	key_name = request.POST.get('key_name', '')
	if not delete_ssh_key(key_name):
		result['result'] = 'error'
		result['message'] = 'delete_ssh_key() failed'

	return result

@login_required
@json_view
def check_updates(request):
	result = {'method': 'check_updates', 'result': 'ok'}

	scan = Scan.objects.filter(state = 'new').first()
	if scan is not None:
		result['scan_progress'] = int(scan.progress)
		result['scan_id'] = int(scan.id)

	load = Download.objects.filter(state = 'new').first()
	if load is not None:
		result['load_id'] = int(load.id)

	return result

@login_required
@json_view
def perform_load(request):
	result = {'method': 'perform_load', 'result': 'ok'}
	Setting.write('roskom:download_requested', '1')
	tasks.perform_load('web')
	return result

@login_required
@json_view
def perform_scan(request):
	result = {'method': 'perform_scan', 'result': 'ok'}
	Setting.write('roskom:scan_requested', '1')
	tasks.perform_scan('web')
	return result
