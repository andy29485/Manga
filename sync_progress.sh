#!/bin/bash

lst="`dirname "$0"`/list.xml"
lib="`xmllint --xpath ".//calibre/@location" $lst | grep -Po '(?<=").*(?=")'`"

contains () {
  local e
  for e in "${@:2}"; do [[ "$e" == "$1" ]] && return 0; done
  return 1
}

calibredb list -f "*progress,*read,series,*list" --separator "=|=" --with-library "$lib" | perl -pe 's/ +/_/g' | perl -pe 's/_*=\|=_*/ /g' | egrep "^[0-9]" > .library_tmp_info

while read line ; do
  declare -a line=($line)
  if [ "${line[1]}" != "100.0" ] && [ "${line[2]}" == "True" ] ; then
    calibredb set_metadata -f "#progress:100.0" ${line[0]} --with-library "$lib"
  elif [ "${line[1]}" == "100.0" ] && [ "${line[2]}" != "True" ] ; then
    calibredb set_metadata -f "#read:True" ${line[0]} --with-library "$lib"
  fi
done < .library_tmp_info

declare -a series

while read line ; do
  declare -a line=($line)
  if [ "${line[4]}" == "device" ] && ! contains "${line[3]}" "${series[@]}" ; then
    series=("${line[3]}" ${series[@]})
  fi
done < .library_tmp_info

while read line ; do
  declare -a line=($line)
  if [ "${line[4]}" == "None" ] && contains "${line[3]}" "${series[@]}" ; then
    calibredb set_metadata -f "#list:device" ${line[0]} --with-library "$lib"
  fi
done < .library_tmp_info
rm .library_tmp_info
