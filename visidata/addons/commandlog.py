import time
import operator

from visidata import *

option('delay', 0.0, '--play delay between commands, in seconds')

globalCommand('D', 'vd.push(vd.commandlog)', 'push the commandlog')
globalCommand('^D', 'saveSheet(vd.commandlog, input("save to: ", "filename", value=fnSuffix("cmdlog-{0}.vd") or "cmdlog.vd"))', 'save commandlog to new file')
#globalCommand('KEY_BACKSPACE', 'vd.commandlog.undo()', 'remove last action on commandlog and replay')

# not necessary to log movements and scrollers
nonLogKeys = 'KEY_DOWN KEY_UP KEY_NPAGE KEY_PPAGE kDOWN kUP j k gj gk ^F ^B r < > { } / ? n N g/ g?'.split()
nonLogKeys += 'KEY_LEFT KEY_RIGHT h l gh gl c'.split()
nonLogKeys += 'zk zj zt zz zb zL zH zh zl zs ze zKEY_END zKEY_HOME zKEY_LEFT zKEY_RIGHT kLFT5 kRIT5'.split()
nonLogKeys += '^L ^C ^U ^D'.split()

def itemsetter(i):
    def g(obj, v):
        obj[i] = v
    return g

def namedlist(objname, fieldnames):
    class NamedListTemplate(list):
        __name__ = objname
        _fields = fieldnames

    for i, attrname in enumerate(fieldnames):
        # create property getter/setter for each field
        setattr(NamedListTemplate, attrname, property(operator.itemgetter(i), itemsetter(i)))

    return NamedListTemplate

CommandLogRow = namedlist('CommandLogRow', 'sheet col row keystrokes input comment'.split())

def fnSuffix(template):
    for i in range(1, 10):
        fn = template.format(i)
        if not Path(fn).exists():
            return fn

def getColVisibleIdxByFullName(sheet, name):
    for i, c in enumerate(sheet.visibleCols):
        if name == c.name:
            return i

def open_vd(p):
    return CommandLog(p.name, p)

# rowdef: CommandLog
class CommandLog(Sheet):
    'Log of commands for current session.'
    commands = [
        Command('x', 'sheet.replayOne(cursorRow); status("replayed one row")', 'replay this row of the commandlog'),
        Command('gx', 'sheet.replay()', 'replay this entire commandlog')
    ]
    columns = [ColumnAttr(x) for x in CommandLogRow._fields]

    currentReplayRow = None  # must be global, to allow replay

    def __init__(self, name, *args):
        super().__init__(name, *args)
        self.currentActiveRow = None

        self.sheetmap = {}   # sheet.name -> vs
        self.currentExecRow = None

    def reload(self):
        reload_tsv_sync(self)
        self.rows = [CommandLogRow(r) for r in self.rows]

    def undo(self):
        'Delete last command, reload sources, and replay entire log.'
        if len(self.rows) < 2:
            error('no more to undo')

        deletedRow = self.rows[-2]   # the command to undo
        del self.rows[-2:]           # delete the previous command and the undo command

        vd().sheets = [self]

        self.sheetmap = {}
        for r in self.rows:
            self.replayOne(r)

        status('undid "%s"' % deletedRow.keystrokes)

    def beforeExecHook(self, sheet, keystrokes, args=''):
        if sheet is self:
            return  # don't record editlog commands
        if self.currentActiveRow:
            self.afterExecSheet(sheet, False, '')
        self.currentActiveRow = CommandLogRow([sheet.name, sheet.cursorCol.name, sheet.cursorRowIndex, keystrokes, args, sheet._commands[keystrokes][1]])

    def afterExecSheet(self, sheet, escaped, err):
        'Records currentActiveRow'
        if not self.currentActiveRow:  # nothing to record
            return

        if err:
            self.currentActiveRow[-1] += ' [%s]' % err

        if sheet is not self:  # don't record jumps to commandlog
            # remove user-aborted commands and simple movements
            if not escaped and self.currentActiveRow.keystrokes not in nonLogKeys:
                self.addRow(self.currentActiveRow)

        self.currentActiveRow = None

    def openHook(self, vs, src):
        self.addRow(CommandLogRow(['', '', 0, 'o', src, 'open file']))

    def getSheet(self, sheetname):
        vs = self.sheetmap.get(sheetname)
        if not vs:
            matchingSheets = [x for x in vd().sheets if x.name == sheetname]
            if not matchingSheets:
                status(','.join(x.name for x in vd().sheets))
                return None
            vs = matchingSheets[0]
        return vs

    def replayOne(self, r, expectedThreads=0):
        'Replay the command in one given row.'
        CommandLog.currentReplayRow = r
        if r.sheet:
            vs = self.getSheet(r.sheet) or error('no sheets named %s' % r.sheet)

            if r.col != vs.cursorCol.name:
                vcolidx = getColVisibleIdxByFullName(vs, r.col)
                if vcolidx is not None:
                    vs.cursorVisibleColIndex = vcolidx
                # delay with simulated movement?
            vs.cursorRowIndex = int(r.row)
            # delay if row changed?

        else:
            vs = self

        vd().keystrokes = r.keystrokes
        escaped = vs.exec_keystrokes(r.keystrokes)

        if escaped:  # escapes should already have been filtered out
            error('unexpected escape')

        sync(expectedThreads)

        CommandLog.currentReplayRow = None

    def replay_sync(self, live=False):
        'Replay all commands in log.'
        self.sheetmap = {}

        for r in self.rows:
            time.sleep(options.delay)
            vd().statuses = []
            # sync should expect this thread if playing live
            self.replayOne(r, 1 if live else 0)

        status('replayed entire %s' % self.name)

    @async
    def replay(self):
        'Inject commands into live execution with interface.'
        self.replay_sync(live=True)

    def getLastArgs(self):
        'Get user input for the currently playing command.'
        if CommandLog.currentReplayRow is not None:
            return CommandLog.currentReplayRow.input
        else:
            return None

    def setLastArgs(self, args):
        'Set user input on last command, if not already set.'
        # only set if not already set (second input usually confirmation)
        if self.currentActiveRow is not None:
            if not self.currentActiveRow.input:
                self.currentActiveRow.input = args

vd().commandlog = CommandLog('commandlog')
vd().addHook('preexec', vd().commandlog.beforeExecHook)
vd().addHook('postexec', vd().commandlog.afterExecSheet)
vd().addHook('preedit', vd().commandlog.getLastArgs)
vd().addHook('postedit', vd().commandlog.setLastArgs)