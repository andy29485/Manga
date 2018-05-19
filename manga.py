#!/usr/bin/env python3

from os.path import expanduser
import xml.etree.cElementTree as ET
from datetime import datetime
from requests import Session
import urllib.request
import urllib.parse
import argparse
import tempfile
import logging
import zipfile
import shutil
import html
import time
import sys
import os
import re

current_dir = os.path.realpath(os.path.dirname(os.path.realpath(sys.argv[0])))

xml_list    = os.path.join(current_dir, 'list.xml')
session     = Session()
session.headers.update({'User-agent': 'Mozilla/5.0'})

if not os.path.exists(os.path.join(current_dir, 'logs')):
  os.mkdir(os.path.join(current_dir, 'logs'))

# logging stuff
logger = logging.getLogger('manga')
logger.setLevel(logging.INFO)
logformat = logging.Formatter(
  '%(asctime)s:%(name)s:%(levelname)s(%(pathname)s:%(lineno)s) - %(message)s'
)
error_log = logging.FileHandler(os.path.join(current_dir, 'logs/error.log'))
error_log.setFormatter(logformat)
error_log.setLevel(logging.ERROR)

fh = logging.FileHandler(os.path.join(current_dir, 'logs/manga.log'))
fh.setFormatter(logformat)
fh.setLevel(logging.DEBUG)

logger.addHandler(error_log)
logger.addHandler(fh)

if os.path.exists(xml_list):
  global tree
  try:
    tree = ET.parse(xml_list)
  except:
    with open(xml_list, 'r') as f: lines = f.readlines()
    lines.insert(1, '<xml>')
    lines.append('</xml>')
    with open(xml_list, 'w') as f: f.write('\n'.join(lines))
    tree = ET.parse(xml_list)

parser = argparse.ArgumentParser()
parser . add_argument('-x', '--list',           default = xml_list,     type=str, help='Path to xml list containing data - default list.xml in directory of this script')
parser . add_argument('-D', '--debug',          action  = 'store_true',           help='log extra info and don\'t remove temp dirs')
parser . add_argument('-v', '--verbose',        action  = 'store_true',           help='Print extra stuff(verbose)')
parser . add_argument('-d', '--dest',           default = '',           type=str, help='Directory to copy files to after download - default nowhere - Only works if url is also specified')
parser . add_argument('-a', '--add-to-calibre', action  = 'store_true',           help='Add book to calibre')
parser . add_argument('-u', '--username',       default = '',           type=str, help='MangaDex username')
parser . add_argument('-p', '--password',       default = '',           type=str, help='MangaDex password')
parser . add_argument('url',  nargs='?',                                type=str, help='Url of page to download - do not combine with -x/--list')
parser . add_argument('chap', nargs='?',                                type=str, help='Chaptes to download - Only works if url is also specified')
args   = parser.parse_args()

#TODO
#Add support for following websites?
#  http://www.mangago.com/
#  http://www.mangaeden.com/
#  http://mangadoom.com/
#
#Allow multiple urls(sites) for same manga?
#
#Creae support for chaper urls - rather than series?

if args.debug:
  logger.setLevel(logging.DEBUG)

if args.verbose:
  sh = logging.StreamHandler()
  sh.setLevel(logging.DEBUG)
  sh.setFormatter(logformat)
  logger.addHandler(sh)

tag_dict = {
  'Slice of Life':  'Nichijou'
}
calibredb_executable = 'calibredb'
lib_path='/mnt/5TB_share/Calibre/Manga/Manga_LN'
lang = 'English'

#My own version of title case
#It's like regular title case but some
#  words such as "the" will not be capitalized
#  (unless they are at the beggining)
def title(string):
  return string.title().replace \
    (' The ' , ' the ' ).replace \
    (' Of '  , ' of '  ).replace \
    (' Is '  , ' is '  ).replace \
    (' In '  , ' in '  ).replace \
    (' For'  , ' for'  ).replace \
    (' On '  , ' on '  ).replace \
    (' If '  , ' if '  ).replace \
    (' Than ', ' than ').replace \
    (' No '  , ' no '  ).replace \
    (' Na '  , ' na '  ).replace \
    (' A '   , ' a '   ).replace \
    (' Nomi ', ' nomi ').replace \
    (' Zo '  , ' zo '  ).replace \
    (' To '  , ' to '  ).replace \
    (' Ga '  , ' ga '  ).replace \
    (' Ni '  , ' ni '  ).replace \
    (' Dxd'  , ' DxD'  ).replace \
    (' Xx'   ,  ' xx'  ).replace \
    (' Xxx'  ,  ' xxx' ).replace \
    ('/'     , '-'     ).strip()

def request(url, set_head=False):
  global session
  r = session.get(url)
  if set_head and 'set-cookie' in r.headers:
    session.headers.update({'cookie':r.headers['set-cookie']})
  return r

def get_html(url, set_head=False):
  h = request(url, set_head=set_head)
  return html.unescape(h.text).replace(
    # '&amp;' , '&' ).replace(
    # '&quot;', '\"').replace(
    # '&lt;'  , '<' ).replace(
    # '&gt;'  , '>' ).replace(
    '\\n'   , '\n').replace(
    '\\t'   , '\t').replace(
    '\\r'   , ''  )

class Element(ET.Element):
  def __init__(self, tag, text=None, tail=None, attrib={}, **extra):
    super().__init__(tag, attrib, **extra)
    if text:
      self.text = text
    if tail:
      self.tail = tail

