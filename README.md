# Search in Files (search-in-files)
A simple tool to search text inside files.

# Setup
Go to project directory and run the following commands.
### Depndencies
```bash
python3
```

### Install
Install as to current user.
```bash
bin/install.sh
```
Install globally.
```bash
sudo bin/install.sh
```
### Uninstall
Install as to current user.
```bash
bin/uninstall.sh
```
Install globally.
```bash
sudo bin/uninstall.sh
```

## Usage
Open in treminal
```bash
search-in-files
```
Search in current directory
```bash
search-in-files "hello world"
```
Search in another directory
```bash
search-in-files "hello world" -d "/home/user/Downloads"
```
Open the found files with your favorite text editor on double-click
```bash
search-in-files "hello world" -d "/home/user/Downloads" -o "vim {file}:{line}"
```
