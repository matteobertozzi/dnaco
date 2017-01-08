#!/usr/bin/env python3

from collections import deque
from time import time_ns
import math

import humans


class TimeRangeCollector:
  def __init__(self, max_interval, window):
    slots = int(math.ceil(max_interval / window))
    self.counters = [None] * slots
    self.window = window
    self.next = 0
    self._set_last_interval(time_ns())

  def update(self, now, collect):
    delta = now - self.last_interval
    if (delta >= self.window): 
      self.next += 1

      # TODO
      data = collect()
      #self._inject_zeros(now)
      self._set_last_interval(now)
      self.next += 1
      self.counters[self.next % len(self.counters)] = data

  def _set_last_interval(self, now):
    self.last_interval = (now - (now % self.window))

class CollectorGroup:
  def __init__(self):
    self.collectors = {}

  def register(self, collector_info):
    self.collectors[collector_info.name] = collector_info

  def register_hourly(self, collector_info):
    self.collectors[collector_info.name] = collector_info

  def snapshot(self):
    data = {}
    for collector_info in self.collectors.values():
      data[collector_info.name] = collector_info.snapshot()
    return data
    
  def human_report(self):
    buf = []
    for collector_info in self.collectors.values():
      buf.append(collector_info.human_report())
    return '\n'.join(buf)

class CollectorRegistry(CollectorGroup):
  def __init__(self):
    super().__init__()
    self.hourly_collectors = {}
    self.hourly_snapshots = TimeRangeCollector(24 * humans.UNIT_HOUR, 1 * humans.UNIT_HOUR)

  def register_hourly(self, collector_info):
    self.hourly_collectors[collector_info.name] = collector_info

  def update_hourly_snapshots(self, now):
    self.hourly_snapshots.update(now, self._hourly_collect)

  def _hourly_collect(self):
    data = {}
    for collector_info in self.hourly_collectors.values():
      snapshot = collector_info.snapshot()
      human_report = collector_info.human_report()
      collector_info.collector.clear()
      data[collector_info.name] = {'snapshot': snapshot, 'human_report': human_report}
    return data

  def snapshot(self):
    data = super().snapshot()
    hourly_data = {}
    for collector_info in self.hourly_collectors.values():
      hourly_data[collector_info.name] = collector_info.snapshot()
    data['hourly'] = hourly_data
    return data
    
  def human_report(self):
    buf = super().human_report()
    hourly_buf = ['']
    hourly_buf.append('================================================================================')
    hourly_buf.append(' Hourly Data')
    hourly_buf.append('================================================================================')
    hourly_buf.append('')
    for collector_info in self.hourly_collectors.values():
      hourly_buf.append(collector_info.human_report())
    return buf + '\n'.join(hourly_buf)

COLLECTOR_REGISTRY_INSTANCE = CollectorRegistry()


class CollectorHourlyEntry:
  def __init__(self, collector):
    self.collector = collector

  def get(self, now = None):
    COLLECTOR_REGISTRY_INSTANCE.update_hourly_snapshots(now if now else time_ns())
    return self.collector

class Collector:
  def __init__(self, name, label, help, unit, collector):
    self.name = name
    self.label = label
    self.unit = unit
    self.help = help
    self.collector = collector

  def snapshot(self):
    return {
      #'name': self.name,
      'label': self.label,
      'help': self.help,
      'unit': self.unit['name'],
      'type': self.collector.COLLECTOR_TYPE,
      'data': self.collector.snapshot()
    }
  
  def human_report(self):
    buf = []
    buf.append('--- %s (%s) ---' % (self.label, self.name))
    if self.help: buf.append(self.help)
    buf.append(self.collector.human_report(self.unit['converter']))
    buf.append('')
    return '\n'.join(buf)

  @staticmethod
  def register(name, label, unit, collector, help = None):
    collector_info = Collector(name, label, help, unit, collector)
    COLLECTOR_REGISTRY_INSTANCE.register(collector_info)
    return collector

  @staticmethod
  def register_hourly(name, label, unit, collector, help = None):
    collector_info = Collector(name, label, help, unit, collector)
    COLLECTOR_REGISTRY_INSTANCE.register_hourly(collector_info)
    return CollectorHourlyEntry(collector)

