#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
"""
A shell to play crypic crosswords using CLI.
"""

import cmd
from copy import deepcopy
from enum import Enum
import io
import os
import pickle
import sys
from kitchen.text.converters import getwriter
sys.path.append('./guardian-crossword-scraper/')
from parser import *
__author__ = "Praveen Kumar"
__email__ = "areteix <at> gmail.com"

YELLOW='\033[93m'
BLUE='\033[94m'
NOCOL='\033[0m'
GREEN='\033[32m'
GRAY='\033[90m'
BOLD='\033[1m'

class XwdCli(cmd.Cmd):
    """CLI for Guardian cryptic crossword"""

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.prompt = BOLD + BLUE + '❭ ' + NOCOL
        self.sol = {
            "w" : 0,        # width
            "h" : 0,        # height
            "all" : None,   # solution as one string
            "grid" : [],    # solution grid
            "a" : {},       # across clues + metadata
            "d" : {},       # down clues + metadata
            }
        self.cn_rc = {}
        self.attempt = []   # attempted answer as a grid
        self.xwd = None
        self.prev_line = None
        self.assist = Assist.disable
        self.xid = None

    def print_warn(self, line):
        print YELLOW + 'Warn: ' + line + NOCOL

    def print_info(self, line):
        print BLUE + 'Info: ' + line + NOCOL

    def cmdloop(self):
        try:
            cmd.Cmd.cmdloop(self)
        except Exception as e:
            self.print_warn(str(e))
            self.cmdloop()

    def do_info(self, line):
        self.print_info("xid: " + str(self.xid))

    def help_play(self):
        print 'Usage: play <xwd_id>'
        print 'Starts http://www.theguardian.com/crosswords/cryptic/<xwd_id>'

    def do_play(self, xid):
        if not xid:
            self.help_play()
            return
        print "Fetching Guardian cryptic crossword: ", xid
        UTF8Writer = getwriter('utf8')
        nullout = UTF8Writer(io.open(os.devnull, 'wb'))
        bkp_stdout = sys.stdout
        sys.stdout = nullout

        xwd = get_crossword(xid, format='etree')
        self.xid = xid

        sys.stdout = bkp_stdout
        nullout.close()
        self.xwd = xwd

        if xwd is None:
            self.print_warn("Error 404: Invalid id")
            return


        print "You are playing: ", xwd.find('Title').attrib['v']
        print "Crossword copyright: ", xwd.find('Copyright').attrib['v']
        print "Type `help` to see available commands."
        self.sol["w"] = int(xwd.find('Width').attrib['v'])
        self.sol["h"] = int(xwd.find('Height').attrib['v'])
        self.sol["all"] = xwd.find('Allanswer').attrib['v']
        for i in range(self.sol["h"]):
            self.sol["grid"].append(list(self.sol["all"][15*i:15*(i+1)]))
        for x in xwd.find('across'):
            clue_attrib = dict(x.attrib)
            self.cn_rc[int(clue_attrib["cn"])] = ((int(clue_attrib["n"])-1)/self.sol["w"], (int(clue_attrib["n"])-1)%self.sol["w"])
            self.cn_rc[((int(clue_attrib["n"])-1)/self.sol["w"], (int(clue_attrib["n"])-1)%self.sol["w"])] = int(clue_attrib["cn"])
            self.sol["a"][x.tag] = clue_attrib
        for x in xwd.find('down'):
            clue_attrib = dict(x.attrib)
            self.cn_rc[int(clue_attrib["cn"])] = ((int(clue_attrib["n"])-1)/self.sol["w"], (int(clue_attrib["n"])-1)%self.sol["w"])
            self.cn_rc[((int(clue_attrib["n"])-1)/self.sol["w"], (int(clue_attrib["n"])-1)%self.sol["w"])] = int(clue_attrib["cn"])
            self.sol["d"][x.tag] = clue_attrib

        for i in range(self.sol["h"]):
            att_str = []
            for c in list(self.sol["grid"][i]):
                if c == '-':
                    att_str.append( u'█')
                else:
                    att_str.append(u' ')
            self.attempt.append(att_str)

    def do_etree(self, line):
        print(etree.tostring(self.xwd, pretty_print=True))

    def fancy(self, d):
        h = len(d)
        w = len(d[0])
        line = "   "
        for x in range(w):
            line +=  " %2d " % x
        print line
        top = "   ┌" + "───┬"*(w-1) + "───" + "┐"
        mid = "   ├" + "───┼"*(w-1) + "───" + "┤"
        bot = "   └" + "───┴"*(w-1) + "───" + "┘"
        print top
        for i,row in enumerate(d):
            row_str = '%2d '%i
            for j,ch in enumerate(row):
                if not (ch.isalpha() or ch == ' '):
                    row_str += u'|███'
                else:
                    if (ch == self.sol["grid"][i][j]) and (self.assist == Assist.letter):
                        color_ch = BOLD + GREEN + ch + NOCOL
                    else:
                        color_ch = BOLD + ch + NOCOL
                    if (i, j) in self.cn_rc:
                        row_str +=  GRAY + u'│%-2d'%self.cn_rc[(i,j)] + NOCOL + color_ch
                    else:
                        row_str +=  u'│  ' + color_ch
            row_str += u'│'
            print row_str
            if (not i == h-1):
                print mid
        print bot

    def help_solution(self):
        print 'Show the solution for the entire crossword'

    def do_solution(self, line):
        bkp_assist = self.assist
        self.assist = Assist.letter
        self.fancy(self.sol["grid"])
        self.assist = bkp_assist

    def help_cheat(self):
        print 'Reveal a word'
        print 'Usage: cheat <cn> <a/d>'
        print '    <cn> : clue number'
        print '    <a/d> : across or down'

    def do_cheat(self, line=None):
        if not line:
            line = self.prev_line
        if not line:
            self.print_warn("args not specified")
            self.help_cheat()
            return
        self.prev_line = line
        clue_num = int(line.split()[0])
        direction = line.split()[1][0].lower()

        found = False
        for k,v in self.sol[direction].iteritems():
            if int(v["cn"]) == clue_num:
                print GREEN + " ".join(list(v["a"])) + NOCOL
                found = True
                break
        if not found:
            self.print_warn("Invalid clue number!")

    def help_check(self):
        print 'Check a word'
        print 'Usage: check <cn ><a/d>'
        print '    <cn> : clue number'
        print '    <a/d> : across or down'
        print 'If no arg, then use arg from prev cmd'

    def do_check(self, line=None):
        bkp_assist = self.assist
        self.assist = Assist.letter
        self.do_clue(line)
        self.assist = bkp_assist


    def help_clue(self):
        print 'Shows the clue for specified item and optionally sets your answer'
        print 'Usage: clue [<cn> <a/d> [<answer>]]'
        print '    <cn> : clue number'
        print '    <a/d> : across or down'
        print '    [<answer>] : optionally set answer'
        print 'If no arg, then use arg from prev cmd'

    def do_clue(self, line=None):
        if not line:
            line = self.prev_line
        if not line:
            self.help_clue()
            return
        self.prev_line = line
        clue_num = int(line.split()[0])
        direction = line.split()[1][0].lower()
        answer = None
        if len(line.split()) > 2:
            answer = list("".join(line.split()[2:]).upper())
            print answer

        found = False
        for k,v in self.sol[direction].iteritems():
            if int(v["cn"]) == clue_num:
                found = True
                idx = int(v["n"])
                print v["c"]
        if not found:
            self.print_warn("Invalid clue number. Run `status` and check again")
            return

        row = idx / self.sol["w"]
        col = (idx % self.sol["w"]) - 1
        atmpt = ""
        is_correct = []
        full_word = False
        if direction == 'a':
            i = col
            if answer:
                answer.extend(['#']*self.sol['w'])
            while i < self.sol["w"]:
                if self.attempt[row][i] == u'█':
                    full_word = True
                    break
                if answer and (i < (col + len(answer))):
                    if answer[i-col].isalpha():
                        self.attempt[row][i] =  answer[i-col]
                    else:
                        self.attempt[row][i] =  ' '
                ch = string.replace(self.attempt[row][i], ' ', '_')
                if ch == self.sol["grid"][row][i]:
                    is_correct.append(True)
                else:
                    is_correct.append(False)
                atmpt += ch
                i += 1
        else:
            i = row
            if answer:
                answer.extend(['#']*self.sol['h'])
            while i < self.sol["h"]:
                if self.attempt[i][col] == u'█':
                    full_word = True
                    break
                if answer and (i < (row + len(answer))):
                    if answer[i-row].isalpha():
                        self.attempt[i][col] = answer[i-row]
                    else:
                        self.attempt[i][col] = ' '
                ch = string.replace(self.attempt[i][col], ' ', '_')
                if ch == self.sol["grid"][i][col]:
                    is_correct.append(True)
                else:
                    is_correct.append(False)
                atmpt += ch
                i += 1
        self.print_word(atmpt, is_correct, full_word)

    def print_word(self, atmpt, is_correct, full_word):
        if self.assist == Assist.word:
            color = True
            if full_word == True:
                for x in is_correct:
                    color = color and x
                    if not x:
                        break
                if color:
                    print GREEN + " ".join(list(atmpt)) + NOCOL
                else:
                    print " ".join(list(atmpt))

        elif self.assist == Assist.letter:
            word = " "
            for i,x in enumerate(atmpt):
                if is_correct[i]:
                    word += GREEN + x + " " + NOCOL
                else:
                    word += x + " "
            print word
        else:
            print " ".join(list(atmpt))


    def help_assist(self):
        print 'Usage: assist [option]'
        print '    option starts with l/w - highlight correct letters/words'
        print '    default disable'

    def do_assist(self,line=None):
        if line.lower().startswith('l'):
            self.assist = Assist.letter
        elif line.lower().startswith('w'):
            self.assist = Assist.word
        else:
            self.assist = Assist.disable

    def help_set(self):
        print "Usage: set <r> <c> <char>"
        print "Sets xwd[r][c] = char"

    def do_set(self, line):
        r = int(line.split()[0])
        c = int(line.split()[1])
        ch = line.split()[2][0]
        if self.attempt[r][c] != u'█':
            self.attempt[r][c] = ch.upper()

    def help_status(self):
        print 'Usage: status [l/w]'
        print 'Shows the current status of xwd'
        print '    l/w: Optionally show correct letters/words'
        print ' Note: currently supports only correct letters'


    def do_status(self, line=None):
        bkp_assist = self.assist
        if (line is not None) and line.startswith('l'):
            print "here"
            self.assist = Assist.letter
        self.fancy(self.attempt)
        self.assist = bkp_assist

    def help_save(self):
        print 'Usage: save [filename]'
        print 'Saves current xwd state to filename (optional)'

    def do_save(self, line=None):
        if not line:
            file_name = 'xwd.save'
        else:
            file_name = line
        with open(file_name, 'wb') as file_handle:
            state = deepcopy(self.__dict__)
            del state['stdout']
            del state['stdin']
            del state['xwd']
            pickle.dump(state, file_handle)
        self.print_info("Saved xwd to " + file_name)

    def help_load(self):
        print 'Usage: load [filename]'
        print 'Loads saved xwd state from filename (optional)'

    def do_load(self, line=None):
        if not line:
            file_name = 'xwd.save'
        else:
            file_name = line
        with open(file_name, 'rb') as file_handle:
            state = pickle.load(file_handle)
        self.__dict__.update(state)
        self.print_info("Loaded xwd from " + file_name)


    def do_clear(self, line):
        os.system(['clear','cls'][os.name == 'nt'])

    def do_q(self, line):
        return True

    def do_exit(self, line):
        return True

    def de_EOF(self, line):
        return True

    def postloop(self):
        cmd.Cmd.postloop(self)
        print "Goodbye!"

    def default(self, line):
        self.print_warn("Invalid command: " + line)

    def emptyline(self):
        return


class Assist(Enum):
    disable = 0
    word = 1
    letter = 2

if __name__ == '__main__':
    print 'xwd-shell - A shell to play crosswords\nType "help" for more information'
    XwdCli().cmdloop()
