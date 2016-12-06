# -*- coding: utf-8 -*-

#------------------------------------------------------------------------------------#
# Этот файл является частью приложения Roskombox, разработанного ООО «Оргтехсервис». #
# https://github.com/orgtechservice/roskombox                                        #
# Предоставляется на условиях GNU GPL v3                                             #
#------------------------------------------------------------------------------------#

# Django
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.conf import settings

from portal.models import *
from portal.utils import *

# Python
import resource, time, sys, threading, locale

# Сторонние компоненты
import requests
from lxml import etree

# Отключим ругань на невалидный сертификат
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Время начала работы скрипта
execution_start = time.time()

# Расставим затычки-мьютексы
in_mutex = threading.Lock()
out_mutex = threading.Lock()

# Счётчик обработанных ссылок (для отображения прогресса)
counter = 0

# Массивы необработанных и обработанных данных
in_list = []
out_list = []

# Подстрока для поиска, по умолчанию из конфига
search_substring = settings.ROSKOM_SEARCH_SUBSTRING
request_headers = {
	'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/49.0.2623.108 Chrome/49.0.2623.108 Safari/537.36',
}

# http://stackoverflow.com/questions/22492484/how-do-i-get-the-ip-address-from-a-http-request-using-the-requests-library
try:
	from requests.packages.urllib3.connectionpool import HTTPConnectionPool
except:
	print("Sadly, your version of Requests is too old.")
	sys.exit(-1)

# Новый метод, который мы обезьянним методом воткнём вместо старого
def _make_request(self, conn, method, url, **kwargs):
	response = self._old_make_request(conn, method, url, **kwargs)
	sock = getattr(conn, 'sock', False)
	if sock:
		setattr(response, 'peer', sock.getpeername())
	else:
		setattr(response, 'peer', None)
	return response

# Осуществляем подмену
HTTPConnectionPool._old_make_request = HTTPConnectionPool._make_request
HTTPConnectionPool._make_request = _make_request

# Наш воркер
class Worker(threading.Thread):
	def __init__(self, thread_id, in_data, out_data, scan):
		threading.Thread.__init__(self),
		self.thread_id = thread_id
		self.in_data = in_data
		self.out_data = out_data
		self.timeout = 3
		self.scan = scan
		self.total_count = len(in_data)

	def select_unprocessed(self):
		with in_mutex:
			try:
				result = self.in_data.pop()
			except:
				result = None
			return result

	def report_progress(self, item):
		global counter
		counter += 1
		if ((counter % 100) == 0):
			percents = int((float(counter) / float(self.total_count)) * 100.0)
			self.scan.set_progress(percents)
		
		print(u"(%d of %d) [%s] %s" % (counter, self.total_count, item['status'], item['url'].encode('utf-8')))

	def process_item(self, item):
		global search_substring, request_headers
		try:
			response = requests.get(item['url'], timeout = self.timeout, stream = True, headers = request_headers)
			item['code'] = response.status_code

			content = response.raw.read(100000, decode_content = True).decode('utf-8')

			if search_substring in content:
				item['status'] = 'blocked'
			else:
				peer = response.raw._original_response.peer
				if peer is not None:
					address = peer[0]
					if address.startswith('127') or address.startswith('192.168') or address.startswith('10.10'):
						item['status'] = 'local-ip'
					else:
						item['status'] = 'available'
						item['reply'] = content
				else:
					item['status'] = 'available'
					item['reply'] = content
		except Exception as e:
			item['status'] = 'failure'

		with out_mutex:
			self.report_progress(item)
			self.out_data.append(item)

	def set_timeout(self, new_timeout):
		self.timeout = new_timeout

	def run(self):
		while True:
			item = self.select_unprocessed()
			if item is None:
				break
			else:
				self.process_item(item)