# ==========================================================================================
#  TimeRangeCounter
# ==========================================================================================
class TimeRangeCounter:
  COLLECTOR_TYPE = 'TIME_RANGE_COUNTER'

  def __init__(self, max_interval, window):
    slots = int(math.ceil(max_interval / window))
    self.counters = [0] * slots
    self.window = window
    self.next = 0
    self._set_last_interval(time_ns())

  def clear(self):
    for i in range(len(self.counters)):
      self.counters[i] = 0
    self._set_last_interval(time_ns())
    self.next = 0

  def inc(self, now = None):
    self.add(1, now if now else time_ns())

  def add(self, amount = 1, now = None):
    now = now if now else time_ns()
    delta = now - self.last_interval
    if (delta < self.window):
      self.counters[self.next % len(self.counters)] += amount
      return
    
    self._inject_zeros(now)
    self._set_last_interval(now)
    self.next += 1
    self.counters[self.next % len(self.counters)] = amount

  def _set_last_interval(self, now):
    self.last_interval = (now - (now % self.window))

  def _inject_zeros(self, now, keep_prev = False):
    delta = (now - self.last_interval)
    if (delta < self.window): return

    slots = int(delta / self.window) - 1
    if slots > 0:
      value = self.counters[self.next % len(self.counters)] if keep_prev else 0
      for i in range(slots):
        self.next += 1
        self.counters[self.next % len(self.counters)] = value
      self._set_last_interval(now)

  def snapshot(self):
    index = self.next % len(self.counters)
    return {
      'window': self.window,
      'last_interval': self.last_interval,
      'counters': (self.counters[index+1:] + self.counters[:index+1])[-(self.next + 1):]
    }
  
  def human_report(self, human_converter):
    index = self.next % len(self.counters)
    data = (self.counters[index+1:] + self.counters[:index+1])[-(self.next + 1):]
    return 'window %s - %s - [%s] - %s' % (
        humans.human_time_diff_ns(self.window),
        humans.human_date_time_ns(self.last_interval - (self.window * len(data))),
        ','.join(human_converter(v) for v in data),
        humans.human_date_time_ns(self.last_interval)
    )

  def __str__(self):
    return self.human_report()

