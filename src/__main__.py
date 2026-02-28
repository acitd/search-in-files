#!/usr/bin/python3
import gi
import os
import subprocess
import argparse
import threading
import time
from queue import Queue,Empty
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
MAX_MB=1
EXCLUDED_EXTS={
	'.7z','.zip','.rar','.tar','.gz','.xz','.bz2','.lz','.lzma','.zst',
	'.jpg','.jpeg','.png','.gif','.bmp','.webp',
	'.svg','.ico','.tiff','.tif','.heic','.heif','.avif',
	'.mp4','.avi','.mkv','.mov','.wmv','.flv','.webm','.m4v','.3gp',
	'.mp3','.wav','.flac','.aac','.ogg','.m4a','.wma',
	'.pdf','.doc','.docx','.xls','.xlsx','.ppt','.pptx',
	'.odt','.ods','.odp','.rtf','.epub',
	'.exe','.dll','.so','.bin','.msi','.dmg','.apk','.app',
	'.iso','.img','.vhd','.vmdk',
	'.ttf','.otf','.woff','.woff2',
	'.db','.sqlite','.sqlite3','.mdb',
	'.deb','.rpm','.pkg'
}
def iter_files_scandir(root_dir,stop_event: threading.Event):
	stack=[root_dir]
	while stack and not stop_event.is_set():
		d=stack.pop()
		try:
			with os.scandir(d) as it:
				for entry in it:
					if stop_event.is_set():
						return
					try:
						if entry.is_dir(follow_symlinks=False):
							stack.append(entry.path)
						elif entry.is_file(follow_symlinks=False):
							yield entry.path,entry
					except OSError:
						continue
		except OSError:
			continue
