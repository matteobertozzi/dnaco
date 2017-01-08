#!/usr/bin/env python3

from time import time_ns, sleep

import http.server
import json
import sys

from collector import Collector, COLLECTOR_REGISTRY_INSTANCE, TimeRangeCounter, MaxAndAvgTimeRangeGauge, CounterMap, Histogram, TopK
import humans

class ServerStats:
  trace_id = 0

  server_request_count = Collector.register(
    name = 'server_request_count',
    label = 'Request Count (last 60min)',
    help = 'Request Count divided by minute',
    unit = humans.HUMAN_COUNT,
    collector = TimeRangeCounter(60 * humans.UNIT_MIN, 1 * humans.UNIT_MIN)
  )

  server_execution_avg_max_times = Collector.register(
    name = 'server_execution_avg_max_times',
    label = 'Avg/Max Execution Time over Time',
    help = 'Avg/Max Execution Time divided by minute',
    unit = humans.HUMAN_TIME_MS,
    collector = MaxAndAvgTimeRangeGauge(60 * humans.UNIT_MIN, 1 * humans.UNIT_MIN)
  )

  server_execution_time_histo = Collector.register_hourly(
    name = 'server_execution_time_histo',
    label = 'Execution Time Histo',
    help = 'Histogram of the server requests execution times',
    unit = humans.HUMAN_TIME_MS,
    collector = Histogram(Histogram.DEFAULT_MS_DURATION_BOUNDS)
  )

  server_execution_top_times = Collector.register_hourly(
    name = 'server_execution_top_times',
    label = 'Top 10 Execution Times',
    help = 'Top 10 server requests with the highest execution time',
    unit = humans.HUMAN_TIME_MS,
    collector = TopK(10)
  )

  server_request_types = Collector.register_hourly(
    name = 'server_request_types',
    label = 'Count of Requests by Type',
    unit = humans.HUMAN_COUNT,
    collector = CounterMap()
  )

  def new_trace_id(self):
    self.trace_id += 1
    return self.trace_id

  def add_request(self, path, trace_id, elapsed):
    now = time_ns()
    self.server_request_count.inc(now)
    self.server_execution_avg_max_times.update(elapsed, now)
    
    self.server_execution_time_histo.get(now).add(elapsed)
    self.server_execution_top_times.get(now).add(path, elapsed, trace_id)
    self.server_request_types.get(now).inc(path)

server_stats = ServerStats()

class TestHandler(http.server.BaseHTTPRequestHandler):
  def __init__(self, *args, **kwargs):
    self.trace_id = server_stats.new_trace_id()
    super().__init__(*args, **kwargs)

  def do_GET(self):
    start_time = time_ns()
    try:
      if self.trace_id is None:
        self.trace_id = server_stats.new_trace_id()

      if self.path == '/metrics':
        data = COLLECTOR_REGISTRY_INSTANCE.human_report()
      elif self.path == '/metrics/json':
        data = json.dumps(COLLECTOR_REGISTRY_INSTANCE.snapshot())
      else:
        data = 'test: ' + self.path

      self._do_something_slow()

      #print('headers: %s' % self.headers)
      self.send_response(200)
      self.end_headers()
      self.wfile.write(data.encode())
    finally:
      elapsed = (time_ns() - start_time) // 1000000
      server_stats.add_request(self.path, self.trace_id, elapsed)
      self.trace_id = None

  def log_message(self, format, *args):
    sys.stderr.write("[%x] - %s - [%s] %s\n" % (
      self.trace_id, self.address_string(),
      self.log_date_time_string(),
      format % args)
    )

  def _do_something_slow(self):
    import random
    sleep(random.random() * 0.1)

if __name__ == '__main__':
  PORT = 8000
  with http.server.ThreadingHTTPServer(('0.0.0.0', PORT), TestHandler) as httpd:
      print("http listening on %d (http://localhost:%d)" % (PORT, PORT))
      httpd.serve_forever()