#Zips directory int a file called zip_file
def zipper(dirName, zip_file):
  zip = zipfile.ZipFile(zip_file, 'w', compression=zipfile.ZIP_DEFLATED)
  root_len = len(os.path.abspath(dirName))
  for root, dirs, files in os.walk(dirName):
    archive_root = os.path.abspath(root)[root_len:]
    for f in files:
      fullpath = os.path.join(root, f)
      archive_name = os.path.join(archive_root, f)
      zip.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)
  zip.close()

#Checks if pid is a running process id
def check_pid(pid):
  import platform
  if platform.system() == "Windows":
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(1, 0, pid)
    if handle == 0:
      return False
    exit_code = ctypes.wintypes.DWORD()
    running = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) == 0
    kernel32.CloseHandle(handle)
    return running or exit_code.value == 259

  else:
    try:
      os.kill(pid, 0)
    except OSError:
      return False
    return True

def login_batoto(username=None, password=None):
  global session
  global tree

  root   = tree.getroot()
  config = root.find('batoto') if root is not None else {}
  if config is None:
    config = {}

  if not username:
    username = args.username or (root.find('batot') or {}).get('username')
  if not password:
    password = args.password or (root.find('batot') or {}).get('password')

  if not username:
    print('It seems like you want to use bato.to, but did not provide a' + \
          ' username or password')
    username = input('please enter your bato.to username: ')
  if not password:
   password = input('please enter your bato.to password: ')

  url = "https://bato.to/forums/"
  html = get_html(url, set_head=True)
  auth_key = re.search('auth_key.*?value=[\'"]([^\'"]+)', html).group(1)
  referer = re.search('referer.*?value=[\'"]([^\'"]+)', html).group(1)
  url = 'https://bato.to/forums/index.php?app=core&module=global&section=login&do=process'
  fields = {
    'anonymous'    : 1,
    'rememberMe'   : 1,
    'auth_key'     : auth_key,
    'referer'      : referer,
    'ips_username' : username,
    'ips_password' : password,
  }
  r = session.post(url, data=fields)
  if 'set-cookie' in r.headers:
    session.headers.update({'cookie':r.headers['set-cookie']})
    return True
  else:
    return False #Login failed


def login_mangadex(username=None, password=None):
  global session
  global tree
  root   = tree.getroot()
  config = root.find('mangadex') if root is not None else {}
  if config is None:
    config = {}

  if not username:
    username = args.username or config.get('username')
  if not password:
    password = args.password or config.get('password')

  if not username or not password:
    print('It seems like you want to use mangadex, but did not provide a' + \
          ' username or password')
    username = input('please enter your mangadex username: ')
    password = input('please enter your mangadex password: ')
    if root and not config:
      root.append(Element('mangadex', username=username, password=password))
    elif config:
      config.set('username', username)
      config.set('password', password)

  url = 'https://mangadex.com/ajax/actions.ajax.php?function=login'
  fields = {
    'remember_me'    : 1,
    'login_username' : username,
    'login_password' : password,
  }
  r = session.post(url, data=fields)
  if 'set-cookie' in r.headers:
    session.headers.update({'cookie':r.headers.get('set-cookie','')})
    return True
  else:
    return False #Login failed

#Prits a little spinner while wating for "pid_file" to be deleted or the proces id in "pid_file" to stop working
def wait(pid_file):
  while True:
    try:
      running = True
      spinner = 0
      while running:
        with open(pid_file, 'r') as f:
          if not check_pid(int(f.read().strip())):
            running = False
          else:
            #If another process is using
            spinner += 1
            print('\r  Waiting for process to finish {}'.format(['\\', '|', '/', '-'][spinner%4]), end="", flush=True)
            time.sleep(0.2)
    except:
      #If file does not exist we asume that no one else is adding to calibre - so don't delete the file
      pass

    #Block other proceses(of this program) from editing calibre's library
    #Prevents corruption - trust me, corruptions are not fun when you have a large collection
    with open(pid_file, 'w') as f:
      f.write(str(os.getpid()))

    #This might seem to take up time(I won't argue with that)
    #  and it might seem overly cautious but I am only adding this
    #  after receiving(countless) errors/coruptions
    #
    #If you really want to save time you -might- be able
    #  to lower the number of seconds to wait(default is ~1/3)
    #  but I heavily stress the might and won't guarantee that 1/3 is safe either
    time.sleep(0.3)
    with open(pid_file, 'r') as f:
      if f.read() == str(os.getpid()):
        return

