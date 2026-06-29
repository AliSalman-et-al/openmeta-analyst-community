import sys
from PyQt5.QtCore import QEvent, Qt, pyqtSignal
from PyQt5.QtWidgets import QTextEdit
import pdb

class MATextEdit(QTextEdit):
    returnPressed = pyqtSignal()

    def __init__(self, *args):
        QTextEdit.__init__(self, *args)

    def event(self, event):
        if event.type()==QEvent.KeyPress:
            if event.key()==Qt.Key_Enter or event.key()==Qt.Key_Return:
                self.returnPressed.emit()
                return True
            elif event.key()==Qt.Key_Up:
                print("up??")
                return True

        return QTextEdit.event(self, event)
