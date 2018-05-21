#!/usr/bin/env python3

import os, re, sys
from colorama import Fore
from lxml import etree

current_dir = os.path.realpath(os.path.dirname(os.path.realpath(sys.argv[0])))
xml_list    = os.path.join(current_dir, 'list.xml')

if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
  xml_list = sys.argv[1]

parser = etree.XMLParser(recover=True, remove_blank_text=True)
tree = etree.parse(xml_list, parser=parser).getroot()

calibredb = cinfo.get('exec', 'calibredb')
lib_path  = cinfo.get('location', 'Calibre')

#1 unread
#2 read
series        = {}
books_read    = []
books_reading = []
books_unread  = []

command = f'{calibredb} list -f "series,*read" --with-library {lib_path}'
for i in os.popen(command).read().split('\n'):
  match = re.search('^\\d+\\s+(.*?)\\s+(True|False)$', i)
  if not match:
    continue
  if match.group(1) not in series.keys():
    series[match.group(1)] = [0, 0]

  if match.group(2) == 'False':
    series[match.group(1)][1] += 1
  else:
    series[match.group(1)][0] += 1
    series[match.group(1)][1] += 1

for i in series:
  if series[i][0] == 0:
    books_unread.append((i, *series[i]))
  elif series[i][0] == series[i][1]:
    books_read.append((i, *series[i]))
  else:
    books_reading.append((i, *series[i]))

print('{}READ:'.format(Fore.GREEN))
for ser,read,total in books_read:
  print('  {} ({}/{})'.format(ser, read, total))


print('{}READING:'.format(Fore.YELLOW))
for ser in books_reading:
  print('  {} ({}/{})'.format(ser, read, total))

print('{}UNREAD:'.format(Fore.RED))
for ser in books_unread:
  print('  {} ({}/{})'.format(ser, read, total))

print(Fore.RESET)