def add_to_calibre(f_name, info):
  pid_file = '{}/.pid'.format(os.path.realpath(os.path.dirname(os.path.realpath(sys.argv[0]))))
  wait(pid_file)

  #Get info to add to meta data
  name        =            info[0]
  series      =            info[1]
  tags        =  ', '.join(info[2])
  pages       =            info[3]
  date        =            info[4]
  if info[0]:
    authors   =            info[5]
  else:
    authors   =           'Unknown'

  if lib_path:
    path = ' --library-path \"{}\"'.format(lib_path)
  else:
    path = ''

  #The extra white space is to remove the previose message
  logger.info('\r  Adding to Calibre                ')

  logger.debug('    {command} add -d -t \"{title}\" -T \"{tags}\" -a \"{aut}\" -s \"{ser}\" -S \"{index}\" \"{f}\"{lib}'.format(
      command=calibredb_executable,
      title=re.sub('([\"$])', '\\\\\\1', name),
      tags=re.sub('([\"$])', '\\\\\\1', tags),
      f=re.sub('([\"$])', '\\\\\\1', f_name),
      ser=re.sub('([\"$])', '\\\\\\1', series),
      index=re.sub('([\"$])', '\\\\\\1', re.search('^.*?([\d]{2,3}\.\d+).*?$', name).group(1)),
      aut=re.sub('([\"$])', '\\\\\\1', authors),
      lib=path))

  #Add file to calibre - at this point only add tags to the meta data
  book_id = os.popen('{command} add -d -t \"{title}\" -T \"{tags}\" -a \"{aut}\" -s \"{ser}\" -S \"{index}\" \"{f}\"{lib}'.format(
    command=calibredb_executable,
    title=re.sub('([\"$])', '\\\\\\1', name),
    tags=re.sub('([\"$])', '\\\\\\1', tags),
    f=re.sub('([\"$])', '\\\\\\1', f_name),
    ser=re.sub('([\"$])', '\\\\\\1', series),
      index=re.sub('([\"$])', '\\\\\\1', re.search('^.*?([\d]{2,3}\.\d+).*?$', name).group(1)),
    aut=re.sub('([\"$])', '\\\\\\1', authors),
    lib=path)).read()

  book_id = re.search('ids:\\s*(\\d+)', book_id).group(1)

  logger.debug('    {command} set_metadata -f \"#read:false\" -f \"pubdate:{date}\" -f\"#aut:{aut}\" -f \"#pages:{pages}\" {bid}{lib}'.format(
    command=calibredb_executable,
    date=date,
    pages=pages,
    bid=book_id,
    aut=re.sub('([\"$])', '\\\\\\1', authors),
    lib=path)
  )

  #Add all other meta data - authors, pages, characters(pururin only), and series
  verbose = os.popen('{command} set_metadata -f \"#read:false\" -f \"pubdate:{date}\" -f\"#aut:{aut}\" -f \"#pages:{pages}\" {bid}{lib}'.format(
    command=calibredb_executable,
    date=date,
    pages=pages,
    bid=book_id,
    aut=re.sub('([\"$])', '\\\\\\1', authors),
    lib=path)
  ).read()

  logger.debug('    Info:\n{}'.format(re.sub('(^|\n)', '\\1      ', verbose.strip())))

  #Open up process for others
  os.remove(pid_file)

def save(links, dirName, img_type, image_links=False):
  dec = 0
  for i in range(len(links)):
    img_name = '{}{:03}.{}'.format(dirName, i+1-dec, img_type)
    if not os.path.exists(img_name.replace('.jpg', '.png')) and not os.path.exists(img_name.replace('.png', '.jpg')):
      print('\r  Downloading {0} of {1}'.format(i+1-dec, len(links)-dec), end="")
      if image_links:
        img_url = links[i]
      elif 'mangadex' in links[i]:
        img_url = re.search('<img[^<]*?id=\"current_page\".*?src=\"([^\"]*?)\"', get_html(links[i]), re.DOTALL|re.MULTILINE).group(1)
        if 'http' not in img_url:
          img_url = 'https://mangadex.com/'+img_url
      elif 'bato.to' in links[i]:
        img_url = re.search('<div.*?>\\s*<img[^<]*?src=\"([^\"]*?)\"[^>]*?/>\\s*</div>', get_html(links[i]), re.DOTALL|re.MULTILINE).group(1)
      elif 'goodmanga.net' in links[i]:
        img_url = re.search('</div>\\s*<a.*?>\\s*<img[^<]*?src=\"(.*?)\".*?>\\s*</a>', get_html(links[i]), re.DOTALL|re.MULTILINE).group(1)
      else:
        img_url = re.search('<a.*?>\\s*<img[^<]*?src=\"(.*?)\".*?>\\s*</a>', get_html(links[i]), re.DOTALL|re.MULTILINE).group(1)

      logger.debug('Downloading(%s) %s', 'T' if image_links else 'F', img_url)

      trys = 8
      for k in range(trys):
        try:
          r = request(img_url)
          if r.status_code != 200:
            raise NameError('No data')
          data = r.content
          break
        except:
          ext = '.' + ('png', 'jpg', 'jpeg', 'gif')[k%4]
          img_url = img_url.rpartition('.')[0] + ext
          img_name = '{}{:03}{}'.format(dirName, i+1, ext)
          if k == trys-1:
            if 'mangadex' in img_url:
              data = None
              break
            raise
          pass
        time.sleep(1.7)
      if not data:
        logger.info('  Could not find image %d (%s)', i, img_url)
        dec += 1
        continue
      with open(img_name, 'wb') as f:
        f.write(data)
  print()
  return len(links) - dec

