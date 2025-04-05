#!/usr/bin/python3

import gi
import os
import subprocess
import argparse
import threading
import time
from queue import Queue

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

class FileSearchWindow(Gtk.Window):
	def __init__(self, initial_dir=None, initial_text=None, open_command=None, max_file_size=2*1024*1024):
		super().__init__(title='Search in Files')
		self.set_default_size(800, 500)
		self.set_icon_from_file('res/icon.svg')

		self.open_command = open_command  # Store the open command (optional)
		self.search_thread = None
		self.search_flag = False  # Flag to track if a search is in progress
		self.result_queue = Queue()  # Queue for transferring results to the main thread
		self.max_file_size = max_file_size  # Maximum file size to read (default 2MB)

		# Main vertical layout
		main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
		self.add(main_vbox)

		# Top HBox with directory, search text, and button
		top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
		main_vbox.pack_start(top_box, False, False, 0)

		# Browse button to the left
		self.dir_button = Gtk.Button(label='Browse')
		self.dir_button.connect('clicked', self.on_browse_button_chosen)
		top_box.pack_start(self.dir_button, False, False, 0)

		# Directory input field
		self.dir_entry = Gtk.Entry()
		self.dir_entry.set_placeholder_text('Directory (e.g. /home/user)')
		#self.dir_entry.connect('changed', self.on_directory_changed)  # Listen for directory changes
		self.dir_entry.connect('activate', self.on_search)
		top_box.pack_start(self.dir_entry, True, True, 0)

		self.search_entry = Gtk.Entry()
		self.search_entry.set_placeholder_text('Text to search')
		#self.search_entry.connect('changed', self.on_text_changed)  # Listen for directory changes
		self.search_entry.connect('activate', self.on_search)
		top_box.pack_start(self.search_entry, True, True, 0)

		#self.search_button = Gtk.Button(label='Search')
		#self.search_button.connect('clicked', self.on_search)
		#top_box.pack_start(self.search_button, False, False, 0)

		self.dir_entry.connect('activate', self.on_search)
		#self.search_entry.connect('activate', self.on_search)

		# ListStore and TreeView
		self.store = Gtk.ListStore(str, str, str)  # File, Line, Content
		self.treeview = Gtk.TreeView(model=self.store)

		# Create columns for the TreeView
		for i, title in enumerate(['File', 'Line', 'Content']):
			renderer = Gtk.CellRendererText()
			column = Gtk.TreeViewColumn(title, renderer, text=i)
			column.set_resizable(True)  # Make the column resizable
			column.set_min_width(100)  # Set a minimum width
			if i == 0:
				column.set_fixed_width(200)  # Set the 'File' column to a fixed width of 200px
				column.set_expand(False)  # Prevent expanding the 'File' column
			if i == 1:
				column.set_resizable(False)  # Make the 'Line' column non-resizable
			self.treeview.append_column(column)

		self.treeview.connect('row-activated', self.on_row_activated)

		# Scrollable area for TreeView
		scroll = Gtk.ScrolledWindow()
		scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		scroll.add(self.treeview)
		main_vbox.pack_start(scroll, True, True, 0)

		# Status Bar at the bottom
		self.status_bar = Gtk.Statusbar()
		#self.status_bar.set_size_request(-1, 20)  # Make the status bar smaller (20px height)
		main_vbox.pack_start(self.status_bar, False, False, 0)

		# Pre-fill and auto-search
		if initial_dir:
			self.dir_entry.set_text(initial_dir)
		if initial_text:
			self.search_entry.set_text(initial_text)
			self.on_search()  # Auto-search on load if both are set

		# Connect window destroy event to handle app termination
		self.connect('destroy', self.on_window_destroy)

	def on_browse_button_chosen(self, widget):
		dialog = Gtk.FileChooserDialog(
			title='Select Directory',
			parent=self,
			action=Gtk.FileChooserAction.SELECT_FOLDER,
			buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
		)

		response = dialog.run()

		if response == Gtk.ResponseType.OK:
			directory = dialog.get_filename()
			self.dir_entry.set_text(directory)  # Set the directory path in the input field

		dialog.destroy()
		self.on_search()

	def on_text_changed(self, entry):
		print('Text changed')
		# When the directory is changed, restart the search
		#self.on_search()

	def on_search(self, *args):
		directory = self.dir_entry.get_text().strip()
		search_text = self.search_entry.get_text().strip()

		# Stop previous search if any is in progress
		self.stop_current_search()

		if not directory or not search_text or not os.path.isdir(directory):
			return

		self.store.clear()
		self.status_bar.push(0, 'Searching...')

		# Start a new search in a separate thread
		self.search_flag = True
		self.result_queue = Queue()  # Reset the result queue for the new search
		self.search_thread = threading.Thread(target=self.search_files, args=(directory, search_text))
		self.search_thread.start()

		# Start periodic updates from the result queue
		GLib.timeout_add(100, self.update_results_from_queue)

	def search_files(self, directory, search_text):
		result_count = 0
		for root, _, files in os.walk(directory):
			if not self.search_flag:  # If a new search is requested, stop this search
				break

			for fname in files:
				if not self.search_flag:  # If a new search is requested, stop this search
					break
				try:
					full_path = os.path.join(root, fname)

					# Skip files that are too large
					if os.path.getsize(full_path) > self.max_file_size:
						continue

					with open(full_path, 'r', errors='ignore') as f:
						for i, line in enumerate(f, 1):
							if search_text in line:
								relpath = os.path.relpath(full_path, directory)
								self.result_queue.put([relpath, str(i), line.strip()])
								result_count += 1
					# Update the status bar with the current file being processed
					GLib.idle_add(self.update_status_bar, full_path)

				except Exception as e:
					print(f'Error reading {full_path}: {e}')

				time.sleep(0.1)  # Tiny sleep to reduce CPU usage

		GLib.idle_add(self.search_completed, result_count)

	def stop_current_search(self):
		if self.search_flag:  # If a search is in progress, stop it
			self.search_flag = False
			if self.search_thread and self.search_thread.is_alive():
				self.search_thread.join()  # Wait for the current search to terminate

	def update_results(self, filename, line_number, line_text):
		# Truncate the content if it exceeds 160 characters
		if len(line_text) > 160:
			line_text = line_text[:160] + '...'  # Add ellipsis to indicate truncation
		# Append results in the main thread (safe UI update)
		self.store.append([filename, line_number, line_text])

	def update_results_from_queue(self):
		# Retrieve and display results from the queue
		while not self.result_queue.empty():
			result = self.result_queue.get()
			GLib.idle_add(self.update_results, *result)

		return True  # Keep the timeout running

	def search_completed(self, result_count):
		# Re-enable search button when done and update status
		#self.search_button.set_sensitive(True)
		if result_count == 0:
			self.status_bar.push(0, 'No results found.')
		else:
			self.status_bar.push(0, f'Search complete: {result_count} results found.')

	def update_status_bar(self, filename):
		# Update the status bar with the current file being processed
		self.status_bar.push(0, f'Processing file: {filename}')

	def on_row_activated(self, treeview, path, column):
		model = treeview.get_model()
		iter = model.get_iter(path)
		filename = model[iter][0]
		line_number = model[iter][1]  # Get the line number

		if self.open_command:
			# If an open command is provided, use it
			command = self.open_command.replace('{file}', filename).replace('{line}', line_number)
			subprocess.Popen(command, shell=True)
		else:
			# Default action: Use xdg-open
			directory = self.dir_entry.get_text().strip()
			full_path = os.path.join(directory, filename)
			if os.path.isfile(full_path):
				subprocess.Popen(['xdg-open', full_path])
			else:
				print(f'File not found: {full_path}')

	def on_window_destroy(self, widget):
		# Stop the current search and quit GTK when window is closed
		self.stop_current_search()
		Gtk.main_quit()

# ---- Argument Parser ----
def main():
	parser = argparse.ArgumentParser(description='GTK File Search Tool')
	parser.add_argument('text', nargs='?', default=None, help='Text to search for')
	parser.add_argument('-d', '--directory', default=os.getcwd(), help='Directory to search in')
	parser.add_argument('-o', '--open', help="Command to open the file (e.g. 'vim {file}:{line}')")
	args = parser.parse_args()

	win = FileSearchWindow(initial_dir=args.directory, initial_text=args.text, open_command=args.open)
	win.connect('destroy', Gtk.main_quit)
	win.show_all()
	Gtk.main()

if __name__ == '__main__':
	main()
