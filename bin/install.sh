#!/bin/bash
if [[ "$EUID" -eq 0 ]]; then
	root_dir=/usr/local
else
	root_dir=~/.local
fi

app_slug=search-in-files

bin_dir=$root_dir/bin
bin_link=$bin_dir/$app_slug
lib_dir=$root_dir/lib/$app_slug
main_file=$lib_dir/__main__.py
share_dir=$root_dir/share/$app_slug


mkdir -p $bin_dir $lib_dir $share_dir


cp -r src/* $lib_dir
cp -r res/* $share_dir

find $lib_dir -type f -exec sed -i "s|res/|$share_dir/|g" {} +

chmod +x $main_file
if [ ! -L $bin_link ]; then
		ln -s $main_file $bin_link
fi

