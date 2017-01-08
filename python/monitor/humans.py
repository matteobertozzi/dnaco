#!/usr/bin/env python3

import datetime

UNIT_NS   = 1
UNIT_MS   = 1000000 * UNIT_NS
UNIT_SEC  = 1000 * UNIT_MS
UNIT_MIN  = 60 * UNIT_SEC
UNIT_HOUR = 60 * UNIT_MIN

def human_time_diff_ms(millis):
  if millis < 1000:
    return '%dms' % millis
  
  hours = millis // (60 * 60 * 1000)
  rem = millis % (60 * 60 * 1000)
  minutes = rem // (60 * 1000)
  rem = rem % (60 * 1000)
  seconds = rem // 1000.0

  if (hours > 0) or (minutes > 0):
    buf = ''
    if hours > 0: buf += '%dhrs, ' % hours
    if minutes > 0: buf += '%dmin, ' % minutes

    if seconds > 0:
      buf += "%.2fsec" % seconds
    else:
      buf = buf[:-2]
    
    if hours > 24:
        return '%s (%.1f days)' % (buf, (hours / 24.0))
    return buf

  if (seconds % 1) != 0:
    return '%.4fsec' % seconds
  return '%.0fsec' % seconds

def human_time_diff_ns(ns):
  if ns < 1000000:
    return '%dns' % ns
  return human_time_diff_ms(ns // 1000000)

def human_date_time_ms(millis):
  return str(datetime.datetime.fromtimestamp(millis / 1000))

def human_date_time_ns(ns):
  return human_date_time_ms(ns / 1000000)

def human_size(size):
  if (size >= (1 << 40)): return "%.2fTiB" % (size / (1 << 40))
  if (size >= (1 << 30)): return "%.2fGiB" % (size / (1 << 30))
  if (size >= (1 << 20)): return "%.2fMiB" % (size / (1 << 20))
  if (size >= (1 << 10)): return "%.2fKiB" % (size / (1 << 10))
  return '%dbytes' if size > 0 else '0'

def human_count(count):
  if count >= 1000000: return "%.2fM" % (count / 1000000)
  if count >= 1000: return "%.2fK" % (count / 1000)
  return '%s' % count

class HumansTableView:
  COLUMN_WRAP_LENGTH = 80

  def __init__(self):
    self.columns = []
    self.rows = []

  def add_column(self, name):
    self.columns.append(name)
  
  def add_columns(self, names):
    self.columns.extend(names)

  def add_row(self, row_values):
    self.rows.append([self._cleanup_column_value(v) for v in row_values])

  def _cleanup_column_value(self, value):
    if value is None: return '(null)'
    return ' '.join(str(value).split())

  def human_view(self):
    buf = []
    columns_length = [self._calc_column_length(i) for i in range(len(self.columns))]
    header_border = ''.join(['+-%s-' % ('-' * col_len) for col_len in columns_length]) + '+'
    
    buf.append(header_border)
    buf.append(self._draw_row(self.columns, columns_length))
    buf.append(header_border)
    for row_values in self.rows:
      buf.append(self._draw_row(row_values, columns_length))
    buf.append(header_border)
    return '\n'.join(buf)

  def _draw_row(self, row_values, columns_length):
    buf = ''
    truncated_columns = []
    has_truncation = False
    for v, col_length in zip(row_values, columns_length):
      buf += '| '
      if col_length < len(v):
        truncated_columns.append(v[col_length:])
        buf += v[:col_length]
        has_truncation = True
      else:
        truncated_columns.append('')
        buf += v + (' ' * (col_length - len(v)))
      buf += ' '
    buf += '|'

    if has_truncation:
      buf += '\n' + self._draw_row(truncated_columns, columns_length)
    return buf

      
  def _calc_column_length(self, index):
    length = len(self.columns[index])
    for row_values in self.rows:
      length = max(length, len(row_values[index]))
    return min(length, self.COLUMN_WRAP_LENGTH)

# ==========================================================================================
#  Human converters
# ==========================================================================================
HUMAN_TIME_NS = {'name': 'time-ns', 'converter': human_time_diff_ns}
HUMAN_TIME_MS = {'name': 'time-ms', 'converter': human_time_diff_ms}
HUMAN_DATE_NS = {'name': 'date-ns', 'converter': human_date_time_ns}
HUMAN_DATE_MS = {'name': 'date-ms', 'converter': human_date_time_ms}
HUMAN_COUNT   = {'name': 'count',   'converter': human_count}
HUMAN_SIZE    = {'name': 'size',    'converter': human_size}
