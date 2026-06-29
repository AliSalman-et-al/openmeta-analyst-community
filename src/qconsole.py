from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QTextEdit

START_COLUMN = 3

class QConsole(QTextEdit):
    returnPressed = pyqtSignal()
    upArrowPressed = pyqtSignal()
    downArrowPressed = pyqtSignal()
        
    def __init__(self, parent):
        super(QConsole, self).__init__(parent)
        self.parent = parent
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            self.returnPressed.emit()
        elif event.key() == Qt.Key_Up:
            self.upArrowPressed.emit()
        elif event.key() == Qt.Key_Down:
            self.downArrowPressed.emit()
        elif event.key() in (Qt.Key_Left, Qt.Key_Backspace) and \
            self.textCursor().columnNumber() == START_COLUMN:
            # we just want to 'block' here, i.e., do nothing; the user
            # has navigated to the start of the column
            pass
            
        else:
            #self.keyPressEvent(event)
            super(QConsole, self).keyPressEvent(event)
            
    def mousePressEvent(self, event):
        ### this works but now you need to set the cursor 
        # on the console initially...
        #self.textCursor().setPosition(100)
        #self.find(">> ")
        ### you would think there'd be an easier
        # /less hacky way to do this..?
        for i in range(3):
            self.moveCursor(16)
        self.moveCursor(15)
        print("(mouse clicked)")
        