class FileSearchWindow(Gtk.Window):
	def __init__(self,initial_dir=None,initial_text=None,open_command=None):
		super().__init__(title='Search in Files')
		self.set_default_size(800,500)
		try:
			self.set_icon_from_file('res/icon.svg')
		except Exception:
			pass
		self.open_command=open_command
		self.max_file_size=MAX_MB*1024*1024
		self.search_thread=None
		self.stop_event=threading.Event()
		self.result_queue=Queue()
		self._ui_timer_id=None
		self._last_status_update=0.0
		self._status_path=''
		self._result_count=0
		main_vbox=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6)
		self.add(main_vbox)
		top_box=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=6)
		main_vbox.pack_start(top_box,False,False,0)
		self.dir_button=Gtk.Button(label='Browse')
		self.dir_button.connect('clicked',self.on_browse_button_chosen)
		top_box.pack_start(self.dir_button,False,False,0)
		self.dir_entry=Gtk.Entry()
		self.dir_entry.set_placeholder_text('Directory (e.g. /home/user)')
		self.dir_entry.connect('activate',self.on_search)
		top_box.pack_start(self.dir_entry,True,True,0)
		self.search_entry=Gtk.Entry()
		self.search_entry.set_placeholder_text('Text to search')
		self.search_entry.connect('activate',self.on_search)
		top_box.pack_start(self.search_entry,True,True,0)
		self.search_entry.grab_focus()
		self.store=Gtk.ListStore(str,str,str)
		self.treeview=Gtk.TreeView(model=self.store)
		for i,title in enumerate(['File','Line','Content']):
			renderer=Gtk.CellRendererText()
			column=Gtk.TreeViewColumn(title,renderer,text=i)
			column.set_resizable(True)
			column.set_min_width(100)
			if i==0:
				column.set_fixed_width(200)
				column.set_expand(False)
			if i==1:
				column.set_resizable(False)
			self.treeview.append_column(column)
		self.treeview.connect('row-activated',self.on_row_activated)
		scroll=Gtk.ScrolledWindow()
		scroll.set_policy(Gtk.PolicyType.AUTOMATIC,Gtk.PolicyType.AUTOMATIC)
		scroll.add(self.treeview)
		main_vbox.pack_start(scroll,True,True,0)
		self.status_bar=Gtk.Statusbar()
		main_vbox.pack_start(self.status_bar,False,False,0)
		if initial_dir:
			self.dir_entry.set_text(initial_dir)
		if initial_text:
			self.search_entry.set_text(initial_text)
			self.search_entry.select_region(0,-1)
			self.on_search()
		self.connect('destroy',self.on_window_destroy)
	def on_browse_button_chosen(self,widget):
		dialog=Gtk.FileChooserDialog(
			title='Select Directory',
			parent=self,
			action=Gtk.FileChooserAction.SELECT_FOLDER,
			buttons=(Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN,Gtk.ResponseType.OK)
		)
		response=dialog.run()
		if response==Gtk.ResponseType.OK:
			directory=dialog.get_filename()
			self.dir_entry.set_text(directory)
		dialog.destroy()
		self.on_search()
	def on_search(self,*args):
		directory=self.dir_entry.get_text().strip()
		search_text=self.search_entry.get_text().strip()
		self.stop_current_search()
		if not directory or not search_text or not os.path.isdir(directory):
			return
		self.store.clear()
		self._result_count=0
		self.status_bar.push(0,'Searching...')
		self.stop_event=threading.Event()
		self.result_queue=Queue()
		self.search_thread=threading.Thread(
			target=self.search_files_worker,
			args=(directory,search_text),
			daemon=True
		)
		self.search_thread.start()
		if self._ui_timer_id is not None:
			GLib.source_remove(self._ui_timer_id)
			self._ui_timer_id=None
		self._ui_timer_id=GLib.timeout_add(50,self.update_results_from_queue)
	def stop_current_search(self):
		try:
			self.stop_event.set()
		except Exception:
			pass
	def search_files_worker(self,directory,search_text):
		needle=search_text.encode('utf-8',errors='ignore')
		for absolute_path,entry in iter_files_scandir(directory,self.stop_event):
			if self.stop_event.is_set():
				break
			_,ext=os.path.splitext(entry.name)
			if ext.lower() in EXCLUDED_EXTS:
				continue
			now=time.monotonic()
			if now - self._last_status_update>0.2:
				self._last_status_update=now
				self._status_path=absolute_path
			try:
				st=entry.stat(follow_symlinks=False)
				if st.st_size>self.max_file_size:
					continue
			except OSError:
				continue
			try:
				with open(absolute_path,'rb') as f:
					for i,line in enumerate(f,1):
						if self.stop_event.is_set():
							break
						if needle in line:
							text=line.decode('utf-8',errors='replace').strip()
							relpath=os.path.relpath(absolute_path,directory)
							self.result_queue.put((relpath,str(i),text))
			except (OSError,IOError):
				continue
		self.result_queue.put(('__DONE__',directory,''))
	def update_results_from_queue(self):
		if self._status_path:
			self.status_bar.push(0,f'Processing file: {self._status_path}')
		done=False
		batch=0
		MAX_BATCH=800
		while batch < MAX_BATCH:
			try:
				relpath,line_no,text=self.result_queue.get_nowait()
			except Empty:
				break
			if relpath=='__DONE__':
				done=True
				break
			if len(text)>160:
				text=text[:160]+'...'
			self.store.append([relpath,line_no,text])
			self._result_count+=1
			batch+=1
		if done:
			while True:
				try:
					relpath,line_no,text=self.result_queue.get_nowait()
				except Empty:
					break
				if relpath=='__DONE__':
					continue
				if len(text)>160:
					text=text[:160]+'...'
				self.store.append([relpath,line_no,text])
				self._result_count+=1
			if self._result_count==0:
				self.status_bar.push(0,'No results found.')
			else:
				self.status_bar.push(0,f'Search complete: {self._result_count} results found.')
			self._ui_timer_id=None
			return False
		return True
	def on_row_activated(self,treeview,path,column):
		model=treeview.get_model()
		it=model.get_iter(path)
		relative_path=model[it][0]
		line_number=model[it][1]
		directory=self.dir_entry.get_text().strip()
		absolute_path=os.path.join(directory,relative_path)
		if self.open_command:
			command=self.open_command.replace('{path}',absolute_path).replace('{line}',line_number)
			subprocess.Popen(command,shell=True)
		else:
			subprocess.Popen(['xdg-open',absolute_path])
	def on_window_destroy(self,widget):
		self.stop_current_search()
		Gtk.main_quit()
def main():
	parser=argparse.ArgumentParser(description='GTK File Search Tool')
	parser.add_argument('text',nargs='?',default=None,help='Text to search for')
	parser.add_argument('-d','--directory',default=os.getcwd(),help='Directory to search in')
	parser.add_argument('-o','--open',help="Command to open the file (e.g. 'vim +{line} {path}')")
	args=parser.parse_args()
	win=FileSearchWindow(initial_dir=args.directory,initial_text=args.text,open_command=args.open)
	win.show_all()
	Gtk.main()
if __name__=='__main__':
	main()