#I'm calling this function name because I can't think of a better name for it
def function_name(chapters, series, tags, author, status):
  global tree
  global entry
  global last
  global dest
  global url

  l = 0

  logger.debug(
    'getting:\n  chapters: %s\n  series: %s\n  tags: %s\n  author: %s\n  status: %s',
    chapters, series, tags, author, status
  )
  print('Series: {}'.format(series))
  tmpdir = tempfile.mkdtemp()+'/'

  for i in re.findall('(&#(\\d*?);)', str(series)):
    series = series.replace(i[0], chr(int(i[1])))

  for chapter in chapters:
    for i in re.findall('(&#(\\d*?);)', str(chapter['name'])):
      chapter['name'] = chapter['name'].replace(i[0], chr(int(i[1])))

    print('  Downloading chapter - {}'.format(chapter['name']))
    logger.info('Downloading chapter - {}'.format(chapter['name']))
    f_name  = '{}{}.cbz'.format(tmpdir, re.sub('[$&\\*<>:;/]', '_', chapter['name']))
    chapdir = tempfile.mkdtemp(dir=tmpdir)+'/'

    logger.info('  Chapdir - \"{}\"'.format(chapdir))

    try:
      if len(list(set(chapter['links']))) < chapter['pages']:
        raise NameError('All_Links_are_the_Same')

      if 'mangareader.net' in url or 'mangapanda.com' in url:
        raise NameError('Not_Valid_Site_for_Quick_links')

      chapter['pages'] = save(chapter['links'], chapdir, chapter['links'][0].rpartition('.')[2][:3], True)
    except:
      try:
        print('\r  Slight problem - will use backup solution(may be a bit slower)')
        if 'mangadex' in chapter['backup_links'][0]:
          save(chapter['backup_links'], chapdir, re.search('<img[^<]*?id=\"current_page\".*?src=\"([^\"]*?)\"', get_html(chapter['backup_links'][0]), re.DOTALL|re.MULTILINE).group(1).rpartition('.')[2][:3])
        else:
          save(chapter['backup_links'], chapdir, re.search('<a.*?>\\s*<img[^<]*?src=\"(.*?)\".*?>\\s*</a>', get_html(chapter['backup_links'][0]), re.DOTALL|re.MULTILINE).group(1).rpartition('.')[2][:3])
      except:
        logger.exception('Series: \"{}\"\nChapter: {}\n\n'.format(series, '{:3.1f}'.format(chapter['num']).zfill(5)))
        print('\n  Failure')
        shutil.rmtree(tmpdir)
        raise
        return


    zipper(chapdir, f_name)

    if args.add_to_calibre:
      add_to_calibre(f_name, [chapter['name'], series, tags, chapter['pages'], chapter['date'], author])

    if dest:
      while dest.endswith('/'):
        dest = dest[:-1]
      dirName = '{}/{}/'.format(dest, re.sub('[$&\\*<>:;/]', '_', series))
      if not os.path.isdir(dirName):
        os.makedirs(dirName)
      shutil.move(f_name, dirName)

    l=chapter['num']

    if not args.debug:
      shutil.rmtree(chapdir)
    logger.debug('NOT deleting chapdir: \"%s\"', chapdir)
    if not args.url:
      elem = tree.getroot().find(f'entry[url="{url}"]')

      elem.find('.//url').set('name', series)

      if elem.find('.//last') is not None:
        elem.find('.//last').text = str(l)
      else:
        elem.find('.//url').tail = '\n    '
        elem.append(Element('last', text=str(l), tail='\n  '))
        tree.write(xml_list)

  if not args.debug:
    try:
      os.rmdir(tmpdir)
    except:
      print()
      shutil.rmtree(tmpdir)
  logger.debug('NOT deleting tmpdir: \"%s\"', chapdir)

  if not args.url:
    elem = tree.getroot().find(f'entry[url="{url}"]')
    if status != 'Completed':
      if l > last:
        last = l

      elem.find('.//url').set('name', series)

      if elem.find('.//last') is not None :
        elem.find('.//last').text = str(l)
      else:
        elem.find('.//url').tail = '\n    '
        elem.append(Element('last', text=str(l), tail='\n  '))
        tree.write(xml_list)
    else:
      tree.getroot().remove(elem)

  if not args.url:
    tree.write(xml_list)

def mangareader(url, download_chapters):
  html = get_html(url)
  global last

  series    = title(re.search('<td.*?>\\s*Name:.*?<h2.*?>\\s*(.*?)\\s*</h2>\\s*</td>', html.replace('\n', '')).group(1))
  status    = re.search('<td.*?>\\s*Status:.*?<td>\\s*(.*?)\\s*</td>', html.replace('\n', '')).group(1)
  author    = re.search('<td.*?>\\s*Author:.*?<td>\\s*(.*?)\\s*</td>', html.replace('\n', '')).group(1).partition('(')[0].strip()
  tags      = re.findall('<a.*?><span class="genretags">(.*?)</span></a>', html)
  for j in range(len(tags)):
    for k in tag_dict:
      tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  for j in re.findall('<tr>\\s*<td>\\s*<div.*?</div>(.*?)</tr>', html, re.DOTALL|re.MULTILINE):
    match = re.search('<a.*?([\\d.,-]+)</a>(\\s*:\\s*)(.*?)\\s*</td>', j)
    num   = float(match.group(1))
    name  = match.group(3)
    link  = 'http://www.mangareader.net' + re.search('<a\\s*href=\"(/.*?)\">', j).group(1)
    date  = re.search('<td>(\\d{2})/(\\d{2})/(\\d{4})</td>', j)
    date  = '{:04}-{:02}-{:02}'.format(int(date.group(3)), int(date.group(1)), int(date.group(2)))

    if name:
      name = '{} - {} : {}'.format(series, '{:3.1f}'.format(num).zfill(5), name)
    else:
      name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

    if (download_chapters and num in download_chapters) or (not download_chapters and num > last):
      logger.info('  Gathering info: \"{}\"'.format(name))
      chap_html = get_html(link)
      links     = ['http://www.mangareader.net' + i for i in re.findall('<option value=\"(.*?)\".*?>\\d+</option>', chap_html)]
      chapters.append({'name':name, 'links':links, 'backup_links':links, 'date':date, 'pages':len(links), 'num':num})

  if chapters:
    function_name(chapters, series, tags, author, status)