class MaxAndAvgTimeRangeGauge:
  COLLECTOR_TYPE = 'MAX_AND_AVG_TIME_RANGE_GAUGE'
  
  def __init__(self, max_interval, window):
    slots = int(math.ceil(max_interval / window))
    self.ring_max = [0] * slots
    self.ring_avg = [0] * slots
    self.window = window
    self.count = 0
    self.vmax = 0
    self.vsum = 0
    self.next = 0
    self._set_last_interval(time_ns())

  def clear(self):
    for i in range(len(self.ring_max)):
      self.ring_max[i] = 0
      self.ring_avg[i] = 0
    self.count = 0
    #self.vmax = 0
    #self.vsum = 0
    self.next = 0
    self._set_last_interval(time_ns())

  def _set_last_interval(self, now):
    self.last_interval = (now - (now % self.window))
  
  def update(self, value, now = None):
    self.set_value(now if now else time_ns(), value)
  
  def set_value(self, now, value):
    delta = now - self.last_interval
    if (delta < self.window):
      self.vmax = max(value, self.vmax)
      self.vsum += value
      self.count += 1
      return
    
    self._inject_zeros(now)
    self._set_last_interval(now)
    self._save_snapshot()

  def _save_snapshot(self, next_inc = 1):
    self.next += next_inc
    index = (self.next % len(self.ring_avg))
    avg = (self.vsum // self.count) if self.count > 0 else 0
    self.ring_avg[index] = avg
    self.ring_max[index] = self.vmax
    self.count = 1
    self.vsum = avg
    self.vmax = avg
  
  def _inject_zeros(self, now, keep_prev = False):
    delta = (now - self.last_interval)
    if (delta < self.window): return

    slots = int(delta / self.window) - 1
    for _ in range(slots):
      self._save_snapshot()

  def snapshot(self):
    self._save_snapshot(0)
    index = self.next % len(self.ring_avg)
    return {
      'events': {
        'avg': (self.ring_avg[index+1:] + self.ring_avg[:index+1])[-(self.next + 1):],
        'max': (self.ring_max[index+1:] + self.ring_max[:index+1])[-(self.next + 1):]
      },
      'slots': len(self.ring_avg),
      'window': self.window,
      'last_interval': self.last_interval
    }

  def human_report(self, human_converter):
    self._save_snapshot(0)
    index = self.next % len(self.ring_avg)
    data_avg = (self.ring_avg[index+1:] + self.ring_avg[:index+1])[-(self.next + 1):]
    data_max = (self.ring_max[index+1:] + self.ring_max[:index+1])[-(self.next + 1):]
    return 'window %s - %s - [%s] - %s' % (
        humans.human_time_diff_ns(self.window),
        humans.human_date_time_ns(self.last_interval - (self.window * len(data_avg))),
        ','.join(human_converter(vavg) + '/' + human_converter(vmax) for vavg, vmax in zip(data_avg, data_max)),
        humans.human_date_time_ns(self.last_interval)
    )


# ==========================================================================================
#  Histogram
# ==========================================================================================
def min_value(bounds, events, max_value):
  for i in range(len(bounds)):
    if events[i] > 0:
      return bounds[i]
  return max_value

def max_value(bounds, events, max_value):
  for i in reversed(range(len(bounds))):
    if events[i] > 0:
      return bounds[i]
  return max_value

def mean(bounds, events, max_value, nevents):
  if nevents == 0: return 0
  xsum = 0
  for i in range(len(bounds)):
    xsum += bounds[i] * events[i]
  if events[-1] > 0:
    xsum += max_value * events[-1]
  return min(max_value, xsum / nevents)

def percentile(bounds, events, max_value, nevents, p):
  if nevents == 0: return 0

  threshold = nevents * (p * 0.01)
  xsum = 0
  i = 0
  while (i < len(bounds)) and (max_value > bounds[i]):
    xsum += events[i]
    if xsum >= threshold:
      # Scale linearly within this bucket
      left_point = bounds[0 if (i == 0) else (i - 1)]
      right_point = bounds[i]
      left_xsum = xsum - events[i]
      right_xsum = xsum
      pos = 0
      right_left_diff = right_xsum - left_xsum
      if right_left_diff != 0:
        pos = (threshold - left_xsum) / right_left_diff
      r = left_point + ((right_point - left_point) * pos)
      return max_value if (r > max_value) else r
    i += 1
  return max_value

class Histogram:
  COLLECTOR_TYPE = 'HISTOGRAM'
  
  DEFAULT_MS_DURATION_BOUNDS = [
    5, 10, 25, 50, 75, 100, 150, 250, 350, 500, 750,  # msec
    1000, 2500, 5000, 10000, 25000, 50000, 60000,     # sec
    75000, 120000,                                    # min
  ]

  DEFAULT_SIZE_BOUNDS = [
    0, 128, 256, 512,
    1 << 10, 2 << 10, 4 << 10, 8 << 10, 16 << 10, 32 << 10, 64 << 10, 128 << 10, 256 << 10, 512 << 10, # kb
    1 << 20, 2 << 20, 4 << 20, 8 << 20, 16 << 20, 32 << 20, 64 << 20, 128 << 20, 256 << 20, 512 << 20, # mb
  ]

  def __init__(self, bounds):
    self.bounds = bounds
    self.events = [0] * (1 + len(bounds))
    self.vmax = 0

  def clear(self):
    for i in range(len(self.events)):
      self.events[i] = 0
    self.vmax = 0

  def add(self, value, num_events = 1):
    index = 0
    bounds = self.bounds
    while (index < len(bounds)) and (value > bounds[index]):
      index += 1
    self.events[index] += num_events
    self.vmax = max(self.vmax, value)

  def snapshot(self):
    return {
      'bounds': self.bounds[:],
      'events': self.events[:],
      'nevents': sum(self.events),
      'max_value': self.vmax
    }

  def human_report(self, human_converter):
    nevents = sum(self.events)
    if nevents == 0: return '(no data)'

    buf = []
    buf.append('Count:%s Min:%s Mean:%s Max:%s' % (
      humans.human_count(nevents),
      human_converter(min_value(self.bounds, self.events, self.vmax)), 
      human_converter(mean(self.bounds, self.events, self.vmax, nevents)),
      human_converter(max_value(self.bounds, self.events, self.vmax))
    ))
    buf.append('Percentiles: P50:%s P75:%s P99:%s P99.9:%s P99.99:%s' % (
      human_converter(percentile(self.bounds, self.events, self.vmax, nevents, 50)),
      human_converter(percentile(self.bounds, self.events, self.vmax, nevents, 75)),
      human_converter(percentile(self.bounds, self.events, self.vmax, nevents, 99)),
      human_converter(percentile(self.bounds, self.events, self.vmax, nevents, 99.9)),
      human_converter(percentile(self.bounds, self.events, self.vmax, nevents, 99.99))
    ))
    buf.append('----------------------------------------------------------------------')

    mult = 100.0 / nevents
    cumulative_sum = 0
    for b in range(len(self.bounds)):
      bucket_value = self.events[b]
      if bucket_value == 0: continue
      cumulative_sum += bucket_value
      marks = int(round(mult * bucket_value / 5 + 0.5))
      buf.append("[%15s, %15s) %7s %7.3f%% %7.3f%% %s" % (
          human_converter(0 if b == 0 else self.bounds[b - 1]), # left
          human_converter(self.bounds[b]),                      # right
          humans.human_count(bucket_value),                     # count
          (mult * bucket_value),                                # percentage
          (mult * cumulative_sum),                              # cumulative percentage
          ('#' * marks)
      ))

    if self.events[-1] > 0:
        cumulative_sum += self.events[-1]
        marks = int(round(mult * bucket_value / 5 + 0.5))
        buf.append("[%15s, %15s) %7s %7.3f%% %7.3f%% %s" % (
            human_converter(self.bounds[-1]),     # left
            human_converter(self.vmax),           # right
            humans.human_count(self.events[-1]),  # count
            (mult * bucket_value),                # percentage
            (mult * cumulative_sum),              # cumulative percentage
            ('#' * marks)
        ))
    return '\n'.join(buf)

# ==========================================================================================
#  TopK
# ==========================================================================================
class TopK:
  COLLECTOR_TYPE = 'TOP_K'
  
  class _Entry:
    def __init__(self, key):
      self.key = key
      self.vmin = None
      self.vmax = None
      self.vmax_ts = None
      self.vsum = 0
      self.freq = 0
      self.trace_ids = deque([], 5)

    def update(self, value, trace_id):
      if self.vmax is None or value >= self.vmax:
        self.trace_ids.append(trace_id)
        self.vmax_ts = time_ns()
        self.vmax = value
      self.vmin = min(value, self.vmin) if self.vmin else value
      self.vsum += value
      self.freq += 1

    def snapshot(self):
      return {
        'key': self.key,
        'max_ts': self.vmax_ts,
        'max': self.vmax,
        'min': self.vmin,
        'avg': (self.vsum // self.freq),
        'freq': self.freq,
        'trace_ids': list(self.trace_ids)
      }

    def human_report(self, human_converter):
      return [
        self.key, humans.human_date_time_ns(self.vmax_ts),
        human_converter(self.vmax), human_converter(self.vmin),
        human_converter((self.vsum // self.freq)), self.freq,
        str(list(self.trace_ids))
      ]

  def __init__(self, k):
    self.data = {}
    self.k = k

  def clear(self):
    self.data = {}

  def add(self, key, value, trace_id = None):
    entry = self.data.get(key)
    if entry is None:
      entry = self._Entry(key)
      self.data[key] = entry
    entry.update(value, trace_id)

    if len(self.data) > (self.k * 2):
      self.data = self._compute(self.k * 2)

  def _compute(self, n):
    data = {}
    entries = sorted(self.data.values(), key = lambda entry: entry.vmax, reverse = True)
    for entry in entries[:n]:
      data[entry.key] = entry
    return data
  
  def snapshot(self):
    data = []
    for entry in self._compute(self.k).values():
      data.append(entry.snapshot())
    return data
  
  def human_report(self, human_converter):
    table = humans.HumansTableView()
    table.add_columns(['', 'Max Timestamp', 'Max', 'Min', 'Avg', 'Freq', 'Trace Ids'])
    for entry in self._compute(self.k).values():
      table.add_row(entry.human_report(human_converter))
    return table.human_view()

# ==========================================================================================
#  CounterMap
# ==========================================================================================
class CounterMap:
  COLLECTOR_TYPE = 'COUNTER_MAP'

  def __init__(self):
    self.data = {}

  def clear(self):
    self.data = {}
  
  def inc(self, key, amount = 1):
    count = self.data.get(key, 0)
    self.data[key] = count + 1

  def snapshot(self):
    return self.data
  
  def human_report(self, human_converter):
    buf = []
    total = sum(self.data.values())
    for key, value in sorted(self.data.items(), key = lambda x: x[1], reverse = True):
      buf.append(' - %5.2f%% (%7s) - %s' % (
        (100 * (value / total)),
        human_converter(value),
        key
      ))
    return '\n'.join(buf)