def parse_registry(filename):
	result = []

	with open(filename, 'rb') as file:
		tree = etree.fromstring(file.read())
		
	records = tree.xpath('//content')
	for item in records:
		try:
			try:
				block_type = item.attrib['blockType']
			except:
				block_type = 'default'

			decision = item.xpath('decision')[0]
			urls = item.xpath('url')
			ips = item.xpath('ip')
			domains = item.xpath('domain')
			ip_subnets = item.xpath('ipSubnet')

			if block_type == 'default':
				result += [{'url': url.text, 'status': 'unknown', 'reply': None, 'code': 0} for url in urls]
			elif block_type == 'ip':
				pass # NOT IMPLEMENTED
			elif block_type == 'domain':
				result += [{'url': "http://%s/" % domain.text, 'status': 'unknown', 'reply': None, 'code': 0} for domain in domains]
			else:
				pass # ???
		except:
			continue

	return result

class Command(BaseCommand):
	args = '<"auto">'
	help = 'Check website availability'
	db = None
	client = None
	service = None

	def handle(self, *args, **options):
		global search_substring
		mode = 'manual'
		if(len(args) > 0):
			mode = args[0]
			if mode not in ['auto', 'web']:
				mode = 'manual'

		# Проверим, имеется ли незавершённая проверка
		prev = Scan.objects.filter(state = 'new').first()

		if mode == 'auto':
			scan = Scan.automatic()
		elif mode == 'web':
			scan = Scan.web()
		else:
			scan = Scan.manual()

		if prev is not None:
			scan.set_failed('Предыдущая проверка всё ещё не завершена')
			self.stderr.write('Previous scan is still in progress, please wait for it to finish')
			exit(-1)

		# Разблокируем кнопку, теперь её будет блокировать само наличие проверки
		Setting.write('roskom:scan_requested', '0')

		# Установим локаль
		try:
			locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
		except:
			pass

		# Зададим подстроку, если в БД определена подмена
		new_substring = Setting.read('search_substring', search_substring)
		if new_substring != '':
			search_substring = new_substring

		self.stdout.write("Starting check")
		
		try:
			self.stdout.write("Parsing dump.xml")
			in_list = parse_registry("%s/dump.xml" % settings.ROSKOM_CACHE_ROOT)
			self.stdout.write("Parsing done")
		except:
			scan.set_failed("Не удалось распарсить dump.xml, возможно, не было выгрузок")
			self.stderr.write("Failed to parse RSOC registry!")
			exit(-1)

		# Инициализируем наши рабочие потоки
		threads = {}
		for i in range(int(settings.ROSKOM_THREADS)):
			threads[i] = Worker(i, in_list, out_list, scan)
			threads[i].set_timeout(3)
			threads[i].setDaemon(True)

		# Разветвляемся
		for index, thread in threads.items():
			thread.start()

		# Соединяемся
		try:
			for index, thread in threads.items():
				thread.join()
		except KeyboardInterrupt:
			print('Exitting requested')
			scan.set_failed('Scan cancelled by pressing ctrl-c')
			exit(0)

		# Подсчёт статистики
		total = len(out_list)
		local = sum(1 for i in out_list if i['status'] == 'local-ip')
		unavailable = sum(1 for i in out_list if i['status'] in ['blocked', 'failure'])

		# С доступными ссылками работаем отдельно — их надо не просто сосчитать, а занести в базу
		available_links = [i for i in out_list if i['status'] == 'available']
		with transaction.atomic():
			for link in available_links:
				item = AvailableLink(scan = scan, url = link['url'], code = link['code'], content = link['reply'].encode('utf-8'))
				item.save()

		available = len(available_links)

		# Проверку отмечаем как завершённую
		scan.succeeded(total, available, unavailable, local)

		# Если превышен порог, формируем уведомление
		max_available = int(Setting.read('max_available', '0'))
		if (max_available != 0) and (available >= max_available):
			send_mail_notification('max_available_exceeded', available)

		self.stdout.write("Job done!")