def mangahere(url, download_chapters):
  html  = get_html(url)
  global last

  series    = title(re.search('<(h1 class=")?title"?><span class="title_icon"></span>(.*?)</(h1|title)>', html.replace('\n', '')).group(1))
  status    = re.search('<li><label>Status:</label>(.*?)<', html.replace('\n', '')).group(1)
  author    = ', '.join(re.findall('<a.*?>(.*?)</a>', re.search('<li><label>Author\\(?s?\\)?:</label>(.*?)</li>', html.replace('\n', '')).group(1)))
  tags      = re.search('<li><label>Genre\\(s\\):</label>(.*?)</li>', html).group(1).split(', ')
  for j in range(len(tags)):
    for k in tag_dict:
      tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  for j in re.findall('<li>\\s*<span class=\"left\">\\s*(.*?\\d{4}</span>)\\s*</li>', html, re.DOTALL|re.MULTILINE)[::-1]:
    match = re.search('<a.*?>.*?([\\d,.]+)\\s*</a>\\s*<span.*?>\\s*(.*?)\\s*</span>', j, re.DOTALL|re.MULTILINE)
    name  = match.group(2)
    num   = float(match.group(1))
    link  = re.search('href=\"(.*?)\"', j).group(1)
    try:
      date  = datetime.strptime(re.search('([A-Za-z]*? \\d{1,2}, \\d{4})</span>', j).group(1), '%b %d, %Y').strftime('%Y-%m-%d')
    except:
      date  = datetime.datetime.today().strftime('%Y-%m-%d')

    if name:
      name = '{} - {} : {}'.format(series, '{:3.1f}'.format(num).zfill(5), name)
    else:
      name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

    if (download_chapters and num in download_chapters) or (not download_chapters and num > last):
      logger.info('  Gathering info: \"{}\"'.format(name))
      chap_html  = get_html(link)
      img_url   = re.sub('001.([A-Za-z]{3})', '{:03}.\\1', re.search('<a.*?>\\s*<img[^<]*?src=\"(.*?)\".*?>\\s*</a>', chap_html, re.DOTALL|re.MULTILINE).group(1))
      if '{:03}' not in img_url and '{}' not in img_url:
        img_url   = re.sub('01.([A-Za-z]{3})', '{:02}.\\1', img_url)
      pages     = max([int(i) for i in re.findall('<option value=\".*?\".*?>(\\d+)</option>', chap_html)])
      b_links    = {float(i[1]):i[0] for i in re.findall('<option value=\"(.*?)\".*?>(\\d+)</option>', chap_html)}
      b_links    = [b_links[i+1] for i in range(pages)]
      links      = [img_url.format(i+1) for i in range(pages)]

      chapters.append({'name':name, 'links':links, 'backup_links':b_links, 'date':date, 'pages':pages, 'num':num})

  if chapters:
    function_name(chapters, series, tags, author, status)


