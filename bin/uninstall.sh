#!/bin/bash
if [[ "$EUID" -eq 0 ]]; then
	root_dir=/usr/local
else
	root_dir=~/.local
fi

app_slug=search-in-files

bin_link=$root_dir/bin/$app_slug
lib_dir=$root_dir/lib/$app_slug
main_file=$lib_dir/__main__.py
share_dir=$root_dir/share/$app_slug

rm -R  $bin_link $lib_dir $share_dir
