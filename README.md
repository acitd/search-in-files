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
To start using it type to the terminal:
```bash
search-in-files
```
If you want to search directly to a specific directory you can do it like this:
```bash
search-in-files -d /home/user/Downloads -t "hello world"
```
If you want to open the found files with your editor
```bash
search-in-files -d /home/user/Downloads -t "hello world" -o 'vim {file}:{line}'
```