def batoto(url, download_chapters):
  login_batoto()
  for i in range(3):
    try:
      html  = get_html(url+'/')
      break
    except:
      if i == 2:
        raise
      else:
        pass

  global last
  global session

  series    = title(re.search('<h1.*?>[\\s\n]*(.*?)[\\s\n]*</h1>', html, re.DOTALL|re.MULTILINE).group(1))
  status    = re.search('<td.*?>Status:</td>\\s*<td>\\s*(.*?)\\s*</td>', html.replace('\n', '')).group(1)
  author    = ', '.join(re.findall('<a.*?>(.*?)</a>', re.search('<td.*?>\\s*Authors?\\s*:?\\s*</td>\\s*<td>(.*?)</td>', html.replace('\n', '')).group(1)))
  tags      = re.findall('<a.*?>\\s*<span.*?>\\s*([A-Za-z]*?)\\s*</span>\\s*</a>', re.search('<td.*?>\\s*Genres?\\s*:?\\s*</td>\\s*<td>(.*?)</td>', html.replace('\n', '')).group(1))
  for j in range(len(tags)):
    for k in tag_dict:
      tags[j] = re.sub(k, tag_dict[k], tags[j])

  chapters  = []

  for j in re.findall('<tr class=\"row lang_([A-Za-z]*?) chapter_row\".*?>(.*?)</tr>', html, re.DOTALL|re.MULTILINE)[::-1]:
    if j[0]  == lang:
      match  = re.search('<a href=\"([^\"]*?)\".*?>\\s*<img.*?>\\s*([^\"<>]*)(\\s*:\\s*)?(.*?)\\s*</a>', j[1], re.DOTALL|re.MULTILINE)
      name   = match.group(4)
      m2     = re.search('[Cc]h(ap)?(ter)?\\.?\\s*([Ee]xtras?:?)?\\s*[\\.:-]?\\s*([\\d\\.,]+)?\\s*(-\\s*[\\d\\.]+)?', match.group(2))
      try:
        if m2.group(3):
          num = 0
        else:
          num = float(m2.group(4).replace(',', '.'))
      except:
        logger.debug(j[1])
        raise

      '''
      #TODO
      if m2.group(3):
        if chapters:
          num = chapters[-1]['num'] + .4
        else:
          num = last + .4
      '''
      try:
        vol  = int(re.search('[Vv]ol(ume)?\\.\\s*(\\d+)', match.group(2)).group(2))
      except:
        vol  = 0
      link   = match.group(1)
      uuid   = link.rpartition('#')[2]
      ref    = link.rpartition('/')[0]+'/' + "reader#" + uuid + "_1"
      head   = {'Referer':ref, 'supress_webtoon':'t'}
      link   = link.rpartition('/')[0]+'/'+ 'areader?id='+uuid+'&p=1'
      session.headers.update(head)

      try:
        date = datetime.strptime(re.search('<td.*?>(\\d{2} [A-Za-z]* \\d{4}.*?([Aa][Mm]|[Pp][Mm])).*?</td>', j[1]).group(1), '%d %B %Y - %I:%M %p').strftime('%Y-%m-%dT%H:%M:00')
      except:
        try:
          t  = re.search('(\\d+) [Mm]inutes ago', j[1]).group(1)
        except:
          t  = '1' if re.search('A minute ago', j[1]) else ''
        if t:
          unit = '%M'
        else:
          try:
            t  = re.search('(\\d+) [Hh]ours ago', j[1]).group(1)
          except:
            t  = '1' if re.search('An hour ago', j[1]) else ''
          if t:
            unit = '%H'
          else:
            try:
              t  = re.search('(\\d+) [Dd]ays ago', j[1]).group(1)
            except:
              t  = '1' if re.search('A day ago', j[1]) else ''
            if t:
              unit = '%d'
            else:
              try:
                t  = re.search('(\\d+) [Ww]eeks ago', j[1]).group(1)
              except:
                t  = '1' if re.search('A week ago', j[1]) else ''
              if t:
                unit = '%W'
              else:
                t = '0'
                unit = '%M'
        date = datetime.fromtimestamp((datetime.today()-datetime.strptime(t, unit)).total_seconds()).strftime('%Y-%m-%dT%H:%M:00')

      if name:
        name = '{} - {} : {}'.format(series, '{:3.1f}'.format(num).zfill(5), name)
      else:
        name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

      if (download_chapters and num in download_chapters) or (not download_chapters and num > last):
        logger.info('  Gathering info: \"{}\"'.format(name))
        chap_html = get_html(link)
        img_url   = re.sub('001\\.([A-Za-z]{3})', '{:03}.\\1', re.search('<div.*?>\\s*<a.*?>\\s*<img[^<]*?src=\"([^\"]*?)\"[^>]*?/>\\s*</div>', chap_html, re.DOTALL|re.MULTILINE).group(1))
        zero = False
        if '{:03}' not in img_url:
          img_url  = re.sub('000\\.([A-Za-z]{3})', '{:03}.\\1', img_url)
          zero = True
          if '{:03}' not in img_url:
            img_url  = re.sub('01\\.([A-Za-z]{3})', '{:02}.\\1', img_url)
            zero = False
            if '{:02}' not in img_url:
              img_url  = re.sub('00\\.([A-Za-z]{3})', '{:02}.\\1', img_url)
              zero = True
        if re.findall('<option value=\".*?\".*?>page (\\d+)</option>', chap_html):
          pages      = max([int(i) for i in re.findall('<option value=\".*?\".*?>page (\\d+)</option>', chap_html)])
        else:
          continue
        b_links    = {float(i[1]):i[0] for i in re.findall('<option value=\"(.*?)\".*?>page (\\d+)</option>', chap_html)}
        b_links    = [b_links[i+1] for i in range(pages)]
        if zero:
          links      = [img_url.format(i) for i in range(pages)]
        else:
          links      = [img_url.format(i+1) for i in range(pages)]

        chapters.append({'name':name, 'links':links, 'backup_links':b_links, 'date':date, 'pages':pages, 'num':num})

  if chapters:
    function_name(chapters, series, tags, author, status)


