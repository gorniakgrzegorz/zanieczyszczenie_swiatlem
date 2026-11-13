# -*- coding: utf-8 -*-
"""Uruchamianie procesów pomocniczych (QProcess) z czytaniem wyjścia linia po linii; interfejs pozostaje responsywny.

Running helper processes (QProcess) with line-by-line output; the interface stays responsive.
"""
from qgis.PyQt.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal


class ProcJob(QObject):
    line = pyqtSignal(str)          # jedna linia wyjścia (stdout i stderr połączone)
    done = pyqtSignal(int, bool)    # kod wyjścia, czy proces się wysypał / exit code, whether the process crashed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._p = QProcess(self)
        self._p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._p.readyReadStandardOutput.connect(self._read)
        self._p.finished.connect(self._finished)
        self._p.errorOccurred.connect(self._error)
        self._buf = ''
        self._failed_to_start = False

    def start(self, program, args, env=None, cwd=None):
        self._buf = ''
        self._failed_to_start = False
        if env is not None:
            qenv = QProcessEnvironment()
            for k, v in env.items():
                qenv.insert(str(k), str(v))
            self._p.setProcessEnvironment(qenv)
        if cwd:
            self._p.setWorkingDirectory(cwd)
        self._p.start(program, [str(a) for a in args])

    def running(self):
        return self._p.state() != QProcess.ProcessState.NotRunning

    def kill(self):
        if self.running():
            self._p.kill()

    def _emit_lines(self, text, flush=False):
        self._buf += text
        parts = self._buf.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        self._buf = '' if flush else parts.pop()
        for ln in (parts if not flush else parts):
            if ln != '' or flush:
                self.line.emit(ln)

    def _read(self):
        data = bytes(self._p.readAllStandardOutput()).decode('utf-8', 'replace')
        self._emit_lines(data)

    def _error(self, err):
        if err == QProcess.ProcessError.FailedToStart:
            self._failed_to_start = True
            self.line.emit(f'FailedToStart: {self._p.errorString()}')
            self.done.emit(-1, True)

    def _finished(self, code, status):
        self._read()
        if self._buf:
            self._emit_lines('', flush=True)
        if self._failed_to_start:
            return
        crashed = status != QProcess.ExitStatus.NormalExit
        self.done.emit(int(code), crashed)
