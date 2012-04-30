#!/usr/bin/env python

import warnings
warnings.simplefilter('ignore', DeprecationWarning)

import paramiko
import getpass
import threading
import time
import sys
import readline
import os
import string
from optparse import OptionParser

padding = 0
do_break = False
prompt = '___::'

class ssh_connection(threading.Thread):
	def __init__(self, user, password, ip, cmd, pretty_print=True, space=False):
		threading.Thread.__init__(self)
		self.ip = ip
		self.alive = True
		self.cmd = cmd
		self.failed = False
		if self.cmd == None:self.cmd = 'uptime'
		self.output = ''
		self.password = password
		self.user = user
		self.pretty_print = pretty_print
		self.space = space
		self.lock = threading.Lock()
		self.ready = True
	
	def format(self, data):
		r = ''
		for l in data.split('\r\n'):
			l = l.strip()
			if self.pretty_print:
				l = '[' + self.ip.rjust(padding) + '] ' + l
			r += l + '\n'
		if self.space:
			self.output = r
		else:
			self.output = r.strip()
	
	def recieve(self, c, cmd):
		data = ''
		count = 0
		while len(data) == 0 or data[-len(prompt):].strip() != prompt:
			if not c.recv_ready():
				count += 1
				time.sleep(0.1)
			else:
				d = c.recv(1024)
				data += d
			if do_break and count > 100: # ROUGHLY TRANSLATES TO 10 SECONDS
				data += '\nbreaking due to timeout...'
				break
		data = string.replace(data, prompt, '').strip()
		return string.replace(data, cmd , '', 1).lstrip()
	
	def run(self):
		try:
			ssh = paramiko.SSHClient()
			ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			ssh.connect(self.ip, username=self.user, password=self.password)
			channel = ssh.invoke_shell()
			channel.set_combine_stderr(True)
		except:
			print self.ip + ' failed to connect'
			self.failed = True
			return
		while not channel.send_ready():print 'x'
		channel.sendall('PS1=' + prompt + '\n')
		self.recieve(channel, '')
		if self.cmd:
			while not channel.send_ready():print 'x'
			channel.sendall(self.cmd + '\n')
			self.format(self.recieve(channel, self.cmd))
		self.cmd = None
		self.ready = False
		while self.alive:
			if self.ready:
				if self.cmd == '#' or self.cmd == 'exit':
					ssh.close()
					self.alive = False
				else:
					while not channel.send_ready():print 'x'
					channel.sendall(self.cmd + '\n')
					self.format(self.recieve(channel, self.cmd))
					self.cmd = None
				self.ready = False
			else:
				time.sleep(0.1)
			
		
if __name__ == '__main__':
	readline.parse_and_bind('tab: complete')
	history_file = '/tmp/.multissh_history'
	if not os.path.exists(history_file):open(history_file, 'w')
	readline.read_history_file(history_file)
	
	parser = OptionParser()
	parser.add_option("-s", help="run a single command and quit", dest='single', action='store_true', default=False)
	parser.add_option("-S", help="keep list sorted the same as the host file", dest='keep_sorted', action='store_true', default=False)
	parser.add_option("-n", help="adds a newline between each result", dest='newline', action='store_true', default=False)
	parser.add_option("-c", "--command", dest="command", help="specify initial command to use", default=None)
	parser.add_option("-f", "--file", dest="file", help="specify host file to use", default=None)
	parser.add_option("-u", "--username", dest="username", help="specify username to use", default=None)
	parser.add_option("-p", "--password", dest="password", help="specify password to use", action='store_true', default=False)
	parser.add_option("-a", "--alias-file", dest="alias_file", help="specify an alias file to use", default=None)

	(options, args) = parser.parse_args()
	
	if options.command:readline.add_history(options.command)
	
	if options.file is None:sys.exit('Please specify a hosts file.')
	if not os.path.exists(options.file):sys.exit(options.file + ' does not exist.')
	
	aliases = {}
	if not options.alias_file is None:
		if os.path.exists(options.alias_file):
			for l in open(options.alias_file).readlines():
				l = l.strip().split(' ')
				aliases[l[0]] = ' '.join(l[1:])
		else:sys.exit(options.alias_file + ' does not exist.')
			
	def shell(shell_cmd):
		if shell_cmd == 'n':
			if options.newline == True:options.newline = False
			else:options.newline = True
		elif shell_cmd == 'p':
			print 'Aliases:'
			for k in sorted(aliases.keys()):
				print k + ': ' + aliases[k]
		elif aliases.has_key(shell_cmd):
			return aliases[shell_cmd]
		else:
			print 'unknown shell command: ' + shell_cmd
		return ''
	
	def terminate():
		for t in threads.values():
			t.alive = False
			t._Thread__stop()
		print ''
	
	show_output = True
	def wait(show_output):
		for t in threads.values():
			try:
				while t.ready and t.alive:
					if t.failed:
						break
					if not t.alive:
						break
					time.sleep(0.1)
			except KeyboardInterrupt:
				terminate()
				sys.exit()
		if show_output:
			hosts = sorted(threads.keys())
			if options.keep_sorted:
				hosts = thread_list
			remove_list = []
			for k in hosts:
				if threads[k].failed:
					del threads[k]
					remove_list.append(k)
					continue
				print threads[k].output
				if options.newline:print ''
			for h in remove_list:
				print 'removing ' + h
				hosts.remove(h)
	
	username = getpass.getuser()
	if options.username:username = options.username
	password = None
	if options.password:
		password = getpass.getpass('password:')
	
	threads = {}
	thread_list = []
	for ip in open(options.file).readlines():
		if ip[0] == '#':continue
		ip = ip.strip()
		if ip == '':continue
		if len(ip) > padding:padding = len(ip)
		
		# HANDLING NEWLINES IN PRINT INSTEAD
		#t = ssh_connection(username, password, ip, options.command, space=options.newline)
		t = ssh_connection(username, password, ip, options.command, space=False)
		threads[ip] = t
		thread_list.append(ip)
		t.start()
	
	wait(show_output)
	if options.single:
		for t in threads.values():
			t.cmd = 'exit'
			t.ready = True
			while t.alive:time.sleep(0.1)
		sys.exit()
			
	cmd=''
	while cmd != '#' or cmd != 'exit':
		try:
			cmd = raw_input(': ')
			if len(cmd) == 0:continue
			if len(cmd) > 1 and cmd[0] == '#':
				cmd = shell(cmd[1:])
				if cmd == '':
					continue
		except EOFError:
			cmd = '#'
			print ''
		except KeyboardInterrupt:
			terminate()
			break
		for t in threads.values():
			if cmd == '#':cmd = 'exit'
			if cmd == 'exit':show_output = False
			t.cmd = cmd
			t.ready = True
		wait(show_output)
		if cmd == '#' or cmd == 'exit':
			sys.exit()
		
	
