#!/usr/bin/env python

# version 0.5

import warnings
warnings.simplefilter('ignore', DeprecationWarning)
import paramiko
import threading
import sys
import getpass
import time
import string
import os
import readline
from optparse import OptionParser

hosts = []
prompt = '___::'
padding = [0]

def load_host_file(f, default_username, default_password):
    if not f:sys.exit('Please specify a hosts file to use.')
    if not os.path.exists(f):sys.exit(f + ' does not exist.')
    for line in open(f).readlines():
        if line[0] == '#' or len(line) == 0:continue
        hosts.append(ssh_connection(line.strip(), username=default_username, password=default_password))
    for host in hosts:
        if len(host.host) > padding[0]:
            padding[0] = len(host.host)

def ssh_f(host, cmd):
    host.exec_cmd(cmd)

def format_host_output(host, data):
    r = ''
    for line in data.strip().split('\r\n'):
        line = line.strip()
        if len(line) > 0:
            r = r + '[' + host.rjust(padding[0]) + '] ' + line + '\n'
    if r == '': r = r + '[' + host.rjust(padding[0]) + '] '
    return r

class ssh_connection:
    def __init__(self, host, username='', password='', prompt_cmd='PS1='):
        self.host = host
        self.username = username
        self.port = '22'
        self.password = password
        if self.host.find(' ') > 0:self.host, self.password = self.host.split(' ')
        if self.host.find('@') > 0:self.username,self.host = self.host.split('@')
        if self.host.find(':') > 0:self.host,self.port = self.host.split(':')
        self.port = int(self.port)
        self.output = ''
        self.prompt_cmd = prompt_cmd
        self.connected = False
        self.ok = False

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
        data = string.replace(data, prompt, '').strip()
        return string.replace(data, cmd , '', 1).lstrip()

    def make_connection(self):
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(self.host, port=self.port, username=self.username, password=self.password)
            self.channel = self.ssh.invoke_shell()
            self.channel.set_combine_stderr(True)
            self.channel.sendall(self.prompt_cmd + prompt + '\n')
            self.channel.sendall('uptime\n')
            self.recieve(self.channel, 'uptime')
            self.connected = True
            self.ok = True
        except:
            print self.host + ' failed to connect'

    def exec_cmd(self, cmd):
        if not self.connected:
            self.make_connection()
        if self.ok:
            self.channel.sendall(cmd + '\n')
            self.output = self.recieve(self.channel, cmd)

    def close(self):
        if hasattr(self, 'ssh'):
            self.ssh.close()

    def __str__(self):
        return self.host

    def __cmp__(self, other):
        if self.host < other: return -1
        return 1

if __name__ == '__main__':
    readline.parse_and_bind('tab: complete')
    history_file = os.path.expanduser('~/.multissh_history')
    if not os.path.exists(history_file):open(history_file, 'w')
    readline.set_history_length(1000)
    readline.read_history_file(history_file)

    parser = OptionParser()
    #parser.add_option('-S', help='keep list sorted the same as the host file', dest='keep_sorted', action='store_true', default=False)
    #parser.add_option('-n', help='adds a newline between each result', dest='newline', action='store_true', default=False)
    #parser.add_option('-x', '--script', dest='script', help='specify local script to copy over and execute', default=None)
    #parser.add_option('-H', '--hosts', dest='hosts', help='specify comma seperated list of hosts to use', default=None)
    #parser.add_option('-P', dest='individual_password', help='specify password to use individual passwords per connection', action='store_true', default=False)
    parser.add_option('-c', '--command', dest='command', help='specify initial command to use', default=None)
    parser.add_option('-f', '--file', dest='hosts_file', help='specify host file to use', default=None)
    parser.add_option('-u', '--username', dest='username', help='specify username to use', default=None)
    parser.add_option('-s', '--single', help='run a single command and quit', dest='single', action='store_true', default=False)
    parser.add_option('-p', '--password', dest='password', help='specify password to use', action='store_true', default=False)
    parser.add_option('-a', '--alias-file', dest='alias_file', help='specify an alias file to use', default=None)
    parser.add_option('--prompt-cmd', dest='prompt_cmd', help='specify prompt command to use', default=None)
    (options, args) = parser.parse_args()

    default_password = ''
    if options.password:
        default_password = getpass.getpass('password: ')
    default_username = getpass.getuser()
    if options.username:
        default_username = options.username
    load_host_file(options.hosts_file, default_username, default_password)
    
    first_run = True
    while True:
        try:
            if first_run:
                if options.command:
                    cmd = options.command
                    readline.add_history(cmd)
                else:
                    cmd = 'uptime'
            else:
                cmd = raw_input(': ')
            if cmd == '':continue
            threads = []
            try:
                for host in hosts:
                    t = threading.Thread(target=ssh_f, args=(host, cmd))
                    threads.append(t)
                    t.start()
                for t in threads:t.join()
                for host in sorted(hosts):
                    if host.connected:
                        print format_host_output(host.host, host.output)
                    else:
                        hosts.remove(host)
            except KeyboardInterrupt:
                print 'attempting to quit...'
                sys.exit()
        except KeyboardInterrupt:
            print ''
            continue
        except EOFError:
            readline.write_history_file(history_file)
            print ''
            break
        if options.single:break
        options.command = None
        first_run = False

    for host in hosts:host.close()
