Manga
=====

downloads manga in cbz files

Websites that work
==
* [MangaDex](https://mangadex.com/)
* [mangareader](https://www.mangareader.net/)
* [mangahere](https://www.mangareader.net/)
* ~~[batoto](https://bato.to/)~~ They shut down
* [mangapanda](https://www.mangapanda.com/)
* [goodmanga](httsp://www.goodmanga.net/)

Install
====
For this to run you'll need python3
Windows/Mac users:
Go here
https://www.python.org/downloads/

Linux:
run `sudo apt-get install python3`
or the equivalet using your perfered(or default) package manager

Command line opptions
====
```
usage: manga.py [-h] [-x LIST] [-D] [-v] [-d DEST] [-a] [-u USERNAME]
                [-p PASSWORD]
                [url] [chap]

positional arguments:
  url                   Url of page to download - do not combine with
                        -x/--list
  chap                  Chaptes to download - Only works if url is also
                        specified

optional arguments:
  -h, --help            show this help message and exit
  -x LIST, --list LIST  Path to xml list containing data - default list.xml in
                        directory of this script
  -D, --debug           Print extra stuff(verbose) and don't remove temp dirs
  -v, --verbose         Print extra stuff(verbose)
  -d DEST, --dest DEST  Directory to copy files to after download - default
                        nowhere - Only works if url is also specified
  -a, --add-to-calibre  Add book to calibre
  -u USERNAME, --username USERNAME
                        MangaDex username
  -p PASSWORD, --password PASSWORD
                        MangaDex password
```

There are a few methods of getting this to work.
By default it will simply download the the images and create a .cbz file, but if you would like it to add the chapter into calibre just set the `-a` flag. *But to use this be sure to specify the location of the calibre library in the python file.*

**Opption 1:**
`manga.py <url> <chapters> [-a]`
- url is the url to the main page of the series: http://www.bato.to/comic/_/comics/sen-to-man-r10545
- chapters is the chapter number(s) that you want for example
  - if the series has chapters 1, 2, 3, 4.5, 5, 6.1, 6.25, 7 out, you can match tem by:
    - 1,2,3,4.5,5,6.1,6.25,7
  - 1-7
  - if you do not want to include chapter 5 just combine the opptions:
    - 1-4.9,6-7

**Opption 2**
Use the xml
1. Create a file named `list.xml` (or something else)
2. Populate the list with entries/passwords (`last` is an optional line)
  ```
  <xml>
    <mangadex username="Your Username" password="Your Password" />
    <batoto username="Your Username" password="Your Password" />
    <entry>
      <url>https://mangadex.com/manga/1</url>
    </entry>
    <entry>
      <url>https://mangadex.com/manga/2</url>
      <last>10</last>
    </entry>
  </xml>
  ```
3. run `manga.py [-x list.xml] [-a]`