def mangadex(url, download_chapters):
  login_mangadex()
  if url.endswith('/'):
    url = re.sub('/+$', '', url)
  for i in range(3):
    try:
      html  = get_html(url)
      break
    except:
      if i == 2:
        raise
      else:
        pass

  global last
  global session

  try:
    series    = title(re.sub('<[^>]+>', '', re.search('<h3 class="panel-title">(.*)</h3>', html).group(1)).strip())
    status    = re.search('<th.*?>Pub. status:</th>\\s*<td>\\s*(.*?)\\s*</td>', html.replace('\n', '')).group(1)
    author    = ', '.join(re.findall('<a.*?>(.*?)</a>', re.search('<th.*?>\\s*Authors?\\s*:?\\s*</th>\\s*<td>(.*?)</td>', html.replace('\n', '')).group(1)))
    tags      = re.findall(r'<span.*?>\s*<a.*?>\s*([A-Za-z]*?)\s*</a>\s*</span>', re.search(r'<th.*?>\s*Genres?\s*:?\s*</th>\s*<td>(.*?)</td>', html.replace('\n', '')).group(1))
  except:
    logger.exception('url: %s', url)
    raise
  for j in range(len(tags)):
    for k in tag_dict:
      tags[j] = re.sub(k, tag_dict[k], tags[j])

  chapters  = []

  for j in re.findall(r'<td>\s*(<a[^>]+href=./chapter/.*?)</tr>', html, re.DOTALL|re.MULTILINE)[::-1]:
    if lang in j:
      try:
        match  = re.search(r'<a[^>]+href=\"([^\"]*?)\".*?>\s*(.*?)\s*</a>', j, re.DOTALL|re.MULTILINE)
        m2     = re.search(r'([Cc]h(ap)?(ter)?\.?|([Ee]xtra|[Ss]pecial)s?:?)\s*[\.:-]?\s*([\d\.,]+)?\s*(-\s*[\d\.]+)?', match.group(2))
        name   = match.group(2).replace(m2.group(0) if m2 else match.group(2), '')
        logger.debug('found chapter: %s', match.group(2))

        if not m2 or m2.group(4):
          num = 0
        else:
          num = float(m2.group(5).replace(',', '.'))
      except:
        logger.debug(j)
        raise

      '''
      #TODO
      if m2.group(3):
        if chapters:
          num = chapters[-1]['num'] + .4
        else:
          num = last + .4
      '''
      try:
        vol  = re.search(r'[Vv]ol(ume)?\.?\s*(\d+)', match.group(2))
        name = name.replace(vol.group(0), '').strip()
        name = re.sub(r'^\s*-? ?(Read On[ -]?line)?\s*', '', name, re.I)
        vol  = int(vol.group(2))
      except:
        vol  = 0
      link   = 'https://mangadex.com/{}/'.format(match.group(1))

      date = re.search('datetime=\"(.*?)( [A-Z]{3})?\"', j).group(1).replace(' ', 'T')

      if name:
        name = '{} - {} : {}'.format(series, '{:3.1f}'.format(num).zfill(5), name)
      else:
        name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

      if (download_chapters and num in download_chapters) or (not download_chapters and num > last):
        logger.info('  Gathering info: \"{}\"'.format(name))
        chap_html = get_html(link+'1')
        img_url   = re.search('<img[^<]*?id=\"current_page\".*?src=\"([^\"]*?)\"', chap_html, re.DOTALL|re.MULTILINE).group(1)
        logger.debug('original url: %s', img_url)
        img_url = re.sub('(/?)0*[01]\\.([A-Za-z]{3})$', r'\1{}.\2', img_url)
        if 'http' not in img_url:
          img_url = 'https://mangadex.com/' + img_url
        zero = False
        if '{' not in img_url:
          img_url = re.sub(r'(/?)0\.([a-zA-Z]{3})', r'\1{}.\2', img_url)
          zero = True
        if '{' not in img_url:
          img_url = re.sub(r'(/?)01\.([a-zA-Z]{3})', r'\1{:02}.\2', img_url)
          zero = False
        if '{' not in img_url:
          img_url = re.sub('0*1\\.([A-Za-z]{3})', r'{:02}.\1', img_url)
          zero = False
        if '{' not in img_url:
          img_url = re.sub('0*0\\.([A-Za-z]{3})', r'{:02}.\1', img_url)
          zero = True
        logger.debug('general  url: %s', img_url)

        if re.findall(r'<option[^>]+value=[\"\'].*?[\'\"].*?>Page (\d+)</option>', chap_html):
          pages = max([int(i) for i in re.findall(r'<option[^>]+value=[\"\'].*?[\'\"].*?>Page (\d+)</option>', chap_html)])
        else:
          continue
        b_links = {float(i[1]):link+i[0] for i in re.findall(r'<option[^>]+value=[\"\'](.*?)[\'\"].*?>Page (\d+)</option>', chap_html)}
        b_links = ['https://mangadex.com/'+b_links[i+1] for i in range(pages)]
        if zero:
          links = [img_url.format(i) for i in range(pages)]
        else:
          links = [img_url.format(i+1) for i in range(pages)]

        chapters.append({'name':name, 'links':links, 'backup_links':b_links, 'date':date, 'pages':pages, 'num':num})

  if chapters:
    function_name(chapters, series, tags, author, status)

def mangapanda(url, download_chapters):
  html  = get_html(url)
  global last

  series    = title(re.search('<h1.*?>\\s*(.*?)\\s*</h1>', html, re.DOTALL|re.MULTILINE).group(1)).rpartition(' Manga')[0]
  status    = re.search('<td.*?>Status:</td>\\s*<td>\\s*(.*?)\\s*</td>', html.replace('\n', '')).group(1)
  author    = re.search('<td.*?>\\s*Authors?\\s*:?\\s*</td>\\s*<td>(.*?)</td>', html.replace('\n', '')).group(1)
  tags      = re.findall('<a.*?>\\s*<span.*?>\\s*([A-Za-z]*?)\\s*</span>\\s*</a>', re.search('<td.*?>\\s*Genres?\\s*:?\\s*</td>\\s*<td>(.*?)</td>', html.replace('\n', '')).group(1))
  for j in range(len(tags)):
    for k in tag_dict:
      tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  for j in re.findall('<tr>\\s*<td>\\s*<div.*?</div>(.*?)</tr>', html, re.DOTALL|re.MULTILINE):
    match = re.search('<a.*?([\\d.,-]+)</a>(\\s*:\\s*)(.*?)\\s*</td>', j)
    num   = float(match.group(1))
    name  = match.group(3)
    link  = 'http://www.mangapanda.com' + re.search('<a\\s*href=\"(/.*?)\">', j).group(1)
    date  = re.search('<td>(\\d{2})/(\\d{2})/(\\d{4})</td>', j)
    date  = '{:04}-{:02}-{:02}'.format(int(date.group(3)), int(date.group(1)), int(date.group(2)))

    if name:
      name = '{} - {} : {}'.format(series, '{:3.1f}'.format(num).zfill(5), name)
    else:
      name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

    if (download_chapters and num in download_chapters) or (not download_chapters and num > last):
      logger.info('  Gathering info: \"{}\"'.format(name))
      chap_html = get_html(link)
      links     = ['http://www.mangareader.net' + i for i in re.findall('<option value=\"(.*?)\".*?>\\d+</option>', chap_html)]
      chapters.append({'name':name, 'links':links, 'backup_links':links, 'date':date, 'pages':len(links), 'num':num})

  if chapters:
    function_name(chapters, series, tags, author, status)

