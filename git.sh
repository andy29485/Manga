#!/bin/bash

cd $(dirname $0)

#git remote add origin https://github.com/andy29485/Manga.git

git pull https://github.com/andy29485/Manga.git

git add -A
git commit
git push origin master

