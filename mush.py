#!/usr/bin/env python

# version 0.7

import warnings
warnings.simplefilter('ignore', DeprecationWarning)
import paramiko
import threading
import sys
import getpass
import time
import string
import os
import socket
import readline
from optparse import OptionParser

timeout = 60
verbose = False
prompt = '___::'
lock = threading.Lock()

def load_hosts(f, h, default_username, default_password):
    hosts = []
    if not f:
        sys.exit('Please specify a hosts file to use.')
    if not os.path.exists(f):
        sys.exit(f + ' does not exist.')
    for line in open(f).readlines():
        if line[0] == '#' or len(line) == 0:
            continue
        hosts.append(ssh_connection(line.strip(), username=default_username, password=default_password))
    for host in h:
        if len(host) > 0:
            hosts.append(ssh_connection(host, username=default_username, password=default_password))
    return hosts

def format_host_output(host, data, padding):
    r = ''
    for line in data.strip().split('\r\n'):
        line = line.strip()
        if len(line) > 0:
            r = r + '[' + host.rjust(padding) + '] ' + line + '\n'
    if r == '':
        r = r + '[' + host.rjust(padding) + '] '
    return r

class ssh_connection:
    def __init__(self, host, username='', password='', prompt_cmd='PS1='):
        self.host = host
        self.username = username
        self.port = '22'
        self.password = password
        if self.host.find(' ') > 0:
            self.host, self.password = self.host.split(' ')
        if self.host.find('@') > 0:
            self.username,self.host = self.host.split('@')
        if self.host.find(':') > 0:
            self.host,self.port = self.host.split(':')
        self.port = int(self.port)
        self.output = ''
        self.prompt_cmd = prompt_cmd
        self.connected = False
        self.ok = False

    def recieve(self, c, cmd):
        data = ''
        attempts = 0
        while len(data) == 0 or data[-len(prompt):].strip() != prompt:
            if not c.recv_ready():
                attempts += 1
                if attempts > timeout:
                    with lock:
                        choice = raw_input(self.host + ' has timed out, quit(y/n)? ')
                        if choice == 'y':
                            self.connected = False
                            return 'timed out' # change this to return a tuple
                        attempts = 0
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
            if verbose:
                print sys.exc_info()

    def exec_cmd(self, cmd):
        if not self.connected:
            self.make_connection()
        if self.ok:
            try:
                self.channel.sendall(cmd + '\n')
                self.output = self.recieve(self.channel, cmd)
            except socket.error:
                self.connected = False
                if verbose:
                    print sys.exc_info()
 
    def close(self):
        if hasattr(self, 'ssh'):
            self.ssh.close()

    def __str__(self):
        return self.host

    def __cmp__(self, other):
        if self.host < other:
            return -1
        return 1


if __name__ == '__main__':
    readline.parse_and_bind('tab: complete')
    history_file = os.path.expanduser('~/.multissh_history')
    if not os.path.exists(history_file):
        open(history_file, 'w')
    readline.set_history_length(1000)
    if sys.platform.lower().find('linux') > -1:
        readline.read_history_file(history_file)

    parser = OptionParser()
    parser.add_option('-c', '--command', dest='command', help='specify initial command to use', default=None)
    parser.add_option('-H', '--hosts', dest='hosts', help='specify comma seperated list of hosts to use', default='')
    parser.add_option('-f', '--file', dest='hosts_file', help='specify host file to use', default=None)
    parser.add_option('-u', '--username', dest='username', help='specify username to use', default=None)
    parser.add_option('-s', '--single', help='run a single command and quit', dest='single', action='store_true', default=False)
    parser.add_option('-p', '--password', dest='password', help='specify password to use', action='store_true', default=False)
    parser.add_option('-a', '--alias-file', dest='alias_file', help='specify an alias file to use', default=None)
    parser.add_option('-t', '--timeout', dest='timeout', help='specify a timeout to use', default=timeout)
    parser.add_option('-v', '--verbose', dest='verbose', help='be verbose with errors', action='store_true', default=False)
    parser.add_option('--prompt-cmd', dest='prompt_cmd', help='specify prompt command to use', default=None)
    (options, args) = parser.parse_args()

    default_password = ''
    if options.password:
        default_password = getpass.getpass('password: ')
    default_username = getpass.getuser()
    if options.username:
        default_username = options.username
    hosts = load_hosts(options.hosts_file, options.hosts.split(','), default_username, default_password)

    if options.timeout:
        timeout = int(options.timeout)

    verbose = options.verbose
    
    padding = max(len(h.host) for h in hosts)

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
            if cmd != '':
                threads = []
                try:
                    for host in hosts:
                        t = threading.Thread(target=host.exec_cmd, args=(cmd,))
                        t.daemon = True
                        threads.append(t)
                        t.start()

                    for t in threads:
                        t.join() # wait for the commands to complete

                    for host in sorted(hosts):
                        if host.connected:
                            print format_host_output(host.host, host.output, padding)
                        else:
                            hosts.remove(host)

                    if len(hosts) == 0:
                        break
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
        if options.single:
            break
        options.command = None
        first_run = False

    for host in hosts:
        host.close()