def goodmanga(url, download_chapters):
  html  = get_html(url)
  global last

  series    = title(re.search('<h1>([^<>]*?)</h1>', html.replace('\n', '')).group(1))
  status    = re.search('<span>Status:</span>\\s*(.*?)\\s*</div>', html.replace('\n', '')).group(1)
  author    = re.search('<span>Authors?:</span>\\s*(.*?)\\s*</div>', html.replace('\n', '')).group(1)
  tags      = re.findall('<a.*?>(.*?)</a>', re.search('<span>Genres:</span>(.*?)\\s*</div>', html, re.DOTALL|re.MULTILINE).group(1))
  for j in range(len(tags)):
    for k in tag_dict:
      tags[j] = re.sub(k, tag_dict[k], tags[j])
  chapters  = []

  while True:
    for j in re.findall('<li>\\s*(.{1,300}?\\d{4}</span>)\\s*</li>', html, re.DOTALL|re.MULTILINE):
      match = re.search('<a.*?>.*?([\\d,.]+)\\s*</a>\\s*<span.*?>\\s*(.*?)\\s*</span>', j, re.DOTALL|re.MULTILINE)
      name  = match.group(2)
      num   = float(match.group(1))
      link  = re.search('href=\"(.*?)\"', j).group(1)
      try:
        date  = datetime.strptime(re.search('([A-Za-z]*? \\d{1,2}, \\d{4})</span>', j).group(1), '%b %d, %Y').strftime('%Y-%m-%d')
      except:
        date  = datetime.datetime.today().strftime('%Y-%m-%d')

      if name:
        name = '{} - {} : {}'.format(series, '{:3.1f}'.format(num).zfill(5), name)
      else:
        name = '{} - {}'.format(series, '{:3.1f}'.format(num).zfill(5))

      if (download_chapters and num in download_chapters) or (not download_chapters and num > last):
        logger.info('  Gathering info: \"{}\"'.format(name))
        chap_html  = get_html(link)
        img_url    = re.sub('1.([jpgnig]{3})', '{}.\\1', re.search('</div>\\s*<a.*?>\\s*<img[^<]*?src=\"(.*?)\".*?>\\s*</a>', chap_html, re.DOTALL|re.MULTILINE).group(1))
        pages      = max([int(i) for i in re.findall('<option value=\".*?\".*?>\\s*(\\d+)\\s*</option>', chap_html)])
        b_links    = {float(i[1]):i[0] for i in re.findall('<option value=\"(.*?)\".*?>\\s*(\\d+)\\s*</option>', chap_html)}
        b_links    = [b_links[i+1] for i in range(pages)]
        links      = [img_url.format(i+1) for i in range(pages)]

        chapters.insert(0, {'name':name, 'links':links, 'backup_links':b_links, 'date':date, 'pages':pages, 'num':num})
    match   = re.search('<a href=\"(.*?)\">Next</a>', html)
    if match:
      html  = get_html(match.group(1))
    else:
      break

  if chapters:
    function_name(chapters, series, tags, author, status)

def main():
  global tree
  global entry
  global last
  global dest
  global url
  global session

  download_chapters = []
  if args.chap:
    download_chapters = re.split('\\s*,\\s*', args.chap)
    for i in download_chapters:
      if type(i) == str and '-' in i:
        download_chapters.remove(i)
        for j in range(int(float(re.split('\\s*-\\s*', i, maxsplit=1)[0])*10), int(float(re.split('\\s*-\\s*', i, maxsplit=1)[1])*10)+1):
          download_chapters.append(j/10.0)
    download_chapters = sorted(list(set([float(j) for j in download_chapters])))
    #logger.debug('chapters: %s', ','.join(str(x) for x in download_chapters))

  if not args.url:
    for entry in tree.getroot().iterfind('entry'):
      session = Session()
      session.headers.update({'User-agent': 'Mozilla/5.0'})
      try:
        url = entry.find('url').text.strip()
      except:
        logger.exception(ET.tostring(entry))
        sys.exit(-1)

      try:
        last   = float(entry.find('last').text.strip())
      except:
        last   = -1

      try:
        dest   = entry.find('destination').text
      except:
        if not args.add_to_calibre:
          dest = './'
        else:
          dest = ''
      logger.info('URL - {}'.format(url))

      if 'mangadex' in url:
        mangadex(url, download_chapters)
      elif 'mangareader.net' in url:
        mangareader(url, download_chapters)
      elif 'mangahere.co' in url:
        mangahere(url, download_chapters)
      elif 'bato.to' in url:
        batoto(url+'/', download_chapters)
      elif 'mangapanda.com' in url:
        mangapanda(url, download_chapters)
      elif 'goodmanga.net' in url:
        goodmanga(url, download_chapters)

      tree.write(xml_list)
  else:
    if args.dest:
      dest = args.dest
    elif not args.add_to_calibre:
      dest = './'
    else:
      dest = ''
    url = args.url
    if not download_chapters:
      last = -1

    if 'mangadex' in url:
      mangadex(url, download_chapters)
    elif 'mangareader.net' in url:
      mangareader(url, download_chapters)
    elif 'mangahere.co' in url:
      mangahere(url, download_chapters)
    elif 'bato.to' in url:
      batoto(url+'/', download_chapters)
    elif 'mangapanda.com' in url:
      mangapanda(url, download_chapters)
    elif 'goodmanga.net' in url:
      goodmanga(url, download_chapters)


if __name__ == "__main__":
  main()
